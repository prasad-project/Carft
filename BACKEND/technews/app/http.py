"""HTTP helper: timeouts come from the client; this adds retries, exponential backoff and rate-limit handling."""
import logging
import time

import httpx

log = logging.getLogger(__name__)


class ConnectorError(Exception):
    pass


class RateLimited(ConnectorError):
    pass


def _retry_after(r: httpx.Response) -> float | None:
    v = r.headers.get("retry-after")
    try:
        return float(v) if v else None
    except ValueError:
        return None


def fetch(client, url, *, method="GET", params=None, headers=None, data=None, auth=None,
          retries=3, backoff=1.0, sleep=time.sleep, max_wait=60.0) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = client.request(method, url, params=params, headers=headers, data=data, auth=auth)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last = ConnectorError(f"network error calling {url}: {e}")
        else:
            limited = r.status_code == 429 or (r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0")
            if limited:
                last = RateLimited(f"rate limited by {url}")
                if attempt < retries:
                    wait = min(_retry_after(r) or backoff * 2 ** attempt, max_wait)
                    log.warning("rate_limited", extra={"url": url, "wait": wait})
                    sleep(wait)
                    continue
                raise last
            if r.status_code >= 500:
                last = ConnectorError(f"HTTP {r.status_code} from {url}")
            elif r.status_code >= 400:
                raise ConnectorError(f"HTTP {r.status_code} from {url}")
            else:
                return r
        if attempt < retries:
            sleep(min(backoff * 2 ** attempt, max_wait))
    raise last  # type: ignore[misc]

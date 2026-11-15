from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def next_runs(now: datetime, hours: str, tz: str, n: int = 3) -> list[datetime]:
    z = ZoneInfo(tz)
    hs = sorted({int(h) for h in hours.split(",") if h.strip()})
    local = now.astimezone(z)
    out, day = [], local.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(out) < n:
        for h in hs:
            t = day.replace(hour=h)
            if t > local and len(out) < n:
                out.append(t)
        day += timedelta(days=1)
    return out

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.api import admin, public
from app.config import get_settings
from app.logging_config import setup_logging

s = get_settings()
setup_logging()
if s.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=s.sentry_dsn, traces_sample_rate=0.0)

limiter = Limiter(key_func=get_remote_address, default_limits=[s.rate_limit_default], storage_uri=s.rate_limit_storage or s.redis_url)
app = FastAPI(title="Tech News API")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


@app.exception_handler(RateLimitExceeded)
async def _rl(request, exc):
    return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)


@app.on_event("startup")
def _seed():
    from app.db import SessionLocal
    from app.services.ingest import seed_reference_data
    try:
        with SessionLocal() as db:
            seed_reference_data(db)
    except Exception:
        logging.getLogger(__name__).exception("seed_failed (have migrations been applied?)")


app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"ok": True}

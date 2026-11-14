from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import extraction, results, upload
from .core.config import get_settings
from .core.logging import log
from .services.job_store import job_store
from .services.ocr_service import ocr_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store.purge_storage()

    async def janitor():
        while True:
            await asyncio.sleep(60)
            job_store.cleanup_expired()

    task = asyncio.create_task(janitor())
    log.info("started; ocr_available=%s", ocr_available())
    yield
    task.cancel()
    job_store.purge_storage()


def create_app() -> FastAPI:
    app = FastAPI(title="Resume Extraction Engine", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(get_settings().cors_origins), allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["Content-Disposition"])
    for r in (upload.router, extraction.router, results.router):
        app.include_router(r)

    @app.get("/health")
    async def health():
        return {"status": "ok", "ocr_available": ocr_available()}

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.error("unhandled %s on %s", type(exc).__name__, request.url.path)
        return JSONResponse({"detail": {"code": "INTERNAL_ERROR", "message": "Internal server error."}}, status_code=500)

    return app


app = create_app()

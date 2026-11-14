import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, domains, matches, players, rooms
from app.core.redis import init_redis
from app.core.security import ArenaError
from app.database.session import create_all
from app.game.engine import reconcile
from app.realtime import ws
from app.realtime.hub import start_subscriber

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_redis()
    await create_all()  # dev convenience; use Alembic migrations in prod
    sub = await start_subscriber()
    n = await reconcile()
    logging.getLogger("arena").info("startup reconcile cancelled %d orphaned matches", n)
    yield
    sub.cancel()


app = FastAPI(title="Coding Arena", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ArenaError)
async def arena_error(_: Request, e: ArenaError):
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


for m in (auth, domains, admin, rooms, matches, players):
    app.include_router(m.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")

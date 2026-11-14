from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_kw = {} if settings.database_url.startswith("sqlite") else {"pool_size": 20, "max_overflow": 20, "pool_pre_ping": True}
engine = create_async_engine(settings.database_url, **_kw)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    async with SessionLocal() as s:
        yield s


async def create_all():
    from app.database.models import Base
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)

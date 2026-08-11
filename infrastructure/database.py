from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from configs.config import settings

# engine = create_async_engine(settings.DATABASE_URL, echo=False)
# But settings.DATABASE_URL uses postgresql+asyncpg which is fine for async engine.
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://") if "asyncpg" not in settings.DATABASE_URL else settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SessionLocal = AsyncSessionLocal

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

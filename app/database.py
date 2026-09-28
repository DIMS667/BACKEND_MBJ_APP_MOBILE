import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    # Rafraîchit les connexions avant qu'un Postgres mutualisé ne les
    # coupe côté serveur pour inactivité (évite les erreurs "connexion
    # fermée" sur une connexion restée ouverte trop longtemps dans le pool).
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    committed = False
    force_cleanup = False
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            committed = True
            from app.core.storage_cleanup import has_new_file_deletions
            force_cleanup = has_new_file_deletions(session)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    if committed:
        from app.core.storage_cleanup import drain_pending_file_deletions
        try:
            await drain_pending_file_deletions(force=force_cleanup)
        except Exception:
            # The user-data transaction already committed; pending jobs remain
            # durable and will be retried on another request.
            logger.exception("Private file cleanup will be retried")

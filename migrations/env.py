import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ─── Ajouter le dossier racine au path Python ───────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ─── Importer les modèles pour l'autogenerate ───────────────────────────────
# Chaque module doit être importé ici pour que ses tables s'enregistrent sur
# Base.metadata avant que target_metadata ne soit capturé plus bas — sinon
# `alembic revision --autogenerate` ne voit qu'une partie du schéma et peut
# proposer de supprimer les tables des modules non importés.
from app.database import Base
from app.modules.auth.models import User, RefreshToken, PasswordResetCode  # noqa: F401
from app.modules.children.models import Child, SensoryProfile, ChildPreferences  # noqa: F401
from app.modules.communication.models import (  # noqa: F401
    PictoCategory,
    Pictogram,
    SentenceHistory,
    FavoritePicto,
    PictogramMedia,
)
from app.modules.games.models import GameCategory, Game, GameScore, GameProgress  # noqa: F401
from app.modules.stories.models import (  # noqa: F401
    Story,
    StoryPage,
    StoryChoice,
    StoryProgress,
    StoryFavorite,
    StoryMedia,
)
from app.modules.audio.models import AudioCategory, AudioFile  # noqa: F401
from app.modules.drawing.models import Drawing  # noqa: F401

# ─── Config Alembic ─────────────────────────────────────────────────────────
config = context.config

# Charger les logs depuis alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata cible pour l'autogenerate
target_metadata = Base.metadata


# ─── Charger l'URL depuis le .env via nos settings ──────────────────────────
from app.config import settings

# Convertir l'URL async → sync pour Alembic (asyncpg → psycopg2 ou psycopg)
# Alembic a besoin d'une URL synchrone pour certaines opérations internes
db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
config.set_main_option("sqlalchemy.url", db_url)


# ─── Mode OFFLINE ────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Migrations sans connexion active — génère le SQL brut."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ─── Mode ONLINE (async) ─────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Crée un engine async et exécute les migrations."""
    # Reconstruire l'URL async pour l'engine
    async_url = settings.DATABASE_URL  # postgresql+asyncpg://...

    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(async_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Point d'entrée pour les migrations en mode online."""
    asyncio.run(run_async_migrations())


# ─── Exécution ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
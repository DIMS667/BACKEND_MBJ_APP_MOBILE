import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from app.config import settings
from app.core.rate_limit import limiter
from app.database import engine
from app.modules.auth.router import router as auth_router
from app.modules.children.router import router as children_router
from app.modules.communication.router import router as communication_router
from app.modules.emotions.router import router as emotions_router
from app.modules.routines.router import router as routines_router
from app.modules.games.router import router as games_router
from app.modules.stories.router import router as stories_router
from app.modules.audio.router import router as audio_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.drawing.router import router as drawing_router
from app.websocket.router import router as ws_router
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(
    title="Maison Bleue Kids API",
    description="API pour l'application mobile éducative TSA",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Fichiers statiques (pictos + audio gTTS) ─────────────────
# ⚠️ Doit être AVANT add_middleware
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Compresse les réponses JSON/texte (rapport dashboard, listes de pictos et
# d'histoires) — n'affecte pas le streaming audio/image, déjà binaire.
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth_router,          prefix="/auth",      tags=["Auth"])
app.include_router(children_router,      prefix="/children",  tags=["Children"])
app.include_router(communication_router, prefix="/pictos",    tags=["Communication"])
app.include_router(emotions_router,      prefix="/emotions",  tags=["Emotions"])
app.include_router(routines_router,      prefix="/routines",  tags=["Routines"])
app.include_router(games_router,         prefix="/games",     tags=["Games"])
app.include_router(stories_router,       prefix="/stories",   tags=["Stories"])
app.include_router(audio_router,         prefix="/audio",     tags=["Audio"])
app.include_router(dashboard_router,     prefix="/dashboard", tags=["Dashboard"])
app.include_router(drawing_router,       prefix="/drawing",   tags=["Drawing"])
app.include_router(ws_router,            tags=["WebSocket"])


# ── Migrations DB au démarrage ────────────────────────────────
# Applique automatiquement les migrations Alembic en attente pour éviter
# qu'un schéma local en retard (ex: colonne manquante) ne casse l'API
# au premier appel plutôt qu'au démarrage.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
# Clé arbitraire fixe pour le verrou consultatif Postgres — seul son
# unicité au sein de l'app compte, pas sa valeur.
_MIGRATION_LOCK_KEY = 823_615_047


@app.on_event("startup")
async def run_pending_migrations() -> None:
    # Verrou consultatif Postgres : si l'hébergeur lance plusieurs workers
    # (Passenger peut en démarrer plus d'un), ils ne doivent pas tous courir
    # `alembic upgrade head` en même temps sur le même schéma. Le premier
    # worker prend le verrou et migre ; les suivants attendent puis trouvent
    # le schéma déjà à jour (upgrade devient un no-op).
    async with engine.connect() as conn:
        await conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _MIGRATION_LOCK_KEY})
        try:
            alembic_cfg = AlembicConfig(str(_BACKEND_DIR / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
            await run_in_threadpool(command.upgrade, alembic_cfg, "head")
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _MIGRATION_LOCK_KEY})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
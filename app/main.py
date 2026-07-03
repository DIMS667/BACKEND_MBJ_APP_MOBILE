from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.children.router import router as children_router
from app.modules.communication.router import router as communication_router
from app.modules.emotions.router import router as emotions_router
from app.modules.routines.router import router as routines_router
from app.modules.games.router import router as games_router
from app.modules.stories.router import router as stories_router
from app.modules.audio.router import router as audio_router
from app.modules.dashboard.router import router as dashboard_router
from app.websocket.router import router as ws_router
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI(
    title="Maison Bleue Kids API",
    description="API pour l'application mobile éducative TSA",
    version="1.0.0",
)

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

app.include_router(auth_router,          prefix="/auth",      tags=["Auth"])
app.include_router(children_router,      prefix="/children",  tags=["Children"])
app.include_router(communication_router, prefix="/pictos",    tags=["Communication"])
app.include_router(emotions_router,      prefix="/emotions",  tags=["Emotions"])
app.include_router(routines_router,      prefix="/routines",  tags=["Routines"])
app.include_router(games_router,         prefix="/games",     tags=["Games"])
app.include_router(stories_router,       prefix="/stories",   tags=["Stories"])
app.include_router(audio_router,         prefix="/audio",     tags=["Audio"])
app.include_router(dashboard_router,     prefix="/dashboard", tags=["Dashboard"])
app.include_router(ws_router,            tags=["WebSocket"])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    print("=== VALIDATION ERROR ===")
    print(exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
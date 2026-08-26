from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.dependencies import get_db
from .schemas import (
    AudioCategoryResponse,
    AudioFileResponse,
    AudioListResponse,
)
from . import service

router = APIRouter()


# ─── Catégories ──────────────────────────────────────────────────
@router.get("/categories", response_model=List[AudioCategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await service.get_categories(db)


# ─── Liste des fichiers audio ────────────────────────────────────
@router.get("/", response_model=List[AudioFileResponse])
async def get_files(
    category: Optional[str] = Query(
        default=None,
        description="narration / calming / feedback / tts"
    ),
    db: AsyncSession = Depends(get_db),
):
    if category:
        return await service.get_files_by_category(db, category)
    return await service.get_all_files(db)


# ─── Détail d'un fichier ─────────────────────────────────────────
@router.get("/{audio_id}", response_model=AudioFileResponse)
async def get_file(
    audio_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_file_by_id(db, audio_id)


# ─── Streaming audio ─────────────────────────────────────────────
@router.get("/{audio_id}/stream")
async def stream_audio(
    audio_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await service.stream_audio(db, audio_id, request)
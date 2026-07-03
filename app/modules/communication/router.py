from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User
from .schemas import (
    PictoCategoryResponse, PictogramResponse,
    ToggleFavoriteRequest, ToggleFavoriteResponse,
    SpeechRequest, SpeechResponse,
    SentenceHistoryResponse,
)
from . import service

router = APIRouter()


# ─── Catégories ──────────────────────────────────────────────────
@router.get("/categories", response_model=List[PictoCategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await service.get_categories(db)


# ─── Pictogrammes ────────────────────────────────────────────────
@router.get("/", response_model=List[PictogramResponse])
async def get_all_pictos(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_all_pictos(db, child_id)


@router.get("/category/{category_id}", response_model=List[PictogramResponse])
async def get_pictos_by_category(
    category_id: int,
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_pictos_by_category(db, category_id, child_id)


# ─── Favoris ─────────────────────────────────────────────────────
@router.post("/{picto_id}/favorite", response_model=ToggleFavoriteResponse)
async def toggle_favorite(
    picto_id: int,
    data: ToggleFavoriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.toggle_favorite(db, picto_id, data, current_user.id)


@router.get("/favorites/{child_id}", response_model=List[PictogramResponse])
async def get_favorites(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_favorites(db, child_id, current_user.id)


# ─── Synthèse vocale ─────────────────────────────────────────────
@router.post("/speech", response_model=SpeechResponse)
async def generate_speech(
    data: SpeechRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.generate_speech(db, data, current_user.id)


# ─── Historique ──────────────────────────────────────────────────
@router.get("/history/{child_id}")
async def get_history(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_history(db, child_id, current_user.id)
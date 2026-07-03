from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User
from .schemas import (
    EmotionResponse,
    EmotionRecordCreate,
    EmotionRecordResponse,
    EmotionStatsResponse,
    CalmingActivityResponse,
)
from . import service

router = APIRouter()


# ─── Liste des émotions ──────────────────────────────────────────
@router.get("/", response_model=List[EmotionResponse])
async def get_emotions(db: AsyncSession = Depends(get_db)):
    return await service.get_all_emotions(db)


# ─── Enregistrer une émotion ─────────────────────────────────────
@router.post("/record", response_model=EmotionRecordResponse, status_code=201)
async def record_emotion(
    data: EmotionRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.save_emotion(db, data, current_user.id)


# ─── Historique ──────────────────────────────────────────────────
@router.get("/{child_id}/history", response_model=List[EmotionRecordResponse])
async def get_history(
    child_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_emotion_history(db, child_id, current_user.id, limit)


# ─── Statistiques ────────────────────────────────────────────────
@router.get("/{child_id}/stats", response_model=EmotionStatsResponse)
async def get_stats(
    child_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_emotion_stats(db, child_id, current_user.id, days)


# ─── Activités apaisantes ────────────────────────────────────────
@router.get("/calming-activities", response_model=List[CalmingActivityResponse])
async def get_calming_activities(
    type: Optional[str] = Query(default=None, description="breathing, music, animation, game"),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_calming_activities(db, type)
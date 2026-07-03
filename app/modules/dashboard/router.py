from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User, UserRole
from app.core.dependencies import require_role
from .schemas import (
    ProgressResponse,
    StatsResponse,
    EmotionTrendsResponse,
    ReportResponse,
)
from . import service

router = APIRouter()


# ─── Progression globale ─────────────────────────────────────────
@router.get("/{child_id}/progress", response_model=ProgressResponse)
async def get_progress(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_progress(db, child_id, current_user.id)


# ─── Statistiques détaillées ─────────────────────────────────────
@router.get("/{child_id}/stats", response_model=StatsResponse)
async def get_stats(
    child_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_stats(db, child_id, current_user.id, days)


# ─── Tendances émotionnelles ─────────────────────────────────────
@router.get("/{child_id}/emotions", response_model=EmotionTrendsResponse)
async def get_emotion_trends(
    child_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_emotion_trends(db, child_id, current_user.id, days)


# ─── Rapport exportable ──────────────────────────────────────────
@router.get("/{child_id}/report", response_model=ReportResponse)
async def generate_report(
    child_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.generate_report(db, child_id, current_user.id, days)
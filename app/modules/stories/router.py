from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User
from .schemas import (
    StoryResponse,
    StoryDetailResponse,
    StoryProgressCreate,
    StoryProgressResponse,
    ChildStoriesProgressResponse,
)
from . import service

router = APIRouter()


# ─── Liste des histoires ─────────────────────────────────────────
@router.get("/", response_model=List[StoryResponse])
async def get_stories(
    category: Optional[str] = Query(
        default=None,
        description="greeting/turn/sharing/doctor/school/help/anger"
    ),
    difficulty: Optional[int] = Query(
        default=None,
        description="1=facile, 2=moyen, 3=difficile"
    ),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_all_stories(db, category, difficulty)


# ─── Détail d'une histoire ───────────────────────────────────────
@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story(
    story_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_story_detail(db, story_id)


# ─── Sauvegarder la progression ──────────────────────────────────
@router.post("/{story_id}/progress", response_model=StoryProgressResponse)
async def save_progress(
    story_id: int,
    data: StoryProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.save_progress(db, story_id, data, current_user.id)


# ─── Progression d'un enfant ─────────────────────────────────────
@router.get("/progress/{child_id}", response_model=ChildStoriesProgressResponse)
async def get_child_progress(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_child_progress(db, child_id, current_user.id)
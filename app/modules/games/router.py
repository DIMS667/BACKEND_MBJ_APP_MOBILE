from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User
from .schemas import (
    GameCategoryResponse,
    GameResponse,
    GameScoreCreate,
    GameScoreResponse,
    GameContentResponse,
    GameProgressResponse,
    SubmitScoreResponse,
    ChildGamesProgressResponse,
)
from . import service

router = APIRouter()


# ─── Catégories ──────────────────────────────────────────────────
@router.get("/categories", response_model=List[GameCategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await service.get_categories(db)


# ─── Liste des jeux ──────────────────────────────────────────────
@router.get("/", response_model=List[GameResponse])
async def get_all_games(
    category_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if category_id:
        return await service.get_games_by_category(db, category_id)
    return await service.get_all_games(db)


# ─── Détail d'un jeu ─────────────────────────────────────────────
@router.get("/{game_id}/content", response_model=GameContentResponse)
async def get_game_content(
    game_id: int,
    level: int = Query(default=1, ge=1, le=5),
    challenge_rank: Optional[int] = Query(default=None, ge=1, le=15),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_game_content(db, game_id, level, challenge_rank)


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_game_by_id(db, game_id)


# ─── Soumettre un score ──────────────────────────────────────────
@router.post("/{game_id}/score", response_model=SubmitScoreResponse)
async def submit_score(
    game_id: int,
    data: GameScoreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.submit_score(db, game_id, data, current_user.id)


# ─── Progression d'un enfant ─────────────────────────────────────
@router.get("/progress/{child_id}", response_model=ChildGamesProgressResponse)
async def get_child_progress(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_child_progress(db, child_id, current_user.id)


# ─── Historique des scores ───────────────────────────────────────
@router.get("/{game_id}/scores/{child_id}", response_model=List[GameScoreResponse])
async def get_game_scores(
    game_id: int,
    child_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_game_scores(
        db, game_id, child_id, current_user.id, limit
    )

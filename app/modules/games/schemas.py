from pydantic import BaseModel, Field
from typing import Optional, List


# ─── Catégorie ───────────────────────────────────────────────────
class GameCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    color: str
    order: int

    model_config = {"from_attributes": True}


# ─── Jeu ─────────────────────────────────────────────────────────
class GameResponse(BaseModel):
    id: int
    category_id: int
    title: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    min_level: int
    max_level: int
    is_offline_available: bool
    category: GameCategoryResponse

    model_config = {"from_attributes": True}


# ─── Score ───────────────────────────────────────────────────────
class GameScoreCreate(BaseModel):
    child_id: int
    score: int = Field(..., ge=0)
    level: int = Field(..., ge=1)
    duration_seconds: Optional[int] = Field(None, ge=0)


class GameScoreResponse(BaseModel):
    id: int
    game_id: int
    child_id: int
    score: int
    level: int
    duration_seconds: Optional[int] = None

    model_config = {"from_attributes": True}


# ─── Progression ─────────────────────────────────────────────────
class GameProgressResponse(BaseModel):
    game_id: int
    child_id: int
    current_level: int
    best_score: int
    total_plays: int
    game: GameResponse

    model_config = {"from_attributes": True}


# ─── Résultat soumission score ───────────────────────────────────
class SubmitScoreResponse(BaseModel):
    score_id: int
    game_id: int
    child_id: int
    score: int
    level: int
    best_score: int
    current_level: int
    level_up: bool          # l'enfant vient de monter de niveau
    message: str            # message bienveillant (CDC)
    reward_animation: str   # animation de récompense douce


# ─── Résumé progression globale ──────────────────────────────────
class ChildGamesProgressResponse(BaseModel):
    child_id: int
    total_games_played: int
    total_plays: int
    progress: List[GameProgressResponse]
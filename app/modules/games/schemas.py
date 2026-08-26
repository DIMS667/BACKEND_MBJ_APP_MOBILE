from pydantic import BaseModel, Field, model_validator
from typing import Any, Optional, List


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


# ─── Contenu dynamique des jeux ───────────────────────────────────────────────
class GameContentAsset(BaseModel):
    id: str
    label: str
    emoji: str
    category: str
    image_url: Optional[str] = None


class GameContentPair(BaseModel):
    left: GameContentAsset
    right: GameContentAsset


class GameContentRound(BaseModel):
    id: str
    type: str
    instruction: str
    prompt: Optional[GameContentAsset] = None
    answer: Optional[GameContentAsset] = None
    choices: List[GameContentAsset] = Field(default_factory=list)
    items: List[GameContentAsset] = Field(default_factory=list)
    pairs: List[GameContentPair] = Field(default_factory=list)
    sequence: List[GameContentAsset] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GameContentResponse(BaseModel):
    game_id: int
    game_title: str
    content_version: int
    session_id: str
    level: int
    challenge_rank: int = Field(default=1, ge=1, le=15)
    max_challenge_rank: int = Field(default=15, ge=1, le=15)
    mode: str
    theme: str
    instructions: str
    rounds: List[GameContentRound]


# ─── Score ───────────────────────────────────────────────────────
class GameScoreCreate(BaseModel):
    child_id: int
    score: int = Field(..., ge=0, le=100)
    level: int = Field(..., ge=1, le=5)
    duration_seconds: Optional[int] = Field(None, ge=0, le=7200)
    session_id: Optional[str] = Field(None, min_length=8, max_length=64)
    # Defaults keep older mobile clients compatible, but their sessions have
    # zero learning evidence and therefore cannot validate a new level.
    correct_answers: int = Field(default=0, ge=0, le=100)
    total_questions: int = Field(default=0, ge=0, le=100)
    mistake_count: int = Field(default=0, ge=0, le=1000)
    hints_used: int = Field(default=0, ge=0, le=100)
    completed: bool = True

    @model_validator(mode="after")
    def validate_answers(self):
        if self.correct_answers > self.total_questions:
            raise ValueError(
                "correct_answers ne peut pas depasser total_questions"
            )
        return self


class GameScoreResponse(BaseModel):
    id: int
    game_id: int
    child_id: int
    score: int
    level: int
    duration_seconds: Optional[int] = None
    session_id: Optional[str] = None
    correct_answers: int = 0
    total_questions: int = 0
    mistake_count: int = 0
    hints_used: int = 0
    completed: bool = True
    independent_success: bool = False
    evidence_score: int = 0

    model_config = {"from_attributes": True}


# ─── Progression ─────────────────────────────────────────────────
class GameProgressResponse(BaseModel):
    game_id: int
    child_id: int
    current_level: int
    best_score: int
    total_plays: int
    mastery_percent: int = 0
    independent_streak: int = 0
    struggle_streak: int = 0
    is_mastered: bool = False
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
    level_down: bool = False  # adaptation douce invisible
    independent_success: bool = False
    assisted_success: bool = False
    mastery_percent: int = 0
    independent_streak: int = 0
    required_independent_successes: int = 3
    evidence_score: int = 0
    learning_status: str = "discovering"
    message: str            # message bienveillant (CDC)
    reward_animation: str   # animation de récompense douce


# ─── Résumé progression globale ──────────────────────────────────
class ChildGamesProgressResponse(BaseModel):
    child_id: int
    total_games_played: int
    total_plays: int
    progress: List[GameProgressResponse]

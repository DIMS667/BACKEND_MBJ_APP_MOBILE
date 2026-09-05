from pydantic import BaseModel
from typing import Optional, List


# ─── Progression par module ──────────────────────────────────────
class ModuleProgressItem(BaseModel):
    module_name: str
    total_activities: int
    completed_activities: int
    completion_rate: float      # pourcentage
    last_activity: Optional[str] = None


class ProgressResponse(BaseModel):
    child_id: int
    child_name: str
    global_completion_rate: float
    modules: List[ModuleProgressItem]


# ─── Statistiques détaillées ─────────────────────────────────────
class GameStatsItem(BaseModel):
    game_title: str
    category: str
    total_plays: int
    best_score: int
    current_level: int
    average_score: float


class StoryStatsItem(BaseModel):
    story_title: str
    category: str
    read_count: int
    is_completed: bool
    last_page: int
    total_pages: int


class StatsResponse(BaseModel):
    child_id: int
    period_days: int
    # Jeux
    games_played: int
    total_game_sessions: int
    game_stats: List[GameStatsItem]
    # Histoires
    stories_started: int
    stories_completed: int
    story_stats: List[StoryStatsItem]
    # Communication
    sentences_built: int
    favorite_pictos: int


# ─── Rapport exportable ──────────────────────────────────────────
class ReportResponse(BaseModel):
    child_id: int
    child_name: str
    generated_at: str
    period_days: int
    # Résumé global
    summary: str
    # Sections
    progress: ProgressResponse
    stats: StatsResponse
    # Recommandations
    recommendations: List[str]
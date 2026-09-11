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
    """Statistiques d'un enfant.

    Les champs sont séparés en deux familles, parce que les mélanger
    rendait le filtre de période trompeur : un parent choisissait
    « 7 jours » et quatre chiffres sur cinq ne bougeaient pas.
    """

    child_id: int
    period_days: int

    # ── Sur la période choisie (7, 30 ou 90 jours) ────────────────
    games_played: int
    total_game_sessions: int
    stories_started: int
    stories_completed: int
    sentences_built: int

    # ── Cumuls depuis le début, et préférences actuelles ──────────
    all_time_game_sessions: int
    all_time_games_played: int
    all_time_stories_started: int
    all_time_stories_completed: int
    favorite_pictos: int

    # ── Détail par activité (cumul) ───────────────────────────────
    game_stats: List[GameStatsItem]
    story_stats: List[StoryStatsItem]


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
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


class RoutineStatsItem(BaseModel):
    routine_title: str
    type: str
    total_sessions: int
    completed_sessions: int
    completion_rate: float


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
    # Routines
    routines_total: int
    routines_completed: int
    routine_stats: List[RoutineStatsItem]
    # Histoires
    stories_started: int
    stories_completed: int
    story_stats: List[StoryStatsItem]
    # Communication
    sentences_built: int
    favorite_pictos: int


# ─── Tendances émotionnelles ─────────────────────────────────────
class EmotionTrendItem(BaseModel):
    emotion_name: str
    color: str
    count: int
    percentage: float


class DailyEmotionItem(BaseModel):
    date: str
    emotion_name: str
    color: str
    context: Optional[str] = None


class EmotionTrendsResponse(BaseModel):
    child_id: int
    period_days: int
    total_records: int
    most_frequent_emotion: Optional[str] = None
    positive_rate: float        # % d'émotions positives
    trends: List[EmotionTrendItem]
    recent_history: List[DailyEmotionItem]


# ─── Rapport exportable ──────────────────────────────────────────
class ReportResponse(BaseModel):
    child_id: int
    child_name: str
    child_age: int
    generated_at: str
    period_days: int
    # Résumé global
    summary: str
    # Sections
    progress: ProgressResponse
    stats: StatsResponse
    emotion_trends: EmotionTrendsResponse
    # Recommandations
    recommendations: List[str]
from pydantic import BaseModel
from typing import Optional, List


# ─── Progression par module ──────────────────────────────────────
class ModuleProgressItem(BaseModel):
    module_name: str
    total_activities: int
    completed_activities: int
    completion_rate: float      # pourcentage
    # Ce que la barre compte réellement : les trois modules n'ont pas le
    # même dénominateur (jeux essayés, catalogue entier, fenêtre de jours).
    detail_label: str = ""
    last_activity: Optional[str] = None


class ProgressResponse(BaseModel):
    """Progression d'un enfant, en trois mesures distinctes.

    Un pourcentage global unique remplaçait ces trois-là : c'était la
    moyenne de ratios qui ne mesurent pas la même chose — maîtrise d'un
    jeu, découverte du catalogue et régularité d'usage. Chacune est
    désormais publiée avec son numérateur et son dénominateur, pour
    qu'aucune ne puisse être lue pour une autre.
    """

    child_id: int
    child_name: str

    # Ce qui a été essayé, rapporté à ce qui existe.
    discovery_rate: float
    discovery_done: int
    discovery_total: int

    # Parmi les jeux essayés, ceux menés au niveau maximum.
    mastery_rate: float
    mastery_done: int
    mastery_total: int

    # Jours où l'enfant a composé au moins une phrase, sur la fenêtre.
    regularity_rate: float
    regularity_done: int
    regularity_total: int

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

    # Dessin : des comptages, pas un taux — il n'y a rien à « terminer ».
    drawings_created: int = 0
    free_drawings: int = 0
    coloring_drawings: int = 0

    # ── Cumuls depuis le début, et préférences actuelles ──────────
    all_time_game_sessions: int
    all_time_games_played: int
    all_time_stories_started: int
    all_time_stories_completed: int
    all_time_drawings: int = 0
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
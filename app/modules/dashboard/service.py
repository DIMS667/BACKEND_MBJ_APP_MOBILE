from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from app.modules.children.models import Child
from app.modules.games.models import Game, GameScore, GameProgress
from app.modules.stories.models import Story, StoryProgress
from app.modules.communication.models import SentenceHistory, FavoritePicto

# Communication n'a pas de "total" fini à atteindre (contrairement aux
# jeux/histoires) : son taux de progression reflète la régularité d'usage
# sur cette fenêtre plutôt qu'un volume figé à 100% dès le 1er usage.
PROGRESS_ENGAGEMENT_WINDOW_DAYS = 30


# ─── Vérifier ownership ──────────────────────────────────────────
async def _get_child(
    db: AsyncSession, child_id: int, parent_id: int
) -> Child:
    result = await db.execute(
        select(Child).where(Child.id == child_id)
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enfant introuvable."
        )
    if child.parent_id != parent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé."
        )
    return child


# ─── Progression globale ─────────────────────────────────────────
async def get_progress(
    db: AsyncSession, child_id: int, parent_id: int
) -> dict:
    child = await _get_child(db, child_id, parent_id)
    modules = []

    # ── Jeux ──────────────────────────────────────────────────────
    games_progress_result = await db.execute(
        select(GameProgress)
        .options(selectinload(GameProgress.game))
        .where(GameProgress.child_id == child_id)
    )
    games_progress = games_progress_result.scalars().all()

    total_game_plays = sum(g.total_plays for g in games_progress)
    last_game_result = await db.execute(
        select(GameScore.created_at)
        .where(GameScore.child_id == child_id)
        .order_by(GameScore.created_at.desc())
        .limit(1)
    )
    last_game = last_game_result.scalar_one_or_none()

    # Un jeu est "maîtrisé" si l'enfant est au niveau max
    mastered_games = sum(
        1 for g in games_progress
        if g.current_level >= g.game.max_level
    )
    game_rate = round(
        (mastered_games / len(games_progress) * 100)
        if games_progress else 0, 1
    )
    modules.append({
        "module_name": "Jeux",
        "total_activities": len(games_progress),
        "completed_activities": mastered_games,
        "completion_rate": game_rate,
        "last_activity": str(last_game) if last_game else None,
    })

    # ── Histoires ─────────────────────────────────────────────────
    stories_result = await db.execute(select(func.count(Story.id)))
    total_stories = stories_result.scalar() or 0

    stories_progress_result = await db.execute(
        select(StoryProgress)
        .where(StoryProgress.child_id == child_id)
    )
    stories_progress = stories_progress_result.scalars().all()
    completed_stories = sum(1 for s in stories_progress if s.is_completed)

    last_story_result = await db.execute(
        select(StoryProgress.updated_at)
        .where(StoryProgress.child_id == child_id)
        .order_by(StoryProgress.updated_at.desc())
        .limit(1)
    )
    last_story = last_story_result.scalar_one_or_none()

    story_rate = round(
        (completed_stories / total_stories * 100) if total_stories > 0 else 0, 1
    )
    modules.append({
        "module_name": "Histoires",
        "total_activities": total_stories,
        "completed_activities": completed_stories,
        "completion_rate": story_rate,
        "last_activity": str(last_story) if last_story else None,
    })

    # ── Communication ─────────────────────────────────────────────
    engagement_since = datetime.now(timezone.utc) - timedelta(
        days=PROGRESS_ENGAGEMENT_WINDOW_DAYS
    )
    comm_agg_result = await db.execute(
        select(
            func.max(SentenceHistory.created_at),
            func.count(
                func.distinct(func.date(SentenceHistory.created_at))
            ).filter(SentenceHistory.created_at >= engagement_since),
        )
        .where(SentenceHistory.child_id == child_id)
    )
    last_sentence, active_comm_days = comm_agg_result.one()
    active_comm_days = active_comm_days or 0

    modules.append({
        "module_name": "Communication",
        "total_activities": PROGRESS_ENGAGEMENT_WINDOW_DAYS,
        "completed_activities": active_comm_days,
        "completion_rate": round(
            active_comm_days / PROGRESS_ENGAGEMENT_WINDOW_DAYS * 100, 1
        ),
        "last_activity": str(last_sentence) if last_sentence else None,
    })

    # ── Taux global ───────────────────────────────────────────────
    rates = [m["completion_rate"] for m in modules if m["total_activities"] > 0]
    global_rate = round(sum(rates) / len(rates), 1) if rates else 0.0

    return {
        "child_id": child_id,
        "child_name": child.first_name,
        "global_completion_rate": global_rate,
        "modules": modules,
    }


# ─── Statistiques détaillées ─────────────────────────────────────
async def get_stats(
    db: AsyncSession, child_id: int, parent_id: int, days: int = 30
) -> dict:
    child = await _get_child(db, child_id, parent_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # ── Stats jeux ────────────────────────────────────────────────
    games_progress_result = await db.execute(
        select(GameProgress)
        .options(
            selectinload(GameProgress.game)
            .selectinload(Game.category)
        )
        .where(GameProgress.child_id == child_id)
    )
    games_progress = games_progress_result.scalars().all()

    # Cumul depuis toujours : distinct des chiffres de la période plus bas.
    total_game_sessions_all_time = sum(g.total_plays for g in games_progress)

    # Sur la période : chaque ligne de GameScore est une partie jouée.
    # `total_plays` de GameProgress est un compteur cumulatif, il ne peut
    # pas répondre à « ces 7 derniers jours » — c'est ce qui faisait que
    # le filtre de période ne changeait presque aucun chiffre.
    period_sessions_result = await db.execute(
        select(
            func.count(GameScore.id),
            func.count(func.distinct(GameScore.game_id)),
        ).where(
            GameScore.child_id == child_id,
            GameScore.created_at >= since,
        )
    )
    game_sessions_in_period, games_played_in_period = period_sessions_result.one()

    # Une seule requête groupée par jeu plutôt qu'un SELECT AVG par jeu joué.
    avg_scores_result = await db.execute(
        select(GameScore.game_id, func.avg(GameScore.score))
        .where(
            GameScore.child_id == child_id,
            GameScore.created_at >= since,
        )
        .group_by(GameScore.game_id)
    )
    avg_score_by_game = dict(avg_scores_result.all())

    game_stats = [
        {
            "game_title": gp.game.title,
            "category": gp.game.category.name,
            "total_plays": gp.total_plays,
            "best_score": gp.best_score,
            "current_level": gp.current_level,
            "average_score": round(float(avg_score_by_game.get(gp.game_id) or 0), 1),
        }
        for gp in games_progress
    ]

    # ── Stats histoires ───────────────────────────────────────────
    stories_progress_result = await db.execute(
        select(StoryProgress)
        .options(selectinload(StoryProgress.story))
        .where(StoryProgress.child_id == child_id)
    )
    stories_progress = stories_progress_result.scalars().all()

    story_stats = [
        {
            "story_title": sp.story.title,
            "category": sp.story.category,
            "read_count": sp.read_count,
            "is_completed": sp.is_completed,
            "last_page": sp.last_page,
            "total_pages": sp.story.total_pages,
        }
        for sp in stories_progress
    ]

    # ── Stats communication ───────────────────────────────────────
    sentences_result = await db.execute(
        select(func.count(SentenceHistory.id))
        .where(
            SentenceHistory.child_id == child_id,
            SentenceHistory.created_at >= since,
        )
    )
    sentences_count = sentences_result.scalar() or 0

    favorites_result = await db.execute(
        select(func.count(FavoritePicto.id))
        .where(FavoritePicto.child_id == child_id)
    )
    favorites_count = favorites_result.scalar() or 0

    # Une histoire « lue sur la période » est une progression touchée dans
    # la fenêtre. `updated_at` est nul tant que la ligne n'a pas été
    # modifiée, d'où le repli sur `created_at`.
    def _touchee_dans_la_periode(progress) -> bool:
        horodatage = progress.updated_at or progress.created_at
        return horodatage is not None and horodatage >= since

    stories_in_period = [sp for sp in stories_progress if _touchee_dans_la_periode(sp)]

    return {
        "child_id": child_id,
        "period_days": days,
        # ── Sur la période choisie ────────────────────────────────
        "games_played": games_played_in_period,
        "total_game_sessions": game_sessions_in_period,
        "stories_started": len(stories_in_period),
        "stories_completed": sum(1 for sp in stories_in_period if sp.is_completed),
        "sentences_built": sentences_count,
        # ── Cumuls depuis le début, et préférences actuelles ───────
        # Présentés à part : mélangés aux chiffres de période, ils
        # donnaient l'impression que le filtre ne servait à rien.
        "all_time_game_sessions": total_game_sessions_all_time,
        "all_time_games_played": len(games_progress),
        "all_time_stories_started": len(stories_progress),
        "all_time_stories_completed": sum(
            1 for sp in stories_progress if sp.is_completed
        ),
        "favorite_pictos": favorites_count,
        # ── Détail par activité (cumul) ───────────────────────────
        "game_stats": game_stats,
        "story_stats": story_stats,
    }


# ─── Rapport complet exportable ──────────────────────────────────
async def generate_report(
    db: AsyncSession, child_id: int, parent_id: int, days: int = 30
) -> dict:
    child = await _get_child(db, child_id, parent_id)

    # Agréger toutes les données
    progress = await get_progress(db, child_id, parent_id)
    stats = await get_stats(db, child_id, parent_id, days)

    # Générer les recommandations automatiques
    recommendations = _generate_recommendations(stats)

    # Résumé global
    summary = _generate_summary(child.first_name, progress)

    return {
        "child_id": child_id,
        "child_name": child.first_name,
        "generated_at": str(datetime.now(timezone.utc)),
        "period_days": days,
        "summary": summary,
        "progress": progress,
        "stats": stats,
        "recommendations": recommendations,
    }


def _generate_summary(name: str, progress: dict) -> str:
    rate = progress["global_completion_rate"]

    if rate >= 80:
        progress_text = f"{name} progresse très bien dans l'ensemble des activités"
    elif rate >= 50:
        progress_text = f"{name} progresse régulièrement dans les activités"
    else:
        progress_text = f"{name} commence à explorer les activités"

    return f"{progress_text} ({rate}% de complétion)."


def _generate_recommendations(stats: dict) -> list:
    """Suggestions fondées sur l'activité **de la période choisie**.

    Les chiffres lus ici décrivent la fenêtre demandée : les phrases le
    disent, pour qu'une suggestion ne paraisse pas contredire un cumul
    affiché ailleurs (« 30 sessions » depuis le début, mais aucune ces
    sept derniers jours).
    """
    recommendations = []
    jours = stats.get("period_days", 30)

    # Recommandation jeux
    if stats["total_game_sessions"] < 5:
        recommendations.append(
            f"Sur les {jours} derniers jours, peu de parties ont été jouées. "
            "Proposer les jeux éducatifs pour développer les capacités "
            "cognitives."
        )

    # Recommandation histoires
    if stats["stories_completed"] == 0 and stats["stories_started"] > 0:
        recommendations.append(
            f"Des histoires ont été ouvertes ces {jours} derniers jours sans "
            "être terminées. Accompagner l'enfant jusqu'au bout renforce les "
            "apprentissages sociaux."
        )

    # Recommandation communication
    if stats["sentences_built"] == 0:
        recommendations.append(
            f"Aucune phrase composée sur les {jours} derniers jours. Explorer "
            "le module de communication par pictogrammes pour développer "
            "l'expression de l'enfant."
        )

    if not recommendations:
        recommendations.append(
            f"Activité régulière sur tous les modules ces "
            f"{jours} derniers jours. Continuer ainsi."
        )

    return recommendations

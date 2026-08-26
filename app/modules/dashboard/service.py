from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from app.modules.children.models import Child
from app.modules.emotions.models import Emotion, EmotionRecord
from app.modules.games.models import Game, GameScore, GameProgress
from app.modules.routines.models import Routine, RoutineSession
from app.modules.stories.models import Story, StoryProgress
from app.modules.communication.models import SentenceHistory, FavoritePicto

# Émotions et Communication n'ont pas de "total" fini à atteindre (contrairement
# aux routines/jeux/histoires) : leur taux de progression reflète la régularité
# d'usage sur cette fenêtre plutôt qu'un volume figé à 100% dès le 1er usage.
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

    # ── Routines ──────────────────────────────────────────────────
    # Un seul aller-retour : total, complétées et dernière session en une
    # requête agrégée plutôt que trois SELECT séparés.
    routine_agg_result = await db.execute(
        select(
            func.count(RoutineSession.id),
            func.count(RoutineSession.id).filter(RoutineSession.is_completed == True),
            func.max(RoutineSession.created_at),
        )
        .join(Routine)
        .where(Routine.child_id == child_id)
    )
    total_sessions, completed_sessions, last_session = routine_agg_result.one()
    total_sessions = total_sessions or 0
    completed_sessions = completed_sessions or 0

    routine_rate = round(
        (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 1
    )
    modules.append({
        "module_name": "Routines",
        "total_activities": total_sessions,
        "completed_activities": completed_sessions,
        "completion_rate": routine_rate,
        "last_activity": str(last_session) if last_session else None,
    })

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

    # ── Emotions ──────────────────────────────────────────────────
    # Pas de "total" à atteindre ici : le taux mesure la régularité
    # (jours avec au moins un enregistrement) sur les 30 derniers jours,
    # pas juste "au moins un enregistrement un jour = 100% pour toujours".
    engagement_since = datetime.now(timezone.utc) - timedelta(
        days=PROGRESS_ENGAGEMENT_WINDOW_DAYS
    )

    emotion_agg_result = await db.execute(
        select(
            func.max(EmotionRecord.recorded_at),
            func.count(
                func.distinct(func.date(EmotionRecord.recorded_at))
            ).filter(EmotionRecord.recorded_at >= engagement_since),
        )
        .where(EmotionRecord.child_id == child_id)
    )
    last_emotion, active_emotion_days = emotion_agg_result.one()
    active_emotion_days = active_emotion_days or 0

    modules.append({
        "module_name": "Émotions",
        "total_activities": PROGRESS_ENGAGEMENT_WINDOW_DAYS,
        "completed_activities": active_emotion_days,
        "completion_rate": round(
            active_emotion_days / PROGRESS_ENGAGEMENT_WINDOW_DAYS * 100, 1
        ),
        "last_activity": str(last_emotion) if last_emotion else None,
    })

    # ── Communication ─────────────────────────────────────────────
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

    total_game_sessions = sum(g.total_plays for g in games_progress)

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

    # ── Stats routines ────────────────────────────────────────────
    routines_result = await db.execute(
        select(Routine)
        .options(selectinload(Routine.sessions))
        .where(Routine.child_id == child_id)
    )
    routines = routines_result.scalars().all()

    routine_stats = []
    for r in routines:
        total = len(r.sessions)
        completed = sum(1 for s in r.sessions if s.is_completed)
        routine_stats.append({
            "routine_title": r.title,
            "type": r.type,
            "total_sessions": total,
            "completed_sessions": completed,
            "completion_rate": round(
                (completed / total * 100) if total > 0 else 0, 1
            ),
        })

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

    return {
        "child_id": child_id,
        "period_days": days,
        "games_played": len(games_progress),
        "total_game_sessions": total_game_sessions,
        "game_stats": game_stats,
        "routines_total": len(routines),
        "routines_completed": sum(
            1 for r in routine_stats if r["completion_rate"] >= 80
        ),
        "routine_stats": routine_stats,
        "stories_started": len(stories_progress),
        "stories_completed": sum(1 for s in stories_progress if s.is_completed),
        "story_stats": story_stats,
        "sentences_built": sentences_count,
        "favorite_pictos": favorites_count,
    }


# ─── Tendances émotionnelles ─────────────────────────────────────
async def get_emotion_trends(
    db: AsyncSession, child_id: int, parent_id: int, days: int = 30
) -> dict:
    await _get_child(db, child_id, parent_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Compter par émotion
    result = await db.execute(
        select(
            Emotion.name,
            Emotion.color,
            Emotion.is_positive,
            func.count(EmotionRecord.id).label("count")
        )
        .join(EmotionRecord, EmotionRecord.emotion_id == Emotion.id)
        .where(
            EmotionRecord.child_id == child_id,
            EmotionRecord.recorded_at >= since,
        )
        .group_by(Emotion.id, Emotion.name, Emotion.color, Emotion.is_positive)
        .order_by(func.count(EmotionRecord.id).desc())
    )
    rows = result.all()

    total = sum(r.count for r in rows)
    positive_count = sum(r.count for r in rows if r.is_positive)
    positive_rate = round(
        (positive_count / total * 100) if total > 0 else 0, 1
    )

    trends = [
        {
            "emotion_name": r.name,
            "color": r.color,
            "count": r.count,
            "percentage": round((r.count / total * 100), 1) if total > 0 else 0,
        }
        for r in rows
    ]

    # Historique récent (30 derniers enregistrements)
    history_result = await db.execute(
        select(EmotionRecord, Emotion)
        .join(Emotion, EmotionRecord.emotion_id == Emotion.id)
        .where(
            EmotionRecord.child_id == child_id,
            EmotionRecord.recorded_at >= since,
        )
        .order_by(
            EmotionRecord.recorded_at.desc(),
            EmotionRecord.id.desc(),
        )
        .limit(30)
    )
    history_rows = history_result.all()

    recent_history = [
        {
            "date": str(row.EmotionRecord.recorded_at),
            "emotion_name": row.Emotion.name,
            "color": row.Emotion.color,
            "context": (
                row.EmotionRecord.context_key
                or row.EmotionRecord.context
            ),
        }
        for row in history_rows
    ]

    return {
        "child_id": child_id,
        "period_days": days,
        "total_records": total,
        "most_frequent_emotion": trends[0]["emotion_name"] if trends else None,
        "positive_rate": positive_rate,
        "trends": trends,
        "recent_history": recent_history,
    }


# ─── Rapport complet exportable ──────────────────────────────────
async def generate_report(
    db: AsyncSession, child_id: int, parent_id: int, days: int = 30
) -> dict:
    child = await _get_child(db, child_id, parent_id)

    # Agréger toutes les données
    progress = await get_progress(db, child_id, parent_id)
    stats = await get_stats(db, child_id, parent_id, days)
    emotion_trends = await get_emotion_trends(db, child_id, parent_id, days)

    # Générer les recommandations automatiques
    recommendations = _generate_recommendations(
        progress, stats, emotion_trends
    )

    # Résumé global
    summary = _generate_summary(child.first_name, progress, emotion_trends)

    return {
        "child_id": child_id,
        "child_name": child.first_name,
        "child_age": child.age,
        "generated_at": str(datetime.now(timezone.utc)),
        "period_days": days,
        "summary": summary,
        "progress": progress,
        "stats": stats,
        "emotion_trends": emotion_trends,
        "recommendations": recommendations,
    }


def _generate_summary(
    name: str, progress: dict, emotion_trends: dict
) -> str:
    rate = progress["global_completion_rate"]
    positive_rate = emotion_trends["positive_rate"]
    most_frequent = emotion_trends.get("most_frequent_emotion", "calme")

    if rate >= 80:
        progress_text = f"{name} progresse très bien dans l'ensemble des activités"
    elif rate >= 50:
        progress_text = f"{name} progresse régulièrement dans les activités"
    else:
        progress_text = f"{name} commence à explorer les activités"

    if positive_rate >= 70:
        emotion_text = f"et exprime majoritairement des émotions positives"
    elif positive_rate >= 40:
        emotion_text = f"avec un équilibre émotionnel en développement"
    else:
        emotion_text = f"avec un accompagnement émotionnel recommandé"

    return (
        f"{progress_text} ({rate}% de complétion) {emotion_text}. "
        f"L'émotion la plus fréquente est : {most_frequent}."
    )


def _generate_recommendations(
    progress: dict, stats: dict, emotion_trends: dict
) -> list:
    recommendations = []

    # Recommandation routines
    routine_module = next(
        (m for m in progress["modules"] if m["module_name"] == "Routines"),
        None
    )
    if routine_module and routine_module["completion_rate"] < 50:
        recommendations.append(
            "Encourager la pratique quotidienne des routines visuelles "
            "pour renforcer les repères de l'enfant."
        )

    # Recommandation émotions
    if emotion_trends["positive_rate"] < 40:
        recommendations.append(
            "Les émotions difficiles sont fréquentes. "
            "Utiliser régulièrement les activités apaisantes proposées par l'application."
        )

    # Recommandation jeux
    if stats["total_game_sessions"] < 5:
        recommendations.append(
            "Encourager l'enfant à explorer les jeux éducatifs "
            "pour développer ses capacités cognitives."
        )

    # Recommandation histoires
    if stats["stories_completed"] == 0 and stats["stories_started"] > 0:
        recommendations.append(
            "Accompagner l'enfant pour terminer les histoires commencées "
            "afin de renforcer les apprentissages sociaux."
        )

    # Recommandation communication
    if stats["sentences_built"] == 0:
        recommendations.append(
            "Explorer le module de communication par pictogrammes "
            "pour développer l'expression de l'enfant."
        )

    if not recommendations:
        recommendations.append(
            f"L'enfant progresse bien sur tous les modules. "
            "Continuer à maintenir une pratique régulière et bienveillante."
        )

    return recommendations

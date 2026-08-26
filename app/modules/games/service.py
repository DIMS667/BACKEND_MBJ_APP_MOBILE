import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.core.cache import cached
from app.modules.children.models import Child
from .models import GameCategory, Game, GameScore, GameProgress
from .schemas import GameScoreCreate
from .content_catalog import build_game_content
from .mastery import (
    REQUIRED_INDEPENDENT_SUCCESSES,
    MasteryState,
    SessionMetrics,
    evaluate_mastery,
    learning_status,
)


# ─── Messages bienveillants (CDC : jamais de sanction) ───────────
SUCCESS_MESSAGES = [
    "Super travail ! Tu es fantastique ! 🌟",
    "Bravo ! Tu progresses vraiment bien ! ⭐",
    "Excellent ! Continue comme ça ! 🎉",
    "Wow, tu es incroyable ! 💪",
    "C'est parfait ! Tu t'améliores chaque jour ! 🌈",
    "Tu es une vraie star ! 🏆",
    "Magnifique ! Tu es très doué(e) ! 🎊",
]

ENCOURAGEMENT_MESSAGES = [
    "Tu as essayé avec courage. On continue doucement ! 🌟",
    "Bravo d'avoir participé. Chaque essai aide à apprendre ! ⭐",
    "Tu avances à ton rythme, et c'est très bien. 🌈",
]

LEVEL_UP_MESSAGES = [
    "Fantastique ! Tu passes au niveau suivant ! 🚀🌟",
    "Incroyable ! Tu es prêt(e) pour de nouveaux défis ! 🎯✨",
    "Bravo champion(ne) ! Un nouveau niveau t'attend ! 🏆🎉",
]

REWARD_ANIMATIONS = [
    "stars_burst",      # étoiles douces
    "confetti_soft",    # confettis légers
    "rainbow_appear",   # arc-en-ciel
    "hearts_float",     # cœurs flottants
    "flowers_bloom",    # fleurs qui s'ouvrent
]

# ─── Vérifier ownership ──────────────────────────────────────────
async def _check_child_ownership(
    db: AsyncSession, child_id: int, parent_id: int
) -> None:
    result = await db.execute(select(Child).where(Child.id == child_id))
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


# ─── Catégories ──────────────────────────────────────────────────
# Catalogue statique (aucune route ne le modifie) : mis en cache pour éviter
# un aller-retour DB à chaque appel de l'écran "Mes jeux".
async def get_categories(db: AsyncSession) -> list:
    async def _load():
        result = await db.execute(
            select(GameCategory).order_by(GameCategory.order)
        )
        return list(result.scalars().all())
    return await cached("games:categories", _load)


# ─── Liste des jeux ──────────────────────────────────────────────
async def get_all_games(db: AsyncSession) -> list:
    async def _load():
        result = await db.execute(
            select(Game)
            .options(selectinload(Game.category))
            .order_by(Game.category_id, Game.id)
        )
        return list(result.scalars().all())
    return await cached("games:all", _load)


async def get_games_by_category(
    db: AsyncSession, category_id: int
) -> list:
    async def _load():
        result = await db.execute(
            select(Game)
            .options(selectinload(Game.category))
            .where(Game.category_id == category_id)
            .order_by(Game.id)
        )
        return list(result.scalars().all())
    return await cached(f"games:by_category:{category_id}", _load)


async def get_game_by_id(db: AsyncSession, game_id: int) -> Game:
    result = await db.execute(
        select(Game)
        .options(selectinload(Game.category))
        .where(Game.id == game_id)
    )
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jeu introuvable."
        )
    return game


async def get_game_content(
    db: AsyncSession,
    game_id: int,
    level: int,
    challenge_rank: int | None = None,
) -> dict:
    game = await get_game_by_id(db, game_id)
    return build_game_content(game, level, challenge_rank)


# ─── Soumettre un score ──────────────────────────────────────────
async def submit_score(
    db: AsyncSession,
    game_id: int,
    data: GameScoreCreate,
    parent_id: int,
) -> dict:
    from app.websocket.manager import manager  # import ici pour éviter circular import
    
    await _check_child_ownership(db, data.child_id, parent_id)

    game = await get_game_by_id(db, game_id)
    if data.level < game.min_level or data.level > game.max_level:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Niveau invalide pour ce jeu.",
        )

    # The row lock prevents two simultaneous submissions from validating the
    # same level independently.
    prog_result = await db.execute(
        select(GameProgress).where(
            GameProgress.game_id == game_id,
            GameProgress.child_id == data.child_id,
        ).with_for_update()
    )
    progress = prog_result.scalar_one_or_none()

    if not progress:
        progress = GameProgress(
            game_id=game_id,
            child_id=data.child_id,
            current_level=1,
            best_score=0,
            total_plays=0,
            consecutive_successes=0,
            mastery_percent=0,
            independent_streak=0,
            struggle_streak=0,
            is_mastered=False,
        )
        db.add(progress)
        await db.flush()

    if data.session_id:
        existing_result = await db.execute(
            select(GameScore).where(
                GameScore.game_id == game_id,
                GameScore.child_id == data.child_id,
                GameScore.session_id == data.session_id,
            )
        )
        existing_score = existing_result.scalar_one_or_none()
        if existing_score:
            return _score_result(
                score_record=existing_score,
                progress=progress,
                message="Cette partie est déjà enregistrée.",
            )

    decision = evaluate_mastery(
        MasteryState(
            current_level=progress.current_level,
            mastery_percent=progress.mastery_percent,
            independent_streak=progress.independent_streak,
            struggle_streak=progress.struggle_streak,
            total_plays=progress.total_plays,
            is_mastered=progress.is_mastered,
        ),
        SessionMetrics(
            played_level=data.level,
            score=data.score,
            correct_answers=data.correct_answers,
            total_questions=data.total_questions,
            mistake_count=data.mistake_count,
            hints_used=data.hints_used,
            completed=data.completed,
        ),
        min_level=game.min_level,
        max_level=game.max_level,
    )

    score_record = GameScore(
        game_id=game_id,
        child_id=data.child_id,
        score=data.score,
        level=data.level,
        duration_seconds=data.duration_seconds,
        session_id=data.session_id,
        correct_answers=data.correct_answers,
        total_questions=data.total_questions,
        mistake_count=data.mistake_count,
        hints_used=data.hints_used,
        completed=data.completed,
        independent_success=decision.independent_success,
        evidence_score=decision.evidence_score,
    )
    db.add(score_record)

    progress.total_plays += 1
    progress.best_score = max(progress.best_score, data.score)
    progress.current_level = decision.current_level
    progress.mastery_percent = decision.mastery_percent
    progress.independent_streak = decision.independent_streak
    progress.struggle_streak = decision.struggle_streak
    progress.is_mastered = decision.is_mastered
    # Kept synchronized for backward compatibility with existing dashboards.
    progress.consecutive_successes = decision.independent_streak

    await db.flush()

    message = _learning_message(decision)
    reward_animation = random.choice(REWARD_ANIMATIONS)
    result_data = _score_result(
        score_record=score_record,
        progress=progress,
        message=message,
        reward_animation=reward_animation,
        independent_success=decision.independent_success,
        assisted_success=decision.assisted_success,
        level_up=decision.level_up,
        level_down=decision.level_down,
        evidence_score=decision.evidence_score,
        learning_status_value=decision.learning_status,
    )

    # ── Événement WebSocket ───────────────────────────────────────
    await manager.send_to_child(data.child_id, {
        "type": "game_score_submitted",
        "data": {
            "child_id": data.child_id,
            "game_id": game_id,
            "game_title": game.title,
            "score": data.score,
            "best_score": progress.best_score,
            "current_level": progress.current_level,
            "level_up": decision.level_up,
            "level_down": decision.level_down,
            "independent_success": decision.independent_success,
            "mastery_percent": progress.mastery_percent,
            "message": message,
        }
    })

    return result_data


def _learning_message(decision) -> str:
    if decision.level_up:
        return random.choice(LEVEL_UP_MESSAGES)
    if decision.is_mastered and decision.independent_success:
        return "Tu maîtrises ce défi sans aide. Bravo pour ton travail ! 🏆"
    if decision.independent_success:
        remaining = max(
            REQUIRED_INDEPENDENT_SUCCESSES - decision.independent_streak,
            0,
        )
        return (
            "Mission réussie sans aide ! "
            f"Encore {remaining} réussite{'s' if remaining > 1 else ''} "
            "pour valider ce niveau."
        )
    if decision.assisted_success:
        return "Tu as compris avec un indice. Rejoue pour réussir sans aide."
    if decision.level_down:
        return "On consolide les bases avant de reprendre le défi suivant."
    if decision.evidence_score < 45:
        return random.choice(ENCOURAGEMENT_MESSAGES)
    return "Tu apprends. Rejoue cette mission pour la réussir avec plus de précision."


def _score_result(
    *,
    score_record: GameScore,
    progress: GameProgress,
    message: str,
    reward_animation: str = "stars_burst",
    independent_success: bool = False,
    assisted_success: bool = False,
    level_up: bool = False,
    level_down: bool = False,
    evidence_score: int | None = None,
    learning_status_value: str | None = None,
) -> dict:
    return {
        "score_id": score_record.id,
        "game_id": score_record.game_id,
        "child_id": score_record.child_id,
        "score": score_record.score,
        "level": score_record.level,
        "best_score": progress.best_score,
        "current_level": progress.current_level,
        "level_up": level_up,
        "level_down": level_down,
        "independent_success": independent_success,
        "assisted_success": assisted_success,
        "mastery_percent": progress.mastery_percent,
        "independent_streak": progress.independent_streak,
        "required_independent_successes": REQUIRED_INDEPENDENT_SUCCESSES,
        "evidence_score": (
            score_record.evidence_score
            if evidence_score is None
            else evidence_score
        ),
        "learning_status": learning_status_value or learning_status(
            progress.mastery_percent,
            progress.independent_streak,
            progress.is_mastered,
        ),
        "message": message,
        "reward_animation": reward_animation,
    }


# ─── Progression d'un enfant ─────────────────────────────────────
async def get_child_progress(
    db: AsyncSession, child_id: int, parent_id: int
) -> dict:
    await _check_child_ownership(db, child_id, parent_id)

    result = await db.execute(
        select(GameProgress)
        .options(
            selectinload(GameProgress.game).selectinload(Game.category)
        )
        .where(GameProgress.child_id == child_id)
        .order_by(GameProgress.game_id)
    )
    progress_list = list(result.scalars().all())

    total_plays = sum(p.total_plays for p in progress_list)

    return {
        "child_id": child_id,
        "total_games_played": len(progress_list),
        "total_plays": total_plays,
        "progress": progress_list,
    }


# ─── Historique des scores d'un enfant pour un jeu ───────────────
async def get_game_scores(
    db: AsyncSession,
    game_id: int,
    child_id: int,
    parent_id: int,
    limit: int = 10,
) -> list:
    await _check_child_ownership(db, child_id, parent_id)

    result = await db.execute(
        select(GameScore)
        .where(
            GameScore.game_id == game_id,
            GameScore.child_id == child_id,
        )
        .order_by(GameScore.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

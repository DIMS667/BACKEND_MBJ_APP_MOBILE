import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.modules.children.models import Child
from .models import GameCategory, Game, GameScore, GameProgress
from .schemas import GameScoreCreate


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

# Nombre de succès consécutifs pour monter de niveau (CDC : adaptation invisible)
LEVEL_UP_THRESHOLD = 3


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
async def get_categories(db: AsyncSession) -> list:
    result = await db.execute(
        select(GameCategory).order_by(GameCategory.order)
    )
    return list(result.scalars().all())


# ─── Liste des jeux ──────────────────────────────────────────────
async def get_all_games(db: AsyncSession) -> list:
    result = await db.execute(
        select(Game)
        .options(selectinload(Game.category))
        .order_by(Game.category_id, Game.id)
    )
    return list(result.scalars().all())


async def get_games_by_category(
    db: AsyncSession, category_id: int
) -> list:
    result = await db.execute(
        select(Game)
        .options(selectinload(Game.category))
        .where(Game.category_id == category_id)
        .order_by(Game.id)
    )
    return list(result.scalars().all())


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


# ─── Soumettre un score ──────────────────────────────────────────
async def submit_score(
    db: AsyncSession,
    game_id: int,
    data: GameScoreCreate,
    parent_id: int,
) -> dict:
    from app.websocket.manager import manager  # import ici pour éviter circular import
    
    await _check_child_ownership(db, data.child_id, parent_id)

    # Vérifier que le jeu existe
    game = await get_game_by_id(db, game_id)

    # Enregistrer le score
    score_record = GameScore(
        game_id=game_id,
        child_id=data.child_id,
        score=data.score,
        level=data.level,
        duration_seconds=data.duration_seconds,
    )
    db.add(score_record)
    await db.flush()

    # Récupérer ou créer la progression
    prog_result = await db.execute(
        select(GameProgress).where(
            GameProgress.game_id == game_id,
            GameProgress.child_id == data.child_id,
        )
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
        )
        db.add(progress)
        await db.flush()

    # Mettre à jour la progression
    progress.total_plays += 1
    level_up = False

    # Mettre à jour le meilleur score
    if data.score > progress.best_score:
        progress.best_score = data.score

    # Logique de progression de niveau (CDC : adaptation invisible)
    # Un score > 70% est considéré comme un succès
    success_threshold = 70
    is_success = data.score >= success_threshold

    if is_success:
        progress.consecutive_successes += 1
        # Monter de niveau après LEVEL_UP_THRESHOLD succès consécutifs
        if (
            progress.consecutive_successes >= LEVEL_UP_THRESHOLD
            and progress.current_level < game.max_level
        ):
            progress.current_level += 1
            progress.consecutive_successes = 0
            level_up = True
    else:
        # Échec discret : on remet le compteur à 0 mais on ne descend PAS
        # CDC : jamais de sentiment d'échec
        progress.consecutive_successes = 0

    await db.flush()

    # Choisir message et animation
    if level_up:
        message = random.choice(LEVEL_UP_MESSAGES)
    else:
        message = random.choice(SUCCESS_MESSAGES)

    reward_animation = random.choice(REWARD_ANIMATIONS)

    result_data = {
        "score_id": score_record.id,
        "game_id": game_id,
        "child_id": data.child_id,
        "score": data.score,
        "level": data.level,
        "best_score": progress.best_score,
        "current_level": progress.current_level,
        "level_up": level_up,
        "message": message,
        "reward_animation": reward_animation,
    }

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
            "level_up": level_up,
            "message": message,
        }
    })

    return result_data


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
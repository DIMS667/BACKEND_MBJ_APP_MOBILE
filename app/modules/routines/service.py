from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime
from app.modules.children.models import Child
from .models import Routine, RoutineStep, RoutineSession
from .schemas import RoutineCreate, RoutineUpdate


# ─── Messages bienveillants (CDC : jamais de sanction) ───────────
STEP_MESSAGES = [
    "Super ! Tu as fait une étape ! 🌟",
    "Bravo, continue comme ça ! ⭐",
    "Excellent travail ! Tu es fantastique ! 🎉",
    "Wow, tu avances bien ! 💪",
    "C'est parfait ! Tu es incroyable ! 🌈",
]

ROUTINE_COMPLETE_MESSAGE = "Félicitations ! Tu as terminé toute la routine ! 🏆🎉"


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


async def _get_routine_owned_by(
    db: AsyncSession, routine_id: int, parent_id: int
) -> Routine:
    result = await db.execute(
        select(Routine)
        .options(selectinload(Routine.steps))
        .where(Routine.id == routine_id)
    )
    routine = result.scalar_one_or_none()
    if not routine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routine introuvable."
        )
    # Vérifier ownership via l'enfant
    await _check_child_ownership(db, routine.child_id, parent_id)
    return routine


# ─── Créer une routine ───────────────────────────────────────────
async def create_routine(
    db: AsyncSession, data: RoutineCreate, parent_id: int
) -> Routine:
    await _check_child_ownership(db, data.child_id, parent_id)

    routine = Routine(
        child_id=data.child_id,
        title=data.title,
        icon_url=data.icon_url,
        type=data.type,
    )
    db.add(routine)
    await db.flush()

    # Ajouter les étapes
    for step_data in data.steps:
        step = RoutineStep(
            routine_id=routine.id,
            order=step_data.order,
            title=step_data.title,
            image_url=step_data.image_url,
            audio_url=step_data.audio_url,
        )
        db.add(step)

    await db.flush()
    return await _get_routine_owned_by(db, routine.id, parent_id)


# ─── Lister les routines d'un enfant ────────────────────────────
async def list_routines(
    db: AsyncSession, child_id: int, parent_id: int
) -> list:
    await _check_child_ownership(db, child_id, parent_id)

    result = await db.execute(
        select(Routine)
        .options(selectinload(Routine.steps))
        .where(Routine.child_id == child_id)
        .order_by(Routine.created_at)
    )
    return list(result.scalars().all())


# ─── Détail d'une routine ────────────────────────────────────────
async def get_routine(
    db: AsyncSession, routine_id: int, parent_id: int
) -> Routine:
    return await _get_routine_owned_by(db, routine_id, parent_id)


# ─── Modifier une routine ────────────────────────────────────────
async def update_routine(
    db: AsyncSession, routine_id: int, data: RoutineUpdate, parent_id: int
) -> Routine:
    routine = await _get_routine_owned_by(db, routine_id, parent_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(routine, field, value)
    await db.flush()
    return routine


# ─── Supprimer une routine ───────────────────────────────────────
async def delete_routine(
    db: AsyncSession, routine_id: int, parent_id: int
) -> None:
    routine = await _get_routine_owned_by(db, routine_id, parent_id)
    await db.delete(routine)


# ─── Valider une étape ───────────────────────────────────────────
async def validate_step(
    db: AsyncSession, routine_id: int, step_id: int, parent_id: int
) -> dict:
    from app.websocket.manager import manager  # import ici pour éviter circular import
    
    routine = await _get_routine_owned_by(db, routine_id, parent_id)

    # Trouver l'étape
    result = await db.execute(
        select(RoutineStep).where(
            RoutineStep.id == step_id,
            RoutineStep.routine_id == routine_id,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Étape introuvable."
        )

    # Marquer comme complétée
    step.is_completed = True
    await db.flush()

    # Compter les étapes complétées
    steps_completed = sum(1 for s in routine.steps if s.is_completed or s.id == step_id)
    total_steps = len(routine.steps)
    routine_completed = steps_completed == total_steps

    # Créer ou mettre à jour la session
    session_result = await db.execute(
        select(RoutineSession).where(
            RoutineSession.routine_id == routine_id,
            RoutineSession.is_completed == False,
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        session = RoutineSession(
            routine_id=routine_id,
            started_at=str(datetime.utcnow()),
            total_steps=total_steps,
        )
        db.add(session)

    session.steps_completed = steps_completed

    if routine_completed:
        session.completed_at = str(datetime.utcnow())
        session.is_completed = True
        message = ROUTINE_COMPLETE_MESSAGE
    else:
        import random
        message = random.choice(STEP_MESSAGES)

    await db.flush()

    result_data = {
        "step_id": step_id,
        "is_completed": True,
        "routine_completed": routine_completed,
        "steps_completed": steps_completed,
        "total_steps": total_steps,
        "message": message,
    }

    # ── Événement WebSocket ───────────────────────────────────────
    await manager.send_to_child(routine.child_id, {
        "type": "routine_step_validated",
        "data": {
            "child_id": routine.child_id,
            "routine_id": routine_id,
            "routine_title": routine.title,
            "step_id": step_id,
            "steps_completed": steps_completed,
            "total_steps": total_steps,
            "routine_completed": routine_completed,
            "message": message,
        }
    })

    return result_data


# ─── Réinitialiser une routine ───────────────────────────────────
async def reset_routine(
    db: AsyncSession, routine_id: int, parent_id: int
) -> Routine:
    routine = await _get_routine_owned_by(db, routine_id, parent_id)

    for step in routine.steps:
        step.is_completed = False

    await db.flush()
    return routine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime
from app.modules.children.models import Child
from .models import Routine, RoutineStep, RoutineSession
from .schemas import RoutineCreate, RoutineStepSync, RoutineUpdate


# ─── Messages bienveillants (CDC : jamais de sanction) ───────────
STEP_MESSAGES = [
    "Super ! Tu as fait une étape ! 🌟",
    "Bravo, continue comme ça ! ⭐",
    "Excellent travail ! Tu es fantastique ! 🎉",
    "Wow, tu avances bien ! 💪",
    "C'est parfait ! Tu es incroyable ! 🌈",
]

ROUTINE_COMPLETE_MESSAGE = "Félicitations ! Tu as terminé toute la routine ! 🏆🎉"
STEP_ALREADY_COMPLETED_MESSAGE = "Cette étape est déjà terminée."
PROTECTED_ROUTINE_MESSAGE = "Une routine proposée ne peut pas être modifiée."
PROTECTED_ROUTINE_DELETE_MESSAGE = (
    "Une routine proposée ne peut pas être supprimée."
)
ROUTINE_IN_PROGRESS_MESSAGE = (
    "Recommencez la routine avant de modifier ses étapes."
)
ROUTINE_STEP_LIMIT_MESSAGE = "Une routine ne peut pas dépasser 20 étapes."
ROUTINE_STEP_COLLISION_MESSAGE = (
    "Cet identifiant correspond déjà à une autre étape."
)


def ensure_step_is_current(routine: Routine, step: RoutineStep) -> bool:
    """Return False for an idempotent replay, reject an out-of-order step."""
    if step.is_completed:
        return False
    current_step = next(
        (
            candidate
            for candidate in sorted(routine.steps, key=lambda item: item.order)
            if not candidate.is_completed
        ),
        None,
    )
    if current_step is None or current_step.id != step.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminez d’abord l’étape en cours.",
        )
    return True


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
    db: AsyncSession,
    routine_id: int,
    parent_id: int,
    *,
    lock: bool = False,
) -> Routine:
    if lock:
        child_id_result = await db.execute(
            select(Routine.child_id).where(Routine.id == routine_id)
        )
        child_id = child_id_result.scalar_one_or_none()
        if child_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine introuvable.",
            )
        # Vérifier l'ownership avant de verrouiller une ligne de routine.
        await _check_child_ownership(db, child_id, parent_id)

    statement = (
        select(Routine)
        .options(selectinload(Routine.steps))
        .where(Routine.id == routine_id)
    )
    if lock:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    routine = result.scalar_one_or_none()
    if not routine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routine introuvable."
        )
    if not lock:
        # Le chemin verrouillé a déjà contrôlé l'ownership avant FOR UPDATE.
        await _check_child_ownership(db, routine.child_id, parent_id)
    return routine


def _ensure_routine_is_custom(routine: Routine, *, deleting: bool = False) -> None:
    """Protect proposed routines even if legacy data has an inconsistent flag."""
    if routine.is_default or routine.type != "custom":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                PROTECTED_ROUTINE_DELETE_MESSAGE
                if deleting
                else PROTECTED_ROUTINE_MESSAGE
            ),
        )


# ─── Créer une routine ───────────────────────────────────────────
async def create_routine(
    db: AsyncSession, data: RoutineCreate, parent_id: int
) -> Routine:
    await _check_child_ownership(db, data.child_id, parent_id)

    routine = Routine(
        child_id=data.child_id,
        title=data.title,
        icon_url=data.icon_url,
        type="custom",
        is_default=False,
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
            is_default=False,
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
    routine = await _get_routine_owned_by(
        db,
        routine_id,
        parent_id,
        lock=True,
    )
    _ensure_routine_is_custom(routine)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(routine, field, value)
    await db.flush()
    return routine


# ─── Supprimer une routine ───────────────────────────────────────
async def delete_routine(
    db: AsyncSession, routine_id: int, parent_id: int
) -> None:
    routine = await _get_routine_owned_by(
        db,
        routine_id,
        parent_id,
        lock=True,
    )
    _ensure_routine_is_custom(routine, deleting=True)
    await db.delete(routine)


# ─── Ajouter/synchroniser une étape personnalisée ────────────────
async def sync_custom_step(
    db: AsyncSession,
    routine_id: int,
    data: RoutineStepSync,
    parent_id: int,
) -> RoutineStep:
    routine = await _get_routine_owned_by(
        db,
        routine_id,
        parent_id,
        lock=True,
    )

    existing = next(
        (
            step
            for step in routine.steps
            if step.client_uuid == data.client_uuid
        ),
        None,
    )
    if existing is not None:
        same_payload = (
            not existing.is_default
            and existing.title == data.title
            and existing.image_url == data.image_url
            and existing.audio_url == data.audio_url
        )
        if not same_payload:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ROUTINE_STEP_COLLISION_MESSAGE,
            )
        return existing

    if any(step.is_completed for step in routine.steps):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ROUTINE_IN_PROGRESS_MESSAGE,
        )
    if len(routine.steps) >= 20:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ROUTINE_STEP_LIMIT_MESSAGE,
        )

    next_order = max((step.order for step in routine.steps), default=0) + 1
    step = RoutineStep(
        routine_id=routine.id,
        order=next_order,
        title=data.title,
        image_url=data.image_url,
        audio_url=data.audio_url,
        is_completed=False,
        is_default=False,
        client_uuid=data.client_uuid,
    )
    routine.steps.append(step)
    db.add(step)
    await db.flush()
    return step


# ─── Valider une étape ───────────────────────────────────────────
async def validate_step(
    db: AsyncSession, routine_id: int, step_id: int, parent_id: int
) -> dict:
    from app.websocket.manager import manager  # import ici pour éviter circular import
    
    routine = await _get_routine_owned_by(
        db,
        routine_id,
        parent_id,
        lock=True,
    )

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

    should_validate = ensure_step_is_current(routine, step)
    total_steps = len(routine.steps)
    if not should_validate:
        steps_completed = sum(1 for item in routine.steps if item.is_completed)
        return {
            "step_id": step_id,
            "is_completed": True,
            "routine_completed": total_steps > 0 and steps_completed == total_steps,
            "steps_completed": steps_completed,
            "total_steps": total_steps,
            "message": STEP_ALREADY_COMPLETED_MESSAGE,
        }

    # Marquer comme complétée
    step.is_completed = True
    await db.flush()

    # Compter les étapes complétées
    steps_completed = sum(
        1 for item in routine.steps if item.is_completed or item.id == step_id
    )
    routine_completed = total_steps > 0 and steps_completed == total_steps

    # Créer ou mettre à jour la session
    session_result = await db.execute(
        select(RoutineSession).where(
            RoutineSession.routine_id == routine_id,
            RoutineSession.is_completed.is_(False),
        ).order_by(RoutineSession.id.desc()).limit(1)
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
    routine = await _get_routine_owned_by(
        db,
        routine_id,
        parent_id,
        lock=True,
    )

    for step in routine.steps:
        step.is_completed = False

    session_result = await db.execute(
        select(RoutineSession).where(
            RoutineSession.routine_id == routine_id,
            RoutineSession.is_completed.is_(False),
        )
    )
    for session in session_result.scalars().all():
        await db.delete(session)

    await db.flush()
    return routine

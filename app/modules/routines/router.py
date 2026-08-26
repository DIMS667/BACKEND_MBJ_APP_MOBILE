from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User
from .schemas import (
    RoutineCreate,
    RoutineResponse,
    RoutineStepResponse,
    RoutineStepSync,
    RoutineUpdate,
    ValidateStepResponse,
)
from . import service

router = APIRouter()


# ─── Créer une routine ───────────────────────────────────────────
@router.post("/", response_model=RoutineResponse, status_code=201)
async def create_routine(
    data: RoutineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_routine(db, data, current_user.id)


# ─── Lister les routines d'un enfant ────────────────────────────
@router.get("/{child_id}", response_model=List[RoutineResponse])
async def list_routines(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.list_routines(db, child_id, current_user.id)


# ─── Détail d'une routine ────────────────────────────────────────
@router.get("/{routine_id}/detail", response_model=RoutineResponse)
async def get_routine(
    routine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_routine(db, routine_id, current_user.id)


# ─── Modifier une routine ────────────────────────────────────────
@router.put("/{routine_id}", response_model=RoutineResponse)
async def update_routine(
    routine_id: int,
    data: RoutineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.update_routine(db, routine_id, data, current_user.id)


# ─── Supprimer une routine ───────────────────────────────────────
@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routine(
    routine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_routine(db, routine_id, current_user.id)


# ─── Ajouter/synchroniser une étape personnalisée ────────────────
@router.put(
    "/{routine_id}/steps/custom/sync",
    response_model=RoutineStepResponse,
)
async def sync_custom_step(
    routine_id: int,
    data: RoutineStepSync,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.sync_custom_step(
        db,
        routine_id,
        data,
        current_user.id,
    )


# ─── Valider une étape ───────────────────────────────────────────
@router.post(
    "/{routine_id}/steps/{step_id}/validate",
    response_model=ValidateStepResponse,
)
async def validate_step(
    routine_id: int,
    step_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.validate_step(db, routine_id, step_id, current_user.id)


# ─── Réinitialiser une routine ───────────────────────────────────
@router.post("/{routine_id}/reset", response_model=RoutineResponse)
async def reset_routine(
    routine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.reset_routine(db, routine_id, current_user.id)

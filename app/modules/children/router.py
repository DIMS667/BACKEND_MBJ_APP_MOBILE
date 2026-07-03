from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.dependencies import get_db, get_current_user
from app.modules.auth.models import User
from .schemas import (
    ChildCreate, ChildUpdate, ChildResponse,
    SensoryProfileUpdate, SensoryProfileResponse,
    ChildPreferencesUpdate, ChildPreferencesResponse,
)
from . import service

router = APIRouter()


@router.post("/", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
async def create_child(
    data: ChildCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_child(db, data, current_user.id)


@router.get("/", response_model=List[ChildResponse])
async def list_children(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.list_children(db, current_user.id)


@router.get("/{child_id}", response_model=ChildResponse)
async def get_child(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_child(db, child_id, current_user.id)


@router.put("/{child_id}", response_model=ChildResponse)
async def update_child(
    child_id: int,
    data: ChildUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.update_child(db, child_id, data, current_user.id)


@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_child(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_child(db, child_id, current_user.id)


@router.put("/{child_id}/sensory-profile", response_model=SensoryProfileResponse)
async def update_sensory_profile(
    child_id: int,
    data: SensoryProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.update_sensory_profile(db, child_id, data, current_user.id)


@router.put("/{child_id}/preferences", response_model=ChildPreferencesResponse)
async def update_preferences(
    child_id: int,
    data: ChildPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.update_preferences(db, child_id, data, current_user.id)


@router.delete("/{child_id}/data", status_code=status.HTTP_200_OK)
async def delete_child_data(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RGPD — Efface toutes les données comportementales de l'enfant.

    Conserve le profil, les préférences et le profil sensoriel.
    Supprime : émotions, scores, progression jeux, pictos favoris,
    historique phrases, progression histoires, sessions routines.
    """
    return await service.delete_child_data(db, child_id, current_user.id)
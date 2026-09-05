from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from .models import Child, SensoryProfile, ChildPreferences
from .schemas import (
    ChildCreate, ChildUpdate,
    SensoryProfileUpdate, ChildPreferencesUpdate,
)


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

async def _get_child_owned_by(
    db: AsyncSession, child_id: int, parent_id: int
) -> Child:
    """Récupère un enfant en vérifiant qu'il appartient bien au parent connecté."""
    result = await db.execute(
        select(Child)
        .options(
            selectinload(Child.sensory_profile),
            selectinload(Child.preferences),
        )
        .where(Child.id == child_id)
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enfant introuvable.",
        )
    if child.parent_id != parent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce profil enfant.",
        )
    return child


# ─────────────────────────────────────────────────────────────────
# CRUD ENFANT
# ─────────────────────────────────────────────────────────────────

MAX_CHILDREN_PER_PARENT = 2


async def create_child(
    db: AsyncSession, data: ChildCreate, parent_id: int
) -> Child:
    existing_count = await db.scalar(
        select(func.count()).select_from(Child).where(Child.parent_id == parent_id)
    )
    if existing_count >= MAX_CHILDREN_PER_PARENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limite de {MAX_CHILDREN_PER_PARENT} profils enfant atteinte.",
        )

    child = Child(
        parent_id=parent_id,
        first_name=data.first_name,
        level=1,
    )
    db.add(child)
    await db.flush()

    # Créer automatiquement profil sensoriel et préférences par défaut
    sensory = SensoryProfile(child_id=child.id)
    prefs = ChildPreferences(
        child_id=child.id,
        favorite_activities=[],
        color_theme="blue",
    )
    db.add_all([sensory, prefs])
    await db.flush()

    # Re-fetch avec toutes les relations chargées
    return await _get_child_owned_by(db, child.id, parent_id)


async def get_child(
    db: AsyncSession, child_id: int, parent_id: int
) -> Child:
    return await _get_child_owned_by(db, child_id, parent_id)


async def list_children(
    db: AsyncSession, parent_id: int
) -> list[Child]:
    result = await db.execute(
        select(Child)
        .options(
            selectinload(Child.sensory_profile),
            selectinload(Child.preferences),
        )
        .where(Child.parent_id == parent_id)
        .order_by(Child.created_at)
    )
    return list(result.scalars().all())


async def update_child(
    db: AsyncSession, child_id: int, data: ChildUpdate, parent_id: int
) -> Child:
    child = await _get_child_owned_by(db, child_id, parent_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(child, field, value)
    await db.flush()
    return child


async def delete_child(
    db: AsyncSession, child_id: int, parent_id: int
) -> None:
    child = await _get_child_owned_by(db, child_id, parent_id)
    await db.delete(child)


# ─────────────────────────────────────────────────────────────────
# PROFIL SENSORIEL
# ─────────────────────────────────────────────────────────────────

async def update_sensory_profile(
    db: AsyncSession,
    child_id: int,
    data: SensoryProfileUpdate,
    parent_id: int,
) -> SensoryProfile:
    child = await _get_child_owned_by(db, child_id, parent_id)
    profile = child.sensory_profile

    if not profile:
        profile = SensoryProfile(child_id=child.id)
        db.add(profile)

    for field, value in data.model_dump().items():
        setattr(profile, field, value)

    await db.flush()
    return profile


# ─────────────────────────────────────────────────────────────────
# PRÉFÉRENCES
# ─────────────────────────────────────────────────────────────────

async def update_preferences(
    db: AsyncSession,
    child_id: int,
    data: ChildPreferencesUpdate,
    parent_id: int,
) -> ChildPreferences:
    child = await _get_child_owned_by(db, child_id, parent_id)
    prefs = child.preferences

    if not prefs:
        prefs = ChildPreferences(child_id=child.id)
        db.add(prefs)

    for field, value in data.model_dump().items():
        setattr(prefs, field, value)

    await db.flush()
    return prefs


# ─────────────────────────────────────────────────────────────────
# RGPD — SUPPRESSION CASCADE DES DONNÉES COMPORTEMENTALES
# Conserve le profil enfant (préférences, profil sensoriel).
# Efface toutes les données d'activité personnelle.
# ─────────────────────────────────────────────────────────────────

async def delete_child_data(
    db: AsyncSession, child_id: int, parent_id: int
) -> dict:
    """Supprime toutes les données comportementales de l'enfant (RGPD)."""
    await _get_child_owned_by(db, child_id, parent_id)

    # Import local pour éviter les imports circulaires
    from app.modules.games.models import GameScore, GameProgress
    from app.modules.communication.models import FavoritePicto, SentenceHistory
    from app.modules.stories.models import StoryProgress

    # Supprimer les scores de jeux
    await db.execute(
        delete(GameScore).where(GameScore.child_id == child_id)
    )

    # Supprimer la progression de jeux
    await db.execute(
        delete(GameProgress).where(GameProgress.child_id == child_id)
    )

    # Supprimer les pictos favoris
    await db.execute(
        delete(FavoritePicto).where(FavoritePicto.child_id == child_id)
    )

    # Supprimer l'historique de phrases
    await db.execute(
        delete(SentenceHistory).where(SentenceHistory.child_id == child_id)
    )

    # Supprimer la progression des histoires
    await db.execute(
        delete(StoryProgress).where(StoryProgress.child_id == child_id)
    )

    await db.flush()
    return {"deleted": True, "child_id": child_id}

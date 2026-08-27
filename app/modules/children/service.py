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
# ROUTINES PRÉCONFIGURÉES PAR DÉFAUT
# Créées automatiquement à chaque nouvel enfant
# ─────────────────────────────────────────────────────────────────

DEFAULT_ROUTINES = [
    {
        "title": "Routine du matin",
        "type": "morning",
        "icon_url": "https://static.arasaac.org/pictograms/2725/2725_300.png",
        "steps": [
            "Se réveiller",
            "Se laver le visage",
            "Se brosser les dents",
            "S'habiller",
            "Prendre le petit-déjeuner",
            "Préparer son sac",
        ]
    },
    {
        "title": "Routine du soir",
        "type": "evening",
        "icon_url": "https://static.arasaac.org/pictograms/4877/4877_300.png",
        "steps": [
            "Ranger ses affaires",
            "Se laver",
            "Mettre le pyjama",
            "Lire une histoire",
            "Dormir",
        ]
    },
    {
        "title": "Routine école",
        "type": "school",
        "icon_url": "https://static.arasaac.org/pictograms/32446/32446_300.png",
        "steps": [
            "Arriver en classe",
            "Accrocher son manteau",
            "S'asseoir",
            "Sortir ses affaires",
            "Dire bonjour",
        ]
    },
]


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


async def _create_default_routines(db: AsyncSession, child_id: int) -> None:
    """
    Crée les 3 routines préconfigurées pour chaque nouvel enfant.
    Appelée automatiquement lors de create_child().
    """
    # Import ici pour éviter les imports circulaires
    from app.modules.routines.models import Routine, RoutineStep

    for routine_data in DEFAULT_ROUTINES:
        routine = Routine(
            child_id=child_id,
            title=routine_data["title"],
            type=routine_data["type"],
            icon_url=routine_data["icon_url"],
            is_default=True,
        )
        db.add(routine)
        await db.flush()

        for i, step_title in enumerate(routine_data["steps"], start=1):
            db.add(RoutineStep(
                routine_id=routine.id,
                order=i,
                title=step_title,
                is_default=True,
            ))

    await db.flush()


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
        age=data.age,
        photo_url=data.photo_url,
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

    # Créer automatiquement les 3 routines préconfigurées
    await _create_default_routines(db, child.id)

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
    from app.modules.emotions.models import (
        CalmingActivityFeedback,
        EmotionRecord,
    )
    from app.modules.games.models import GameScore, GameProgress
    from app.modules.communication.models import FavoritePicto, SentenceHistory
    from app.modules.stories.models import StoryProgress
    from app.modules.routines.models import Routine, RoutineSession

    # Supprimer les enregistrements d'émotions
    await db.execute(
        delete(CalmingActivityFeedback).where(
            CalmingActivityFeedback.child_id == child_id
        )
    )
    await db.execute(
        delete(EmotionRecord).where(EmotionRecord.child_id == child_id)
    )

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

    # Supprimer les sessions de routines (via les routines de l'enfant)
    routine_ids_result = await db.execute(
        select(Routine.id).where(Routine.child_id == child_id)
    )
    routine_ids = [row[0] for row in routine_ids_result.all()]
    if routine_ids:
        await db.execute(
            delete(RoutineSession).where(
                RoutineSession.routine_id.in_(routine_ids)
            )
        )

    await db.flush()
    return {"deleted": True, "child_id": child_id}

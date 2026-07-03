from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.modules.children.models import Child
from .models import Story, StoryPage, StoryProgress
from .schemas import StoryProgressCreate


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


# ─── Liste des histoires ─────────────────────────────────────────
async def get_all_stories(
    db: AsyncSession,
    category: str = None,
    difficulty: int = None,
) -> list:
    query = select(Story).order_by(Story.difficulty_level, Story.id)
    if category:
        query = query.where(Story.category == category)
    if difficulty:
        query = query.where(Story.difficulty_level == difficulty)
    result = await db.execute(query)
    return list(result.scalars().all())


# ─── Détail d'une histoire avec toutes ses pages ─────────────────
async def get_story_detail(db: AsyncSession, story_id: int) -> Story:
    result = await db.execute(
        select(Story)
        .options(selectinload(Story.pages))
        .where(Story.id == story_id)
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Histoire introuvable."
        )
    return story


# ─── Sauvegarder la progression ──────────────────────────────────
async def save_progress(
    db: AsyncSession,
    story_id: int,
    data: StoryProgressCreate,
    parent_id: int,
) -> StoryProgress:
    await _check_child_ownership(db, data.child_id, parent_id)

    # Vérifier que l'histoire existe
    story_result = await db.execute(
        select(Story).where(Story.id == story_id)
    )
    if not story_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Histoire introuvable."
        )

    # Récupérer ou créer la progression
    result = await db.execute(
        select(StoryProgress).where(
            StoryProgress.story_id == story_id,
            StoryProgress.child_id == data.child_id,
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        progress = StoryProgress(
            story_id=story_id,
            child_id=data.child_id,
            last_page=data.last_page,
            is_completed=data.is_completed,
            read_count=1,
        )
        db.add(progress)
    else:
        progress.last_page = data.last_page
        progress.is_completed = data.is_completed
        # Incrémenter le compteur si l'histoire est terminée
        if data.is_completed:
            progress.read_count += 1

    await db.flush()
    return progress


# ─── Progression d'un enfant ─────────────────────────────────────
async def get_child_progress(
    db: AsyncSession, child_id: int, parent_id: int
) -> dict:
    await _check_child_ownership(db, child_id, parent_id)

    result = await db.execute(
        select(StoryProgress)
        .where(StoryProgress.child_id == child_id)
        .order_by(StoryProgress.story_id)
    )
    progress_list = list(result.scalars().all())

    completed = sum(1 for p in progress_list if p.is_completed)
    in_progress = sum(1 for p in progress_list if not p.is_completed)

    return {
        "child_id": child_id,
        "total_stories": len(progress_list),
        "completed_stories": completed,
        "in_progress_stories": in_progress,
        "progress": progress_list,
    }
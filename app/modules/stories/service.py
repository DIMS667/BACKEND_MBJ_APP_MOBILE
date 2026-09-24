from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.modules.children.models import Child

from .models import (
    Story,
    StoryChoice,
    StoryFavorite,
    StoryMedia,
    StoryPage,
    StoryProgress,
)
from .schemas import StoryProgressCreate


MAX_STORY_IMAGE_BYTES = 8 * 1024 * 1024
PRIVATE_MEDIA_ROOT = (
    Path(settings.STORAGE_PATH).resolve().parent / "private_storage" / "stories"
)
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def _check_child_ownership(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> Child:
    result = await db.execute(select(Child).where(Child.id == child_id))
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enfant introuvable.",
        )
    if child.parent_id != parent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé.",
        )
    return child


def _story_access_clause(parent_id: int):
    return or_(Story.is_custom.is_(False), Story.owner_id == parent_id)


def _public_media_url(url: str | None) -> str | None:
    """Do not leak a private media path through a malformed catalog entry."""
    if not url:
        return None
    if url.startswith((
        "/storage/pictos/",
        "/storage/audio/",
        "https://static.arasaac.org/pictograms/",
    )):
        return url
    return None


def _public_story_payload(story: Story, *, include_pages: bool = False) -> dict:
    payload = {
        "id": story.id,
        "title": story.title,
        "description": story.description or "",
        "cover_url": _public_media_url(story.cover_url) or "",
        "category": story.category,
        "is_offline_available": bool(story.is_offline_available),
        "total_pages": story.total_pages,
    }
    if include_pages:
        payload["pages"] = [
            {
                "id": page.id,
                "story_id": story.id,
                "page_number": page.page_number,
                "text": page.text,
                "image_url": _public_media_url(page.image_url),
                "pictogram_url": _public_media_url(page.pictogram_url),
                "audio_url": _public_media_url(page.audio_url),
                "animation_type": page.animation_type or "fade",
                "local_page_key": page.local_page_key,
                "next_page_number": page.next_page_number,
                "choices": [
                    {
                        "id": choice.id,
                        "label": choice.label,
                        "pictogram_url": _public_media_url(choice.pictogram_url),
                        "next_page_number": choice.next_page_number,
                        "sort_order": choice.sort_order,
                    }
                    for choice in page.choices
                ],
            }
            for page in story.pages
        ]
    return payload


async def get_public_stories(
    db: AsyncSession,
    category: str | None = None,
) -> list[dict]:
    # Unauthenticated reads must never reuse the family-aware query: only
    # global seed content belongs here, not a parent's custom story.
    query = select(Story).where(
        Story.is_custom.is_(False),
        Story.owner_id.is_(None),
        Story.child_id.is_(None),
    )
    if category:
        query = query.where(Story.category == category)
    result = await db.execute(query.order_by(Story.category, Story.title))
    return [_public_story_payload(story) for story in result.scalars().all()]


async def get_public_story_detail(
    db: AsyncSession,
    story_id: int,
) -> dict:
    result = await db.execute(
        select(Story)
        .options(selectinload(Story.pages).selectinload(StoryPage.choices))
        .where(
            Story.id == story_id,
            Story.is_custom.is_(False),
            Story.owner_id.is_(None),
            Story.child_id.is_(None),
        )
    )
    story = result.scalar_one_or_none()
    if story is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Histoire introuvable.",
        )
    return _public_story_payload(story, include_pages=True)


async def _favorite_ids(
    db: AsyncSession,
    child_id: int | None,
) -> set[int]:
    if child_id is None:
        return set()
    result = await db.execute(
        select(StoryFavorite.story_id).where(StoryFavorite.child_id == child_id)
    )
    return set(result.scalars().all())


def _mark_favorite(story: Story, favorite_ids: set[int]) -> Story:
    story.is_favorite = story.id in favorite_ids
    return story


async def get_all_stories(
    db: AsyncSession,
    parent_id: int,
    category: str | None = None,
    child_id: int | None = None,
    favorites_only: bool = False,
) -> list[Story]:
    if child_id is not None:
        await _check_child_ownership(db, child_id, parent_id)

    query = (
        select(Story)
        .where(_story_access_clause(parent_id))
        .order_by(Story.category, Story.title)
    )
    if child_id is not None:
        query = query.where(or_(Story.child_id.is_(None), Story.child_id == child_id))
    if category:
        query = query.where(Story.category == category)

    favorite_ids = await _favorite_ids(db, child_id)
    result = await db.execute(query)
    stories = list(result.scalars().all())
    if favorites_only:
        stories = [story for story in stories if story.id in favorite_ids]
    return [_mark_favorite(story, favorite_ids) for story in stories]


async def get_story_detail(
    db: AsyncSession,
    story_id: int,
    parent_id: int,
    child_id: int | None = None,
) -> Story:
    if child_id is not None:
        await _check_child_ownership(db, child_id, parent_id)

    result = await db.execute(
        select(Story)
        .options(
            selectinload(Story.pages).selectinload(StoryPage.choices),
        )
        .where(Story.id == story_id, _story_access_clause(parent_id))
    )
    story = result.scalar_one_or_none()
    if not story or (story.child_id is not None and story.child_id != child_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Histoire introuvable.",
        )
    favorite_ids = await _favorite_ids(db, child_id)
    return _mark_favorite(story, favorite_ids)


async def save_progress(
    db: AsyncSession,
    story_id: int,
    data: StoryProgressCreate,
    parent_id: int,
) -> StoryProgress:
    await _check_child_ownership(db, data.child_id, parent_id)
    story = await get_story_detail(db, story_id, parent_id, data.child_id)
    if data.last_page > story.total_pages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La page demandée n'existe pas.",
        )
    valid_choices = {
        str(page.page_number): {choice.label for choice in page.choices}
        for page in story.pages
        if page.choices
    }
    for page_number, label in data.selected_choices.items():
        if label not in valid_choices.get(page_number, set()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Un choix narratif enregistré est invalide.",
            )

    result = await db.execute(
        select(StoryProgress).where(
            StoryProgress.story_id == story_id,
            StoryProgress.child_id == data.child_id,
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = StoryProgress(
            story_id=story_id,
            child_id=data.child_id,
            last_page=data.last_page,
            is_completed=data.is_completed,
            read_count=1 if data.is_completed else 0,
            selected_choices=data.selected_choices,
        )
        db.add(progress)
    else:
        was_completed = progress.is_completed
        progress.last_page = data.last_page
        progress.is_completed = data.is_completed
        progress.selected_choices = data.selected_choices
        if data.is_completed and not was_completed:
            progress.read_count += 1
    await db.flush()
    return progress


async def get_child_progress(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(StoryProgress)
        .join(Story, Story.id == StoryProgress.story_id)
        .where(
            StoryProgress.child_id == child_id,
            _story_access_clause(parent_id),
        )
        .order_by(StoryProgress.story_id)
    )
    progress_list = list(result.scalars().all())
    completed = sum(1 for item in progress_list if item.is_completed)
    return {
        "child_id": child_id,
        "total_stories": len(progress_list),
        "completed_stories": completed,
        "in_progress_stories": len(progress_list) - completed,
        "progress": progress_list,
    }


async def set_favorite(
    db: AsyncSession,
    story_id: int,
    child_id: int,
    is_favorite: bool,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, child_id, parent_id)
    await get_story_detail(db, story_id, parent_id, child_id)
    result = await db.execute(
        select(StoryFavorite).where(
            StoryFavorite.story_id == story_id,
            StoryFavorite.child_id == child_id,
        )
    )
    favorite = result.scalar_one_or_none()
    if is_favorite and favorite is None:
        db.add(StoryFavorite(story_id=story_id, child_id=child_id))
    elif not is_favorite and favorite is not None:
        await db.delete(favorite)
    return {
        "story_id": story_id,
        "child_id": child_id,
        "is_favorite": is_favorite,
    }


async def get_private_media(
    db: AsyncSession,
    media_id: int,
    parent_id: int,
) -> StoryMedia:
    result = await db.execute(
        select(StoryMedia).where(
            StoryMedia.id == media_id,
            StoryMedia.owner_id == parent_id,
        )
    )
    media = result.scalar_one_or_none()
    if media is None or not Path(media.file_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image introuvable.",
        )
    return media

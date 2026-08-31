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
from .schemas import CustomStoryUpsert, StoryProgressCreate


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


def _private_media_ids(urls: set[str | None]) -> set[int]:
    prefix = "/stories/media/"
    media_ids: set[int] = set()
    for url in urls:
        if not url or not url.startswith(prefix):
            continue
        raw_id = url.removeprefix(prefix).split("?", 1)[0]
        if raw_id.isdigit():
            media_ids.add(int(raw_id))
    return media_ids


async def _delete_private_media(
    db: AsyncSession,
    media_ids: set[int],
    parent_id: int,
) -> None:
    if not media_ids:
        return
    result = await db.execute(
        select(StoryMedia).where(
            StoryMedia.id.in_(media_ids),
            StoryMedia.owner_id == parent_id,
        )
    )
    for media in result.scalars().all():
        try:
            Path(media.file_path).unlink(missing_ok=True)
        except OSError:
            pass
        await db.delete(media)


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


async def upsert_custom_story(
    db: AsyncSession,
    data: CustomStoryUpsert,
    parent_id: int,
) -> Story:
    await _check_child_ownership(db, data.child_id, parent_id)

    result = await db.execute(
        select(Story).where(
            Story.client_uuid == data.client_uuid,
            Story.owner_id == parent_id,
        )
    )
    story = result.scalar_one_or_none()
    old_media_urls: set[str | None] = set()
    if story is None:
        story = Story(
            client_uuid=data.client_uuid,
            owner_id=parent_id,
            child_id=data.child_id,
            is_custom=True,
            is_offline_available=True,
        )
        db.add(story)
        await db.flush()
    elif not story.is_custom:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet identifiant est déjà utilisé.",
        )
    else:
        old_page_result = await db.execute(
            select(StoryPage.image_url).where(StoryPage.story_id == story.id)
        )
        old_media_urls = set(old_page_result.scalars().all())
        old_media_urls.add(story.cover_url)

    story.title = data.title.strip()
    story.description = data.description.strip()
    story.category = data.category.strip().lower()
    story.child_id = data.child_id
    story.total_pages = len(data.pages)
    story.cover_url = data.cover_url or next(
        (
            page.image_url or page.pictogram_url
            for page in data.pages
            if page.image_url or page.pictogram_url
        ),
        "",
    )

    await db.execute(delete(StoryPage).where(StoryPage.story_id == story.id))
    await db.flush()

    for page_data in sorted(data.pages, key=lambda item: item.page_number):
        page = StoryPage(
            story_id=story.id,
            page_number=page_data.page_number,
            text=page_data.text.strip(),
            image_url=page_data.image_url,
            pictogram_url=page_data.pictogram_url,
            audio_url=page_data.audio_url,
            animation_type=page_data.animation_type,
            local_page_key=page_data.local_page_key,
            next_page_number=page_data.next_page_number,
        )
        db.add(page)
        await db.flush()
        for choice_data in sorted(
            page_data.choices,
            key=lambda item: item.sort_order,
        ):
            db.add(
                StoryChoice(
                    page_id=page.id,
                    label=choice_data.label.strip(),
                    pictogram_url=choice_data.pictogram_url,
                    next_page_number=choice_data.next_page_number,
                    sort_order=choice_data.sort_order,
                )
            )

    new_media_urls = {data.cover_url}
    new_media_urls.update(page.image_url for page in data.pages)
    removed_media_ids = _private_media_ids(old_media_urls) - _private_media_ids(
        new_media_urls
    )
    await _delete_private_media(db, removed_media_ids, parent_id)
    await db.flush()
    return await get_story_detail(db, story.id, parent_id, data.child_id)


async def delete_custom_story(
    db: AsyncSession,
    client_uuid: str,
    parent_id: int,
) -> None:
    result = await db.execute(
        select(Story).where(
            Story.client_uuid == client_uuid,
            Story.owner_id == parent_id,
            Story.is_custom.is_(True),
        )
    )
    story = result.scalar_one_or_none()
    if story is None:
        return
    page_result = await db.execute(
        select(StoryPage.image_url).where(StoryPage.story_id == story.id)
    )
    media_urls = set(page_result.scalars().all())
    media_urls.add(story.cover_url)
    await _delete_private_media(
        db,
        _private_media_ids(media_urls),
        parent_id,
    )
    await db.delete(story)


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


def _validate_image_signature(content: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


async def save_private_media(
    db: AsyncSession,
    upload: UploadFile,
    client_uuid: str,
    parent_id: int,
) -> StoryMedia:
    content_type = upload.content_type or ""
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Format accepté : JPEG, PNG ou WebP.",
        )

    content = await upload.read(MAX_STORY_IMAGE_BYTES + 1)
    if len(content) > MAX_STORY_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="L'image ne doit pas dépasser 8 Mo.",
        )
    if not _validate_image_signature(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le contenu du fichier image est invalide.",
        )

    existing_result = await db.execute(
        select(StoryMedia).where(
            StoryMedia.client_uuid == client_uuid,
            StoryMedia.owner_id == parent_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    owner_directory = PRIVATE_MEDIA_ROOT / str(parent_id)
    owner_directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    file_path = owner_directory / filename
    async with aiofiles.open(file_path, "wb") as output:
        await output.write(content)

    media = StoryMedia(
        owner_id=parent_id,
        client_uuid=client_uuid,
        file_path=str(file_path),
        content_type=content_type,
        original_name=upload.filename,
    )
    db.add(media)
    await db.flush()
    return media


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

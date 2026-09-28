"""Find files belonging to deleted parent/child records.

Call ``collect_child_files`` before removing database rows, then call the
matching ``finish_*`` function after flush. Files are unlinked by the session
only after its transaction commits.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import or_, select

from app.config import settings
from app.core.storage_cleanup import owned_directory_files, queue_private_file_deletion
from app.modules.audio.models import AudioFile
from app.modules.children.models import Child
from app.modules.communication.models import (
    PictoCategory,
    Pictogram,
    PictogramMedia,
    SentenceHistory,
)
from app.modules.drawing.models import Drawing
from app.modules.stories.models import Story, StoryChoice, StoryMedia, StoryPage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChildFiles:
    child_id: int
    drawing_paths: frozenset[str]
    speech_urls: frozenset[str]
    pictogram_media_ids: frozenset[int]
    story_media_ids: frozenset[int]


def _private_root() -> Path:
    return Path(settings.STORAGE_PATH).resolve().parent / "private_storage"


def _storage_root() -> Path:
    return Path(settings.STORAGE_PATH).resolve()


def _picto_directory(parent_id: int, path: str | Path) -> Path:
    owner_root = _private_root() / "communication" / str(parent_id)
    candidate = Path(path).parent
    if candidate == owner_root or (
        candidate.parent == owner_root
        and candidate.name.isdecimal()
        and int(candidate.name) > 0
    ):
        return candidate
    return owner_root  # validation will reject any foreign path


def _owner_picto_files(parent_id: int) -> set[str]:
    owner_root = _private_root() / "communication" / str(parent_id)
    files = owned_directory_files(owner_root)
    try:
        for directory in owner_root.iterdir():
            if directory.name.isdecimal() and directory.is_dir():
                files.update(owned_directory_files(directory))
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("Could not inspect pictogram directory for parent %s", parent_id)
    return files


def _media_id(url: str | None, prefix: str) -> int | None:
    if not url or not url.startswith(prefix):
        return None
    suffix = url[len(prefix):]
    return int(suffix) if suffix.isdecimal() and int(suffix) > 0 else None


def _speech_path(url: str, child_id: int) -> Path | None:
    prefix = "/storage/audio/tts/"
    if not url.startswith(prefix):
        return None
    suffix = url[len(prefix):]
    parts = suffix.split("/")
    if len(parts) == 1:
        filename = parts[0]  # legacy flat layout
        directory = _storage_root() / "audio" / "tts"
    elif len(parts) == 2 and parts[0] == str(child_id):
        filename = parts[1]
        directory = _storage_root() / "audio" / "tts" / str(child_id)
    else:
        return None
    if not filename.endswith(".mp3") or "/" in filename or "\\" in filename:
        return None
    try:
        identifier = UUID(filename[:-4])
    except ValueError:
        return None
    if identifier.version != 4 or str(identifier) != filename[:-4]:
        return None
    return directory / filename


async def collect_child_files(db, child_id: int, parent_id: int, *, include_creations: bool = True) -> ChildFiles:
    speech = await db.execute(
        select(SentenceHistory.audio_url).where(SentenceHistory.child_id == child_id)
    )
    speech_urls = frozenset(url for url in speech.scalars().all() if url)
    if not include_creations:
        return ChildFiles(child_id, frozenset(), speech_urls, frozenset(), frozenset())

    drawings = await db.execute(
        select(Drawing.image_url).where(Drawing.child_id == child_id)
    )
    drawing_paths = set(drawings.scalars().all())
    drawing_paths.update(
        owned_directory_files(_private_root() / "drawings" / str(child_id))
    )
    pictograms = await db.execute(
        select(Pictogram.image_url, Pictogram.audio_url).where(
            Pictogram.child_id == child_id,
            Pictogram.owner_id == parent_id,
            Pictogram.is_default.is_(False),
        )
    )
    categories = await db.execute(
        select(PictoCategory.icon_url).where(
            PictoCategory.child_id == child_id,
            PictoCategory.owner_id == parent_id,
            PictoCategory.is_default.is_(False),
        )
    )
    media_rows = await db.execute(
        select(PictogramMedia.id).where(
            PictogramMedia.child_id == child_id,
            PictogramMedia.owner_id == parent_id,
        )
    )
    picto_urls = [url for row in pictograms.all() for url in row]
    picto_urls.extend(categories.scalars().all())
    picto_ids = {
        media_id
        for url in picto_urls
        if (media_id := _media_id(url, "/pictos/media/")) is not None
    }
    picto_ids.update(media_rows.scalars().all())

    story_ids_result = await db.execute(
        select(Story.id, Story.cover_url).where(
            Story.child_id == child_id,
            Story.owner_id == parent_id,
            Story.is_custom.is_(True),
        )
    )
    story_rows = story_ids_result.all()
    owned_story_media = await db.execute(
        select(StoryMedia.id).where(
            StoryMedia.child_id == child_id,
            StoryMedia.owner_id == parent_id,
        )
    )
    story_ids = [row[0] for row in story_rows]
    story_urls = [row[1] for row in story_rows]
    if story_ids:
        pages_result = await db.execute(
            select(StoryPage.id, StoryPage.image_url, StoryPage.audio_url, StoryPage.pictogram_url)
            .where(StoryPage.story_id.in_(story_ids))
        )
        page_rows = pages_result.all()
        page_ids = [row[0] for row in page_rows]
        story_urls.extend(url for row in page_rows for url in row[1:])
        if page_ids:
            choices_result = await db.execute(
                select(StoryChoice.pictogram_url).where(StoryChoice.page_id.in_(page_ids))
            )
            story_urls.extend(choices_result.scalars().all())

    media_ids = {
        media_id
        for url in story_urls
        if (media_id := _media_id(url, "/stories/media/")) is not None
    }
    media_ids.update(owned_story_media.scalars().all())
    return ChildFiles(
        child_id,
        frozenset(drawing_paths),
        speech_urls,
        frozenset(picto_ids),
        frozenset(media_ids),
    )


async def _queue_child_drawing_and_speech_files(db, files: ChildFiles) -> None:
    drawing_directory = _private_root() / "drawings" / str(files.child_id)
    for image_path in files.drawing_paths:
        remaining = await db.execute(select(Drawing.id).where(Drawing.image_url == image_path).limit(1))
        if remaining.first() is None:
            queue_private_file_deletion(db, image_path, drawing_directory)

    child_speech_directory = _storage_root() / "audio" / "tts" / str(files.child_id)
    speech_urls = set(files.speech_urls)
    speech_urls.update(
        f"/storage/audio/tts/{files.child_id}/{Path(path).name}"
        for path in owned_directory_files(child_speech_directory)
    )
    for url in speech_urls:
        remaining = await db.execute(
            select(SentenceHistory.id).where(SentenceHistory.audio_url == url).limit(1)
        )
        path = _speech_path(url, files.child_id)
        catalog_reference = await db.execute(
            select(AudioFile.id).where(AudioFile.file_url == url).limit(1)
        )
        if remaining.first() is None and catalog_reference.first() is None and path is not None:
            queue_private_file_deletion(db, path, path.parent)


async def _story_media_is_referenced(db, media_id: int) -> bool:
    url = f"/stories/media/{media_id}"
    checks = (
        select(Story.id).where(Story.cover_url == url).limit(1),
        select(StoryPage.id).where(
            or_(StoryPage.image_url == url, StoryPage.audio_url == url, StoryPage.pictogram_url == url)
        ).limit(1),
        select(StoryChoice.id).where(StoryChoice.pictogram_url == url).limit(1),
    )
    for query in checks:
        result = await db.execute(query)
        if result.first() is not None:
            return True
    return False


async def finish_child_cleanup(db, files: ChildFiles, parent_id: int, *, include_creations: bool = True) -> None:
    """Remove unreferenced media rows and queue the corresponding owned files."""
    await _queue_child_drawing_and_speech_files(db, files)
    if not include_creations:
        return

    picto_directory = _private_root() / "communication" / str(parent_id)
    for media_id in files.pictogram_media_ids:
        url = f"/pictos/media/{media_id}"
        remaining = await db.execute(
            select(Pictogram.id).where(
                or_(Pictogram.image_url == url, Pictogram.audio_url == url)
            ).limit(1)
        )
        category_reference = await db.execute(
            select(PictoCategory.id).where(PictoCategory.icon_url == url).limit(1)
        )
        if remaining.first() is not None or category_reference.first() is not None:
            continue
        result = await db.execute(
            select(PictogramMedia).where(PictogramMedia.id == media_id, PictogramMedia.owner_id == parent_id)
        )
        media = result.scalar_one_or_none()
        if media is not None:
            await db.delete(media)
            await db.flush()
            duplicate = await db.execute(
                select(PictogramMedia.id).where(PictogramMedia.file_path == media.file_path).limit(1)
            )
            if duplicate.first() is None:
                queue_private_file_deletion(
                    db, media.file_path, _picto_directory(parent_id, media.file_path)
                )

    # New uploads are stored under their child's directory. A file written
    # just before a worker crash has no row, but still belongs to this child.
    for path in owned_directory_files(picto_directory / str(files.child_id)):
        duplicate = await db.execute(
            select(PictogramMedia.id).where(PictogramMedia.file_path == path).limit(1)
        )
        if duplicate.first() is None:
            queue_private_file_deletion(db, path, picto_directory / str(files.child_id))

    story_directory = _private_root() / "stories" / str(parent_id)
    for media_id in files.story_media_ids:
        if await _story_media_is_referenced(db, media_id):
            continue
        result = await db.execute(
            select(StoryMedia).where(StoryMedia.id == media_id, StoryMedia.owner_id == parent_id)
        )
        media = result.scalar_one_or_none()
        if media is not None:
            await db.delete(media)
            await db.flush()
            duplicate = await db.execute(
                select(StoryMedia.id).where(StoryMedia.file_path == media.file_path).limit(1)
            )
            if duplicate.first() is None:
                queue_private_file_deletion(db, media.file_path, story_directory)


async def collect_account_files(db, parent_id: int) -> tuple[list[ChildFiles], list[tuple[int, str]], list[tuple[int, str]]]:
    children = await db.execute(select(Child.id).where(Child.parent_id == parent_id))
    child_files = [
        await collect_child_files(db, child_id, parent_id, include_creations=True)
        for child_id in children.scalars().all()
    ]
    pictos = await db.execute(select(PictogramMedia.id, PictogramMedia.file_path).where(PictogramMedia.owner_id == parent_id))
    stories = await db.execute(select(StoryMedia.id, StoryMedia.file_path).where(StoryMedia.owner_id == parent_id))
    return child_files, list(pictos.all()), list(stories.all())


async def finish_account_cleanup(
    db,
    parent_id: int,
    child_files: list[ChildFiles],
    pictogram_paths: list[tuple[int, str]],
    story_paths: list[tuple[int, str]],
) -> None:
    for files in child_files:
        await _queue_child_drawing_and_speech_files(db, files)
    for path in {path for _, path in pictogram_paths} | _owner_picto_files(parent_id):
        duplicates = await db.execute(
            select(PictogramMedia.id).where(PictogramMedia.file_path == path).limit(1)
        )
        if duplicates.first() is not None:
            continue
        media_ids = [media_id for media_id, candidate in pictogram_paths if candidate == path]
        for media_id in media_ids:
            url = f"/pictos/media/{media_id}"
            references = await db.execute(
                select(Pictogram.id).where(
                    or_(Pictogram.image_url == url, Pictogram.audio_url == url)
                ).limit(1)
            )
            category_reference = await db.execute(
                select(PictoCategory.id).where(PictoCategory.icon_url == url).limit(1)
            )
            if references.first() is not None or category_reference.first() is not None:
                break
        else:
            queue_private_file_deletion(db, path, _picto_directory(parent_id, path))

    story_directory = _private_root() / "stories" / str(parent_id)
    for path in {path for _, path in story_paths} | owned_directory_files(story_directory):
        duplicates = await db.execute(
            select(StoryMedia.id).where(StoryMedia.file_path == path).limit(1)
        )
        if duplicates.first() is not None:
            continue
        media_ids = [media_id for media_id, candidate in story_paths if candidate == path]
        referenced = False
        for media_id in media_ids:
            if await _story_media_is_referenced(db, media_id):
                referenced = True
                break
        if not referenced:
            queue_private_file_deletion(db, path, story_directory)

"""Transactional, retryable removal of private files.

Deletion jobs are stored in the same database transaction as the user data
deletion. A failed filesystem unlink or worker crash leaves a job for the
next request rather than losing the cleanup instruction.
"""

import logging
from pathlib import Path
from time import monotonic

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.storage_models import PendingFileDeletion


logger = logging.getLogger(__name__)
_CREATED_FILES = "mbj_new_private_files"
_NEW_DELETIONS = "mbj_has_new_file_deletions"
_last_drain_at = 0.0
_RETRY_INTERVAL_SECONDS = 60


def _allowed_directory(directory: Path) -> bool:
    storage = Path(settings.STORAGE_PATH).resolve()
    private = storage.parent / "private_storage"
    if directory == storage / "audio" / "tts":
        return True  # Old TTS files used a shared directory.
    if directory.parent == storage / "audio" / "tts":
        return directory.name.isdecimal() and int(directory.name) > 0
    for folder in ("drawings", "communication", "stories"):
        if directory.parent == private / folder:
            return directory.name.isdecimal() and int(directory.name) > 0
    if directory.parent.parent == private / "communication":
        return (
            directory.parent.name.isdecimal()
            and int(directory.parent.name) > 0
            and directory.name.isdecimal()
            and int(directory.name) > 0
        )
    return False


def _validated_file(file_path: str | Path, owner_directory: Path) -> tuple[Path, Path] | None:
    path = Path(file_path)
    if not path.is_absolute():
        logger.warning("Ignoring non-absolute private media path: %s", path)
        return None
    try:
        directory = owner_directory.resolve()
        expected_directory = owner_directory.parent.resolve() / owner_directory.name
        if (
            directory != expected_directory
            or not _allowed_directory(directory)
            or path.parent.resolve() != directory
            or path.resolve().parent != directory
        ):
            logger.warning("Ignoring private media path outside owned directory: %s", path)
            return None
    except OSError:
        logger.exception("Could not validate private media path: %s", path)
        return None
    return path, directory


def queue_private_file_deletion(db, file_path: str | Path, owner_directory: Path) -> bool:
    """Persist an owned file's deletion alongside the row removal."""
    validated = _validated_file(file_path, owner_directory)
    if validated is None:
        return False
    path, directory = validated
    db.add(PendingFileDeletion(file_path=str(path), owner_directory=str(directory)))
    db.info[_NEW_DELETIONS] = True
    return True


def queue_created_file_on_rollback(db, file_path: str | Path, owner_directory: Path) -> None:
    """A newly generated file must not outlive a failed database transaction."""
    validated = _validated_file(file_path, owner_directory)
    if validated is not None:
        db.info.setdefault(_CREATED_FILES, set()).add(validated)


def owned_directory_files(owner_directory: Path) -> set[str]:
    """Find upload files left without a database row by an interrupted save."""
    try:
        directory = owner_directory.resolve()
        if directory != owner_directory.parent.resolve() / owner_directory.name or not _allowed_directory(directory):
            logger.warning("Ignoring redirected private media directory: %s", owner_directory)
            return set()
        return {str(path) for path in owner_directory.iterdir() if path.is_file()}
    except FileNotFoundError:
        return set()
    except OSError:
        logger.exception("Could not inspect private media directory: %s", owner_directory)
        return set()


@event.listens_for(Session, "after_commit")
def _forget_created_files_after_commit(session: Session) -> None:
    session.info.pop(_CREATED_FILES, None)


@event.listens_for(Session, "after_rollback")
def _remove_created_files_after_rollback(session: Session) -> None:
    for path, directory in session.info.pop(_CREATED_FILES, set()):
        try:
            if _validated_file(path, directory) is not None:
                path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove generated media after rollback: %s", path)
    session.info.pop(_NEW_DELETIONS, None)


async def process_pending_file_deletions(db) -> int:
    """Process a bounded batch; keep failed jobs for a later retry."""
    result = await db.execute(
        select(PendingFileDeletion)
        .order_by(PendingFileDeletion.attempts, PendingFileDeletion.id)
        .limit(100)
        .with_for_update(skip_locked=True)
    )
    removed = 0
    for job in result.scalars().all():
        validated = _validated_file(job.file_path, Path(job.owner_directory))
        if validated is None:
            logger.error("Invalid pending private file deletion job %s", job.id)
            job.attempts += 1
            continue
        path, _ = validated
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove private media; will retry: %s", path)
            job.attempts += 1
            continue
        await db.delete(job)
        removed += 1
    return removed


async def drain_pending_file_deletions(*, force: bool = False) -> None:
    """Retry after commits and periodically on subsequent requests."""
    global _last_drain_at
    now = monotonic()
    if not force and now - _last_drain_at < _RETRY_INTERVAL_SECONDS:
        return
    _last_drain_at = now
    from app.database import AsyncSessionLocal  # avoid an import cycle

    async with AsyncSessionLocal() as db:
        try:
            await process_pending_file_deletions(db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


def has_new_file_deletions(db) -> bool:
    return bool(db.info.pop(_NEW_DELETIONS, False))

"""Account and child deletion must remove only their committed private files."""

from datetime import datetime, timedelta
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.config import settings
from app.core.storage_cleanup import process_pending_file_deletions
from app.core.storage_models import PendingFileDeletion
from app.database import Base
from app.modules.auth.models import AccountDeletionCode, User
from app.modules.auth.service import confirm_account_deletion
from app.modules.children.models import Child
from app.modules.children.service import delete_child, delete_child_data
from app.modules.communication.models import (
    PictoCategory,
    Pictogram,
    PictogramMedia,
    SentenceHistory,
)
from app.modules.communication.schemas import SpeechRequest
from app.modules.communication import service as communication_service
from app.modules.drawing.models import Drawing
from app.modules.stories.models import Story, StoryMedia

# Register every model for SQLite's foreign keys and SQLAlchemy relationships.
from app.modules import audio, games  # noqa: F401
from app.modules.audio import models as audio_models  # noqa: F401
from app.modules.games import models as game_models  # noqa: F401


class AsyncSessionFacade:
    """Exercise async services against a real, transactional SQLite database."""

    def __init__(self, session: Session):
        self.session = session
        self.info = session.info

    async def execute(self, statement):
        return self.session.execute(statement)

    async def delete(self, instance):
        self.session.delete(instance)

    async def flush(self):
        self.session.flush()

    def add(self, instance):
        self.session.add(instance)


@pytest.fixture
def database(monkeypatch):
    test_base = (Path(__file__).resolve().parent / "runtime_file_cleanup").resolve()
    test_root = test_base / uuid4().hex
    test_root.mkdir(parents=True)
    storage = test_root / "storage"
    storage.mkdir()
    monkeypatch.setattr(settings, "STORAGE_PATH", str(storage))
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session, AsyncSessionFacade(session), test_root
    engine.dispose()
    if test_root.resolve().is_relative_to(test_base):
        shutil.rmtree(test_root)


def _file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"private data")
    return path


def _parent(session: Session, email: str) -> User:
    user = User(email=email, hashed_password="hash", first_name="Parent", last_name="Test")
    session.add(user)
    session.flush()
    return user


def _child(session: Session, parent: User, name: str) -> Child:
    child = Child(parent_id=parent.id, first_name=name)
    session.add(child)
    session.flush()
    return child


def _drawing(session: Session, root: Path, child: Child) -> Path:
    path = _file(root / "private_storage" / "drawings" / str(child.id) / f"{uuid4().hex}.png")
    session.add(Drawing(child_id=child.id, image_url=str(path)))
    session.flush()
    return path


def _speech(session: Session, root: Path, child: Child) -> Path:
    name = f"{uuid4()}.mp3"
    path = _file(root / "storage" / "audio" / "tts" / name)
    session.add(SentenceHistory(child_id=child.id, sentence_pictos=[], sentence_text="Bonjour", audio_url=f"/storage/audio/tts/{name}"))
    session.flush()
    return path


def _picto_media(session: Session, root: Path, parent: User, children: list[Child]) -> Path:
    path = _file(root / "private_storage" / "communication" / str(parent.id) / f"{uuid4().hex}.png")
    media = PictogramMedia(owner_id=parent.id, client_uuid=uuid4().hex, file_path=str(path), content_type="image/png")
    session.add(media)
    session.flush()
    for child in children:
        category = PictoCategory(name="Privé", is_default=False, owner_id=parent.id, child_id=child.id, client_uuid=uuid4().hex)
        session.add(category)
        session.flush()
        session.add(Pictogram(category_id=category.id, label="Photo", image_url=f"/pictos/media/{media.id}", is_default=False, owner_id=parent.id, child_id=child.id, client_uuid=uuid4().hex))
    session.flush()
    return path


def _story_media(session: Session, root: Path, parent: User, child: Child) -> Path:
    path = _file(root / "private_storage" / "stories" / str(parent.id) / f"{uuid4().hex}.png")
    media = StoryMedia(owner_id=parent.id, client_uuid=uuid4().hex, file_path=str(path), content_type="image/png")
    session.add(media)
    session.flush()
    session.add(Story(title="Histoire privée", category="custom", is_custom=True, owner_id=parent.id, child_id=child.id, cover_url=f"/stories/media/{media.id}"))
    session.flush()
    return path


async def _drain(session: Session, db: AsyncSessionFacade) -> None:
    await process_pending_file_deletions(db)
    session.commit()


@pytest.mark.asyncio
async def test_child_deletion_removes_own_files_after_commit_but_preserves_shared_media(database):
    session, db, root = database
    parent = _parent(session, "parent@example.org")
    first = _child(session, parent, "Un")
    second = _child(session, parent, "Deux")
    drawing = _drawing(session, root, first)
    orphan_drawing = _file(root / "private_storage" / "drawings" / str(first.id) / f"{uuid4().hex}.png")
    other_drawing = _drawing(session, root, second)
    speech = _speech(session, root, first)
    orphan_speech = _file(root / "storage" / "audio" / "tts" / str(first.id) / f"{uuid4()}.mp3")
    shared_picto = _picto_media(session, root, parent, [first, second])
    linked_picto = _file(root / "private_storage" / "communication" / str(parent.id) / f"{uuid4().hex}.png")
    orphan_child_picto = _file(root / "private_storage" / "communication" / str(parent.id) / str(first.id) / f"{uuid4().hex}.png")
    session.add(PictogramMedia(
        owner_id=parent.id, child_id=first.id, client_uuid=uuid4().hex,
        file_path=str(linked_picto), content_type="image/png",
    ))
    private_story = _story_media(session, root, parent, first)
    linked_story = _file(root / "private_storage" / "stories" / str(parent.id) / f"{uuid4().hex}.png")
    session.add(StoryMedia(
        owner_id=parent.id, child_id=first.id, client_uuid=uuid4().hex,
        file_path=str(linked_story), content_type="image/png",
    ))
    session.commit()

    await delete_child(db, first.id, parent.id)
    assert all(path.exists() for path in (drawing, orphan_drawing, speech, orphan_speech, shared_picto, private_story, linked_picto, orphan_child_picto, linked_story))
    session.commit()
    assert session.scalar(select(PendingFileDeletion.id)) is not None
    await _drain(session, db)

    assert not drawing.exists()
    assert not orphan_drawing.exists()
    assert not speech.exists()
    assert not orphan_speech.exists()
    assert not private_story.exists()
    assert not linked_picto.exists()
    assert not orphan_child_picto.exists()
    assert not linked_story.exists()
    assert shared_picto.exists()
    assert other_drawing.exists()
    assert session.get(Child, second.id) is not None
    assert session.get(Child, first.id) is None


@pytest.mark.asyncio
async def test_account_deletion_removes_all_owned_files_and_never_catalog_or_foreign_files(database):
    session, db, root = database
    parent = _parent(session, "delete@example.org")
    other = _parent(session, "keep@example.org")
    child = _child(session, parent, "A supprimer")
    other_child = _child(session, other, "A garder")
    drawing = _drawing(session, root, child)
    speech = _speech(session, root, child)
    picto = _picto_media(session, root, parent, [child])
    orphan_picto = _file(root / "private_storage" / "communication" / str(parent.id) / f"{uuid4().hex}.png")
    orphan_nested_picto = _file(root / "private_storage" / "communication" / str(parent.id) / "999999" / f"{uuid4().hex}.png")
    story = _story_media(session, root, parent, child)
    orphan_story = _file(root / "private_storage" / "stories" / str(parent.id) / f"{uuid4().hex}.png")
    other_drawing = _drawing(session, root, other_child)
    catalog = _file(root / "storage" / "pictos" / "catalog.png")
    session.add(Drawing(child_id=child.id, image_url=str(catalog)))
    session.add(AccountDeletionCode(user_id=parent.id, code="123456", expires_at=datetime.utcnow() + timedelta(minutes=10), used=False))
    session.commit()

    await confirm_account_deletion(db, parent, "123456")
    assert all(path.exists() for path in (drawing, speech, picto, story))
    session.commit()
    assert session.scalar(select(PendingFileDeletion.id)) is not None
    await _drain(session, db)

    assert all(not path.exists() for path in (drawing, speech, picto, story, orphan_picto, orphan_nested_picto, orphan_story))
    assert catalog.exists()
    assert other_drawing.exists()
    assert session.get(User, parent.id) is None
    assert session.get(User, other.id) is not None


@pytest.mark.asyncio
async def test_rollback_keeps_files_and_records(database):
    session, db, root = database
    parent = _parent(session, "rollback@example.org")
    child = _child(session, parent, "Conserver")
    drawing = _drawing(session, root, child)
    session.commit()

    await delete_child(db, child.id, parent.id)
    session.rollback()

    assert drawing.exists()
    assert session.get(Child, child.id) is not None
    assert session.scalar(select(PendingFileDeletion.id)) is None


@pytest.mark.asyncio
async def test_delete_child_activity_data_removes_tts_but_keeps_creations(database):
    session, db, root = database
    parent = _parent(session, "activity@example.org")
    child = _child(session, parent, "Conserver profil")
    drawing = _drawing(session, root, child)
    speech = _speech(session, root, child)
    session.commit()

    await delete_child_data(db, child.id, parent.id)
    session.commit()
    await _drain(session, db)

    assert not speech.exists()
    assert drawing.exists()
    assert session.get(Child, child.id) is not None
    assert session.scalar(select(SentenceHistory.id).where(SentenceHistory.child_id == child.id)) is None


@pytest.mark.asyncio
async def test_child_sentence_stays_on_server_without_external_audio(database):
    session, db, root = database
    parent = _parent(session, "tts@example.org")
    child = _child(session, parent, "TTS")
    session.commit()

    payload = await communication_service.generate_speech(
        db, SpeechRequest(child_id=child.id, sentence_text="Bonjour", picto_ids=[]), parent.id
    )
    assert payload == {"sentence_text": "Bonjour", "audio_url": ""}
    assert not (root / "storage" / "audio" / "tts" / str(child.id)).exists()
    assert session.scalar(select(SentenceHistory.sentence_text).where(SentenceHistory.child_id == child.id)) == "Bonjour"
    session.rollback()

    assert session.scalar(select(SentenceHistory.id).where(SentenceHistory.child_id == child.id)) is None


@pytest.mark.asyncio
async def test_pending_cleanup_is_retryable_after_unlink_failure(database, monkeypatch):
    session, db, root = database
    parent = _parent(session, "retry@example.org")
    child = _child(session, parent, "Retry")
    drawing = _drawing(session, root, child)
    session.commit()
    await delete_child(db, child.id, parent.id)
    session.commit()

    original_unlink = Path.unlink

    def fail_once(self, *args, **kwargs):
        if self == drawing:
            raise PermissionError("simulated filesystem error")
        return original_unlink(self, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(Path, "unlink", fail_once)
        await _drain(session, db)
    assert drawing.exists()
    assert session.scalar(select(PendingFileDeletion.attempts)) == 1

    await _drain(session, db)
    assert not drawing.exists()
    assert session.scalar(select(PendingFileDeletion.id)) is None


@pytest.mark.asyncio
async def test_pictogram_upload_is_child_owned_and_removed_on_rollback(database, monkeypatch):
    session, db, root = database
    monkeypatch.setattr(
        communication_service, "PRIVATE_MEDIA_ROOT",
        root / "private_storage" / "communication",
    )
    parent = _parent(session, "upload@example.org")
    other = _parent(session, "other-upload@example.org")
    child = _child(session, parent, "Mon enfant")
    foreign_child = _child(session, other, "Autre enfant")
    session.commit()

    class FakeUpload:
        filename = "photo.png"
        content_type = "image/png"

        async def read(self, _limit):
            return b"\x89PNG\r\n\x1a\nprivate"

    with pytest.raises(HTTPException) as forbidden:
        await communication_service.save_private_media(
            db, FakeUpload(), uuid4().hex, parent.id, child_id=foreign_child.id
        )
    assert forbidden.value.status_code == 403

    media = await communication_service.save_private_media(
        db, FakeUpload(), uuid4().hex, parent.id, child_id=child.id
    )
    path = Path(media.file_path)
    assert path.parent == root / "private_storage" / "communication" / str(parent.id) / str(child.id)
    assert path.exists()
    session.rollback()
    assert not path.exists()

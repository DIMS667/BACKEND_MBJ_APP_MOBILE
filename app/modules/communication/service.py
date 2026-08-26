import asyncio
import uuid
from collections import Counter
from pathlib import Path
from typing import Iterable

import aiofiles
from fastapi import HTTPException, UploadFile, status
from gtts import gTTS
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.children.models import Child

from .models import (
    FavoritePicto,
    PictoCategory,
    Pictogram,
    PictogramMedia,
    SentenceHistory,
)
from .schemas import (
    CustomCategoryUpsert,
    CustomPictogramUpsert,
    SetFavoriteRequest,
    SpeechRequest,
    ToggleFavoriteRequest,
)


MAX_PICTOGRAM_IMAGE_BYTES = 8 * 1024 * 1024
PRIVATE_MEDIA_ROOT = (
    Path(settings.STORAGE_PATH).resolve().parent
    / "private_storage"
    / "communication"
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
    if child is None:
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


def _category_access_clause(parent_id: int, child_id: int):
    return or_(
        PictoCategory.is_default.is_(True),
        and_(
            PictoCategory.is_default.is_(False),
            PictoCategory.owner_id == parent_id,
            PictoCategory.child_id == child_id,
        ),
    )


def _pictogram_access_clause(parent_id: int, child_id: int):
    return or_(
        Pictogram.is_default.is_(True),
        and_(
            Pictogram.is_default.is_(False),
            Pictogram.owner_id == parent_id,
            Pictogram.child_id == child_id,
        ),
    )


def _category_payload(category: PictoCategory) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "icon_url": category.icon_url,
        "color": category.color,
        "order": category.order or 0,
        "is_default": bool(category.is_default),
        "child_id": category.child_id,
        "client_uuid": category.client_uuid,
    }


def _pictogram_payload(
    pictogram: Pictogram,
    favorite_ids: set[int] | None = None,
) -> dict:
    return {
        "id": pictogram.id,
        "category_id": pictogram.category_id,
        "label": pictogram.label,
        "image_url": pictogram.image_url,
        "audio_url": pictogram.audio_url or "",
        "is_default": bool(pictogram.is_default),
        "is_favorite": pictogram.id in (favorite_ids or set()),
        "child_id": pictogram.child_id,
        "client_uuid": pictogram.client_uuid,
    }


async def _favorite_ids(db: AsyncSession, child_id: int) -> set[int]:
    result = await db.execute(
        select(FavoritePicto.picto_id).where(
            FavoritePicto.child_id == child_id,
        )
    )
    return set(result.scalars().all())


async def get_categories(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(PictoCategory)
        .where(_category_access_clause(parent_id, child_id))
        .order_by(
            PictoCategory.is_default.desc(),
            PictoCategory.order,
            PictoCategory.name,
        )
    )
    return [_category_payload(category) for category in result.scalars().all()]


async def upsert_custom_category(
    db: AsyncSession,
    data: CustomCategoryUpsert,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)
    result = await db.execute(
        select(PictoCategory).where(
            PictoCategory.owner_id == parent_id,
            PictoCategory.client_uuid == data.client_uuid,
        )
    )
    category = result.scalar_one_or_none()

    duplicate_result = await db.execute(
        select(PictoCategory).where(
            _category_access_clause(parent_id, data.child_id),
            func.lower(PictoCategory.name) == data.name.lower(),
            PictoCategory.client_uuid.is_distinct_from(data.client_uuid),
        )
    )
    if duplicate_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une catégorie porte déjà ce nom.",
        )

    if category is None:
        category = PictoCategory(
            owner_id=parent_id,
            child_id=data.child_id,
            client_uuid=data.client_uuid,
            is_default=False,
            order=1000,
        )
        db.add(category)
    elif category.child_id != data.child_id or category.is_default:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette catégorie ne peut pas être modifiée.",
        )

    category.name = data.name
    category.color = data.color.upper()
    category.icon_url = None
    await db.flush()
    return _category_payload(category)


async def delete_custom_category(
    db: AsyncSession,
    client_uuid: str,
    parent_id: int,
) -> None:
    result = await db.execute(
        select(PictoCategory).where(
            PictoCategory.owner_id == parent_id,
            PictoCategory.client_uuid == client_uuid,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        return
    if category.is_default:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une catégorie par défaut ne peut pas être supprimée.",
        )

    pictogram_result = await db.execute(
        select(Pictogram).where(Pictogram.category_id == category.id)
    )
    pictograms = list(pictogram_result.scalars().all())
    if any(
        pictogram.is_default
        or pictogram.owner_id != parent_id
        or pictogram.child_id != category.child_id
        for pictogram in pictograms
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette catégorie contient des données protégées.",
        )

    media_ids = {
        media_id
        for pictogram in pictograms
        if (media_id := _media_id_from_url(pictogram.image_url)) is not None
    }
    await db.delete(category)
    await db.flush()

    for media_id in media_ids:
        await _delete_private_media_if_unused(
            db,
            media_id,
            parent_id,
            excluding_picto_id=0,
        )


async def _get_accessible_category(
    db: AsyncSession,
    category_id: int,
    child_id: int,
    parent_id: int,
) -> PictoCategory:
    result = await db.execute(
        select(PictoCategory).where(
            PictoCategory.id == category_id,
            _category_access_clause(parent_id, child_id),
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catégorie introuvable.",
        )
    return category


async def get_all_pictos(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(Pictogram)
        .where(_pictogram_access_clause(parent_id, child_id))
        .order_by(Pictogram.label)
    )
    favorite_ids = await _favorite_ids(db, child_id)
    return [
        _pictogram_payload(pictogram, favorite_ids)
        for pictogram in result.scalars().all()
    ]


async def get_pictos_by_category(
    db: AsyncSession,
    category_id: int,
    child_id: int,
    parent_id: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    await _get_accessible_category(db, category_id, child_id, parent_id)
    result = await db.execute(
        select(Pictogram)
        .where(
            Pictogram.category_id == category_id,
            _pictogram_access_clause(parent_id, child_id),
        )
        .order_by(Pictogram.label)
    )
    favorite_ids = await _favorite_ids(db, child_id)
    return [
        _pictogram_payload(pictogram, favorite_ids)
        for pictogram in result.scalars().all()
    ]


def _media_id_from_url(url: str | None) -> int | None:
    if not url or not url.startswith("/pictos/media/"):
        return None
    raw_id = url.removeprefix("/pictos/media/").split("/", 1)[0]
    return int(raw_id) if raw_id.isdigit() else None


async def _get_owned_media(
    db: AsyncSession,
    media_id: int,
    parent_id: int,
) -> PictogramMedia | None:
    result = await db.execute(
        select(PictogramMedia).where(
            PictogramMedia.id == media_id,
            PictogramMedia.owner_id == parent_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_custom_pictogram(
    db: AsyncSession,
    data: CustomPictogramUpsert,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)
    await _get_accessible_category(
        db,
        data.category_id,
        data.child_id,
        parent_id,
    )

    media_id = _media_id_from_url(data.image_url)
    media = (
        await _get_owned_media(db, media_id, parent_id)
        if media_id is not None
        else None
    )
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L’image privée est invalide ou inaccessible.",
        )

    result = await db.execute(
        select(Pictogram).where(
            Pictogram.owner_id == parent_id,
            Pictogram.client_uuid == data.client_uuid,
        )
    )
    pictogram = result.scalar_one_or_none()
    old_media_id = _media_id_from_url(
        pictogram.image_url if pictogram is not None else None
    )

    if pictogram is None:
        pictogram = Pictogram(
            owner_id=parent_id,
            child_id=data.child_id,
            client_uuid=data.client_uuid,
            is_default=False,
            audio_url="",
        )
        db.add(pictogram)
    elif pictogram.child_id != data.child_id or pictogram.is_default:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce pictogramme ne peut pas être modifié.",
        )

    pictogram.category_id = data.category_id
    pictogram.label = data.label
    pictogram.image_url = data.image_url
    await db.flush()

    if old_media_id is not None and old_media_id != media_id:
        await _delete_private_media_if_unused(
            db,
            old_media_id,
            parent_id,
            excluding_picto_id=pictogram.id,
        )

    favorite_ids = await _favorite_ids(db, data.child_id)
    return _pictogram_payload(pictogram, favorite_ids)


async def delete_custom_pictogram(
    db: AsyncSession,
    client_uuid: str,
    parent_id: int,
) -> None:
    result = await db.execute(
        select(Pictogram).where(
            Pictogram.owner_id == parent_id,
            Pictogram.client_uuid == client_uuid,
            Pictogram.is_default.is_(False),
        )
    )
    pictogram = result.scalar_one_or_none()
    if pictogram is None:
        return
    media_id = _media_id_from_url(pictogram.image_url)
    pictogram_id = pictogram.id
    await db.delete(pictogram)
    await db.flush()
    if media_id is not None:
        await _delete_private_media_if_unused(
            db,
            media_id,
            parent_id,
            excluding_picto_id=pictogram_id,
        )


async def toggle_favorite(
    db: AsyncSession,
    picto_id: int,
    data: ToggleFavoriteRequest,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)
    await _ensure_pictogram_access(
        db,
        picto_id,
        data.child_id,
        parent_id,
        lock=True,
    )
    result = await db.execute(
        select(FavoritePicto).where(
            FavoritePicto.child_id == data.child_id,
            FavoritePicto.picto_id == picto_id,
        )
    )
    existing = list(result.scalars().all())
    if existing:
        for favorite in existing:
            await db.delete(favorite)
        is_favorite = False
    else:
        db.add(FavoritePicto(child_id=data.child_id, picto_id=picto_id))
        is_favorite = True

    return {
        "picto_id": picto_id,
        "child_id": data.child_id,
        "is_favorite": is_favorite,
    }


async def _ensure_pictogram_access(
    db: AsyncSession,
    picto_id: int,
    child_id: int,
    parent_id: int,
    lock: bool = False,
) -> None:
    statement = select(Pictogram.id).where(
        Pictogram.id == picto_id,
        _pictogram_access_clause(parent_id, child_id),
    )
    if lock:
        statement = statement.with_for_update()
    pictogram_result = await db.execute(statement)
    if pictogram_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pictogramme introuvable.",
        )


async def set_favorite(
    db: AsyncSession,
    picto_id: int,
    data: SetFavoriteRequest,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)
    await _ensure_pictogram_access(
        db,
        picto_id,
        data.child_id,
        parent_id,
        lock=True,
    )
    result = await db.execute(
        select(FavoritePicto).where(
            FavoritePicto.child_id == data.child_id,
            FavoritePicto.picto_id == picto_id,
        )
    )
    existing = list(result.scalars().all())
    if data.is_favorite and not existing:
        db.add(FavoritePicto(child_id=data.child_id, picto_id=picto_id))
    elif not data.is_favorite:
        for favorite in existing:
            await db.delete(favorite)

    return {
        "picto_id": picto_id,
        "child_id": data.child_id,
        "is_favorite": data.is_favorite,
    }


async def get_favorites(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(Pictogram)
        .distinct()
        .join(FavoritePicto, FavoritePicto.picto_id == Pictogram.id)
        .where(
            FavoritePicto.child_id == child_id,
            _pictogram_access_clause(parent_id, child_id),
        )
        .order_by(Pictogram.label)
    )
    return [
        _pictogram_payload(pictogram, {pictogram.id})
        for pictogram in result.scalars().all()
    ]


async def _validate_sentence_pictograms(
    db: AsyncSession,
    picto_ids: Iterable[int],
    child_id: int,
    parent_id: int,
) -> None:
    unique_ids = set(picto_ids)
    if not unique_ids:
        return
    result = await db.execute(
        select(Pictogram.id).where(
            Pictogram.id.in_(unique_ids),
            _pictogram_access_clause(parent_id, child_id),
        )
    )
    if set(result.scalars().all()) != unique_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Un pictogramme de la phrase est introuvable.",
        )


async def generate_speech(
    db: AsyncSession,
    data: SpeechRequest,
    parent_id: int,
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)
    await _validate_sentence_pictograms(
        db,
        data.picto_ids,
        data.child_id,
        parent_id,
    )

    audio_dir = Path(settings.STORAGE_PATH) / "audio" / "tts"
    audio_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.mp3"
    filepath = audio_dir / filename
    tts = gTTS(text=data.sentence_text, lang="fr", slow=False)
    await asyncio.to_thread(tts.save, str(filepath))

    audio_url = f"/storage/audio/tts/{filename}"
    history = SentenceHistory(
        child_id=data.child_id,
        sentence_pictos=data.picto_ids,
        sentence_text=data.sentence_text,
        audio_url=audio_url,
    )
    db.add(history)
    await db.flush()
    return {
        "sentence_text": data.sentence_text,
        "audio_url": audio_url,
    }


def rank_suggestion_ids(
    histories: Iterable[Iterable[int]],
    previous_picto_id: int | None,
    limit: int,
) -> list[int]:
    sequences = [list(sequence) for sequence in histories]
    scores: Counter[int] = Counter()
    sequence_count = len(sequences)
    for recency_index, sequence in enumerate(sequences):
        weight = max(1, sequence_count - recency_index)
        if previous_picto_id is None:
            for picto_id in sequence:
                scores[picto_id] += weight
            continue
        for index, picto_id in enumerate(sequence[:-1]):
            if picto_id == previous_picto_id:
                scores[sequence[index + 1]] += weight

    if previous_picto_id is not None:
        scores.pop(previous_picto_id, None)
    return [
        picto_id
        for picto_id, _ in sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
    ]


async def get_suggestions(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
    previous_picto_id: int | None,
    limit: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    history_result = await db.execute(
        select(SentenceHistory.sentence_pictos)
        .where(SentenceHistory.child_id == child_id)
        .order_by(SentenceHistory.created_at.desc())
        .limit(100)
    )
    histories = [
        [int(value) for value in (sequence or [])]
        for sequence in history_result.scalars().all()
    ]
    ranked_ids = rank_suggestion_ids(histories, previous_picto_id, limit)

    favorite_ids = await _favorite_ids(db, child_id)
    fallback_ids = list(favorite_ids)
    candidate_result = await db.execute(
        select(Pictogram)
        .where(_pictogram_access_clause(parent_id, child_id))
        .order_by(Pictogram.is_default.asc(), Pictogram.label)
    )
    candidates = list(candidate_result.scalars().all())
    by_id = {pictogram.id: pictogram for pictogram in candidates}

    ordered_ids = []
    for picto_id in [*ranked_ids, *fallback_ids, *by_id]:
        if picto_id == previous_picto_id:
            continue
        if picto_id in by_id and picto_id not in ordered_ids:
            ordered_ids.append(picto_id)
        if len(ordered_ids) >= limit:
            break

    return [
        _pictogram_payload(by_id[picto_id], favorite_ids)
        for picto_id in ordered_ids
    ]


async def get_history(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(SentenceHistory)
        .where(SentenceHistory.child_id == child_id)
        .order_by(SentenceHistory.created_at.desc())
        .limit(50)
    )
    return [
        {
            "id": history.id,
            "child_id": history.child_id,
            "sentence_pictos": history.sentence_pictos or [],
            "sentence_text": history.sentence_text,
            "audio_url": history.audio_url,
            "created_at": str(history.created_at),
        }
        for history in result.scalars().all()
    ]


def validate_image_signature(content: bytes, content_type: str) -> bool:
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
) -> PictogramMedia:
    content_type = upload.content_type or ""
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Format accepté : JPEG, PNG ou WebP.",
        )

    content = await upload.read(MAX_PICTOGRAM_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier image est vide.",
        )
    if len(content) > MAX_PICTOGRAM_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="L’image ne doit pas dépasser 8 Mo.",
        )
    if not validate_image_signature(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le contenu du fichier image est invalide.",
        )

    existing_result = await db.execute(
        select(PictogramMedia).where(
            PictogramMedia.owner_id == parent_id,
            PictogramMedia.client_uuid == client_uuid,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    owner_directory = PRIVATE_MEDIA_ROOT / str(parent_id)
    owner_directory.mkdir(parents=True, exist_ok=True)
    file_path = owner_directory / f"{uuid.uuid4().hex}{extension}"
    async with aiofiles.open(file_path, "wb") as output:
        await output.write(content)

    media = PictogramMedia(
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
) -> PictogramMedia:
    media = await _get_owned_media(db, media_id, parent_id)
    if media is None or not Path(media.file_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image introuvable.",
        )
    return media


async def _delete_private_media_if_unused(
    db: AsyncSession,
    media_id: int,
    parent_id: int,
    excluding_picto_id: int,
) -> None:
    media_url = f"/pictos/media/{media_id}"
    usage_result = await db.execute(
        select(Pictogram.id).where(
            Pictogram.image_url == media_url,
            Pictogram.id != excluding_picto_id,
        )
    )
    if usage_result.first() is not None:
        return
    media = await _get_owned_media(db, media_id, parent_id)
    if media is None:
        return
    try:
        Path(media.file_path).unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(media)

import os
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from gtts import gTTS
from app.config import settings
from app.modules.children.models import Child
from .models import PictoCategory, Pictogram, FavoritePicto, SentenceHistory
from .schemas import SpeechRequest, ToggleFavoriteRequest


# ─── Vérifier que l'enfant appartient au parent connecté ─────────
async def _check_child_ownership(db: AsyncSession, child_id: int, parent_id: int) -> None:
    result = await db.execute(select(Child).where(Child.id == child_id))
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enfant introuvable.")
    if child.parent_id != parent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")


# ─── Catégories ──────────────────────────────────────────────────
async def get_categories(db: AsyncSession) -> list[PictoCategory]:
    result = await db.execute(
        select(PictoCategory).order_by(PictoCategory.order)
    )
    return list(result.scalars().all())


# ─── Pictogrammes ────────────────────────────────────────────────
async def get_all_pictos(db: AsyncSession, child_id: int) -> list[dict]:
    result = await db.execute(select(Pictogram).order_by(Pictogram.label))
    pictos = result.scalars().all()
    return await _attach_favorites(db, list(pictos), child_id)


async def get_pictos_by_category(db: AsyncSession, category_id: int, child_id: int) -> list[dict]:
    result = await db.execute(
        select(Pictogram)
        .where(Pictogram.category_id == category_id)
        .order_by(Pictogram.label)
    )
    pictos = result.scalars().all()
    return await _attach_favorites(db, list(pictos), child_id)


async def _attach_favorites(db: AsyncSession, pictos: list, child_id: int) -> list[dict]:
    """Ajoute le champ is_favorite à chaque pictogramme."""
    fav_result = await db.execute(
        select(FavoritePicto.picto_id).where(FavoritePicto.child_id == child_id)
    )
    fav_ids = set(fav_result.scalars().all())

    enriched = []
    for p in pictos:
        d = {
            "id": p.id,
            "category_id": p.category_id,
            "label": p.label,
            "image_url": p.image_url,
            "audio_url": p.audio_url,
            "is_default": p.is_default,
            "is_favorite": p.id in fav_ids,
        }
        enriched.append(d)
    return enriched


# ─── Favoris ─────────────────────────────────────────────────────
async def toggle_favorite(
    db: AsyncSession, picto_id: int, data: ToggleFavoriteRequest, parent_id: int
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)

    result = await db.execute(
        select(FavoritePicto).where(
            FavoritePicto.child_id == data.child_id,
            FavoritePicto.picto_id == picto_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        return {"picto_id": picto_id, "child_id": data.child_id, "is_favorite": False}
    else:
        fav = FavoritePicto(child_id=data.child_id, picto_id=picto_id)
        db.add(fav)
        return {"picto_id": picto_id, "child_id": data.child_id, "is_favorite": True}


async def get_favorites(db: AsyncSession, child_id: int, parent_id: int) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(Pictogram)
        .join(FavoritePicto, FavoritePicto.picto_id == Pictogram.id)
        .where(FavoritePicto.child_id == child_id)
        .order_by(Pictogram.label)
    )
    pictos = result.scalars().all()
    return [
        {
            "id": p.id,
            "category_id": p.category_id,
            "label": p.label,
            "image_url": p.image_url,
            "audio_url": p.audio_url,
            "is_default": p.is_default,
            "is_favorite": True,
        }
        for p in pictos
    ]


# ─── Synthèse vocale (gTTS) ───────────────────────────────────────
async def generate_speech(
    db: AsyncSession, data: SpeechRequest, parent_id: int
) -> dict:
    await _check_child_ownership(db, data.child_id, parent_id)

    # Générer le fichier audio avec gTTS
    audio_dir = os.path.join(settings.STORAGE_PATH, "audio", "tts")
    os.makedirs(audio_dir, exist_ok=True)

    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(audio_dir, filename)

    tts = gTTS(text=data.sentence_text, lang="fr", slow=False)
    tts.save(filepath)

    audio_url = f"/storage/audio/tts/{filename}"

    # Sauvegarder dans l'historique
    history = SentenceHistory(
        child_id=data.child_id,
        sentence_pictos=data.picto_ids,
        sentence_text=data.sentence_text,
        audio_url=audio_url,
    )
    db.add(history)
    await db.flush()

    return {"sentence_text": data.sentence_text, "audio_url": audio_url}


# ─── Historique ──────────────────────────────────────────────────
async def get_history(db: AsyncSession, child_id: int, parent_id: int) -> list:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(SentenceHistory)
        .where(SentenceHistory.child_id == child_id)
        .order_by(SentenceHistory.created_at.desc())
        .limit(50)
    )
    histories = result.scalars().all()
    return [
        {
            "id": h.id,
            "child_id": h.child_id,
            "sentence_pictos": h.sentence_pictos,
            "sentence_text": h.sentence_text,
            "audio_url": h.audio_url,
            "created_at": str(h.created_at),
        }
        for h in histories
    ]
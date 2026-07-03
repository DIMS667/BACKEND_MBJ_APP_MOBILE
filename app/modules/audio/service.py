import os
import mimetypes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from app.config import settings
from .models import AudioCategory, AudioFile


# ─── Catégories ──────────────────────────────────────────────────
async def get_categories(db: AsyncSession) -> list:
    result = await db.execute(
        select(AudioCategory).order_by(AudioCategory.id)
    )
    return list(result.scalars().all())


# ─── Liste des fichiers audio ────────────────────────────────────
async def get_all_files(db: AsyncSession) -> list:
    result = await db.execute(
        select(AudioFile)
        .options(selectinload(AudioFile.category))
        .order_by(AudioFile.category_id, AudioFile.id)
    )
    return list(result.scalars().all())


async def get_files_by_category(
    db: AsyncSession, category_name: str
) -> list:
    result = await db.execute(
        select(AudioFile)
        .options(selectinload(AudioFile.category))
        .join(AudioCategory)
        .where(AudioCategory.name == category_name)
        .order_by(AudioFile.id)
    )
    return list(result.scalars().all())


async def get_file_by_id(db: AsyncSession, audio_id: int) -> AudioFile:
    result = await db.execute(
        select(AudioFile)
        .options(selectinload(AudioFile.category))
        .where(AudioFile.id == audio_id)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier audio introuvable."
        )
    return file


# ─── Streaming audio ─────────────────────────────────────────────
async def stream_audio(db: AsyncSession, audio_id: int):
    """
    Stream un fichier audio local.
    Permet la lecture progressive sans charger tout le fichier en mémoire.
    CDC : lecture déclenchée en moins de 500ms.
    """
    audio = await get_file_by_id(db, audio_id)

    if not audio.is_local:
        # Fichier distant : redirection directe
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": audio.file_url}
        )

    # ✅ removeprefix au lieu de lstrip
    relative_path = audio.file_url.removeprefix("/storage/")
    filepath = os.path.join(settings.STORAGE_PATH, relative_path)

    # Debug : afficher le chemin cherché
    print(f"🔍 Chemin audio cherché : {filepath}")
    print(f"🔍 Fichier existe : {os.path.exists(filepath)}")

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier audio non trouvé : {filepath}"
        )

    # Détecter le type MIME
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type:
        mime_type = "audio/mpeg"

    # Streaming par chunks pour performance
    def iterfile():
        with open(filepath, "rb") as f:
            while chunk := f.read(1024 * 64):  # chunks de 64KB
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type=mime_type,
        headers={
            "Content-Disposition": f"inline; filename={os.path.basename(filepath)}",
            "Accept-Ranges": "bytes",
        }
    )
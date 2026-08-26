import logging
import os
import re
import mimetypes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse, FileResponse
from app.config import settings
from app.core.cache import cached
from .models import AudioCategory, AudioFile

logger = logging.getLogger("app.audio")

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
_STREAM_CHUNK_BYTES = 64 * 1024


# ─── Catégories ──────────────────────────────────────────────────
async def get_categories(db: AsyncSession) -> list:
    async def _load():
        result = await db.execute(
            select(AudioCategory).order_by(AudioCategory.id)
        )
        return list(result.scalars().all())
    return await cached("audio:categories", _load)


# ─── Liste des fichiers audio ────────────────────────────────────
async def get_all_files(db: AsyncSession) -> list:
    async def _load():
        result = await db.execute(
            select(AudioFile)
            .options(selectinload(AudioFile.category))
            .order_by(AudioFile.category_id, AudioFile.id)
        )
        return list(result.scalars().all())
    return await cached("audio:all", _load)


async def get_files_by_category(
    db: AsyncSession, category_name: str
) -> list:
    async def _load():
        result = await db.execute(
            select(AudioFile)
            .options(selectinload(AudioFile.category))
            .join(AudioCategory)
            .where(AudioCategory.name == category_name)
            .order_by(AudioFile.id)
        )
        return list(result.scalars().all())
    return await cached(f"audio:by_category:{category_name}", _load)


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
async def stream_audio(db: AsyncSession, audio_id: int, request: Request):
    """
    Stream un fichier audio local, avec support des requêtes Range
    (206 Partial Content) pour permettre le seek/scrub côté lecteur audio
    sans retélécharger tout le fichier à chaque déplacement.
    CDC : lecture déclenchée en moins de 500ms.
    """
    audio = await get_file_by_id(db, audio_id)

    if not audio.is_local:
        # Fichier distant : redirection directe
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": audio.file_url}
        )

    relative_path = audio.file_url.removeprefix("/storage/")
    filepath = os.path.join(settings.STORAGE_PATH, relative_path)

    if not os.path.exists(filepath):
        logger.warning("Fichier audio introuvable : %s", filepath)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier audio non trouvé : {filepath}"
        )

    mime_type, _ = mimetypes.guess_type(filepath)
    mime_type = mime_type or "audio/mpeg"
    file_size = os.path.getsize(filepath)

    start, end = 0, file_size - 1
    range_header = request.headers.get("range")
    if range_header:
        match = _RANGE_RE.match(range_header)
        if match:
            start_str, end_str = match.groups()
            if start_str:
                start = int(start_str)
            if end_str:
                end = min(int(end_str), file_size - 1)
            if start > end:
                raise HTTPException(
                    status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                    headers={"Content-Range": f"bytes */{file_size}"},
                )

    chunk_length = end - start + 1

    def iterfile():
        with open(filepath, "rb") as f:
            f.seek(start)
            remaining = chunk_length
            while remaining > 0:
                chunk = f.read(min(_STREAM_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Disposition": f"inline; filename={os.path.basename(filepath)}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_length),
    }

    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        return StreamingResponse(
            iterfile(), status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=mime_type, headers=headers,
        )

    return StreamingResponse(iterfile(), media_type=mime_type, headers=headers)
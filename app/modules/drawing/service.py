import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.children.models import Child

from .models import Drawing

MAX_DRAWING_IMAGE_BYTES = 6 * 1024 * 1024
DRAWINGS_ROOT = (
    Path(settings.STORAGE_PATH).resolve().parent
    / "private_storage"
    / "drawings"
)


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


def _drawing_payload(drawing: Drawing) -> dict:
    return {
        "id": drawing.id,
        "child_id": drawing.child_id,
        "template_key": drawing.template_key,
        "title": drawing.title,
        "image_url": f"/drawing/media/{drawing.id}",
        "created_at": str(drawing.created_at),
    }


async def list_gallery(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> list[dict]:
    await _check_child_ownership(db, child_id, parent_id)
    result = await db.execute(
        select(Drawing)
        .where(Drawing.child_id == child_id)
        .order_by(Drawing.created_at.desc())
    )
    return [_drawing_payload(d) for d in result.scalars().all()]


def _validate_png(content: bytes) -> None:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier doit être une image PNG.",
        )


async def save_drawing(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
    image: UploadFile,
    template_key: Optional[str],
    title: Optional[str],
) -> dict:
    await _check_child_ownership(db, child_id, parent_id)

    content = await image.read(MAX_DRAWING_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le dessin est vide.",
        )
    if len(content) > MAX_DRAWING_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Le dessin ne doit pas dépasser 6 Mo.",
        )
    _validate_png(content)

    child_directory = DRAWINGS_ROOT / str(child_id)
    child_directory.mkdir(parents=True, exist_ok=True)
    file_path = child_directory / f"{uuid.uuid4().hex}.png"
    async with aiofiles.open(file_path, "wb") as output:
        await output.write(content)

    drawing = Drawing(
        child_id=child_id,
        template_key=template_key,
        title=title,
        image_url=str(file_path),
    )
    db.add(drawing)
    await db.flush()
    return _drawing_payload(drawing)


async def get_drawing_media(
    db: AsyncSession,
    drawing_id: int,
    parent_id: int,
) -> Drawing:
    result = await db.execute(select(Drawing).where(Drawing.id == drawing_id))
    drawing = result.scalar_one_or_none()
    if drawing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dessin introuvable.",
        )
    await _check_child_ownership(db, drawing.child_id, parent_id)
    if not Path(drawing.image_url).is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image introuvable.",
        )
    return drawing


async def delete_drawing(
    db: AsyncSession,
    drawing_id: int,
    parent_id: int,
) -> None:
    result = await db.execute(select(Drawing).where(Drawing.id == drawing_id))
    drawing = result.scalar_one_or_none()
    if drawing is None:
        return
    await _check_child_ownership(db, drawing.child_id, parent_id)
    try:
        Path(drawing.image_url).unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(drawing)
    await db.flush()

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.modules.auth.models import User

from . import service
from .schemas import DrawingResponse

router = APIRouter()


@router.get("/gallery/{child_id}", response_model=List[DrawingResponse])
async def get_gallery(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.list_gallery(db, child_id, current_user.id)


@router.post("/save", response_model=DrawingResponse)
async def save_drawing(
    child_id: int = Form(...),
    template_key: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.save_drawing(
        db, child_id, current_user.id, image, template_key, title
    )


@router.get("/media/{drawing_id}")
async def get_media(
    drawing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    drawing = await service.get_drawing_media(db, drawing_id, current_user.id)
    return FileResponse(drawing.image_url, media_type="image/png")


@router.delete("/{drawing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drawing(
    drawing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_drawing(db, drawing_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

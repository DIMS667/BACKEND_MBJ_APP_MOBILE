from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.modules.auth.models import User

from . import service
from .schemas import (
    CLIENT_UUID_PATTERN,
    CustomCategoryUpsert,
    CustomPictogramUpsert,
    PictoCategoryResponse,
    PictogramMediaResponse,
    PictogramResponse,
    SetFavoriteRequest,
    SentenceHistoryResponse,
    SpeechRequest,
    SpeechResponse,
    ToggleFavoriteRequest,
    ToggleFavoriteResponse,
)


router = APIRouter()


@router.get("/categories", response_model=List[PictoCategoryResponse])
async def get_categories(
    child_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_categories(db, child_id, current_user.id)


@router.put(
    "/categories/custom/sync",
    response_model=PictoCategoryResponse,
)
async def sync_custom_category(
    data: CustomCategoryUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.upsert_custom_category(db, data, current_user.id)


@router.delete(
    "/categories/custom/{client_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_custom_category(
    client_uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_custom_category(db, client_uuid, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/", response_model=List[PictogramResponse])
async def get_all_pictos(
    child_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_all_pictos(db, child_id, current_user.id)


@router.get(
    "/category/{category_id}",
    response_model=List[PictogramResponse],
)
async def get_pictos_by_category(
    category_id: int,
    child_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_pictos_by_category(
        db,
        category_id,
        child_id,
        current_user.id,
    )


@router.put("/custom/sync", response_model=PictogramResponse)
async def sync_custom_pictogram(
    data: CustomPictogramUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.upsert_custom_pictogram(db, data, current_user.id)


@router.delete(
    "/custom/{client_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_custom_pictogram(
    client_uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_custom_pictogram(db, client_uuid, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/media", response_model=PictogramMediaResponse)
async def upload_pictogram_media(
    image: UploadFile = File(...),
    client_uuid: str = Form(
        ...,
        min_length=12,
        max_length=64,
        pattern=CLIENT_UUID_PATTERN,
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = await service.save_private_media(
        db,
        image,
        client_uuid,
        current_user.id,
    )
    return PictogramMediaResponse(
        id=media.id,
        client_uuid=media.client_uuid,
        media_url=f"/pictos/media/{media.id}",
        content_type=media.content_type,
    )


@router.get("/media/{media_id}")
async def get_pictogram_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = await service.get_private_media(db, media_id, current_user.id)
    return FileResponse(
        media.file_path,
        media_type=media.content_type,
        filename=media.original_name,
    )


@router.get(
    "/suggestions/{child_id}",
    response_model=List[PictogramResponse],
)
async def get_suggestions(
    child_id: int,
    previous_picto_id: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=6, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_suggestions(
        db,
        child_id,
        current_user.id,
        previous_picto_id,
        limit,
    )


@router.post(
    "/{picto_id}/favorite",
    response_model=ToggleFavoriteResponse,
)
async def toggle_favorite(
    picto_id: int,
    data: ToggleFavoriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.toggle_favorite(
        db,
        picto_id,
        data,
        current_user.id,
    )


@router.put(
    "/{picto_id}/favorite",
    response_model=ToggleFavoriteResponse,
)
async def set_favorite(
    picto_id: int,
    data: SetFavoriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.set_favorite(
        db,
        picto_id,
        data,
        current_user.id,
    )


@router.get(
    "/favorites/{child_id}",
    response_model=List[PictogramResponse],
)
async def get_favorites(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_favorites(db, child_id, current_user.id)


@router.post("/speech", response_model=SpeechResponse)
async def generate_speech(
    data: SpeechRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.generate_speech(db, data, current_user.id)


@router.get(
    "/history/{child_id}",
    response_model=List[SentenceHistoryResponse],
)
async def get_history(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_history(db, child_id, current_user.id)

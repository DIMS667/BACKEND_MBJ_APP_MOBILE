from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.modules.auth.models import User

from . import service
from .schemas import (
    ChildStoriesProgressResponse,
    CustomStoryUpsert,
    StoryDetailResponse,
    StoryFavoriteRequest,
    StoryFavoriteResponse,
    StoryMediaResponse,
    StoryProgressCreate,
    StoryProgressResponse,
    StoryResponse,
)


router = APIRouter()


@router.get("/", response_model=list[StoryResponse])
async def get_stories(
    category: Optional[str] = Query(default=None, max_length=40),
    difficulty: Optional[int] = Query(default=None, ge=1, le=3),
    child_id: Optional[int] = Query(default=None, gt=0),
    favorites_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_all_stories(
        db,
        current_user.id,
        category,
        difficulty,
        child_id,
        favorites_only,
    )


@router.get(
    "/progress/{child_id}",
    response_model=ChildStoriesProgressResponse,
)
async def get_child_progress(
    child_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_child_progress(db, child_id, current_user.id)


@router.put("/custom/sync", response_model=StoryDetailResponse)
async def sync_custom_story(
    data: CustomStoryUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.upsert_custom_story(db, data, current_user.id)


@router.delete("/custom/{client_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_story(
    client_uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_custom_story(db, client_uuid, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/media", response_model=StoryMediaResponse)
async def upload_story_media(
    image: UploadFile = File(...),
    client_uuid: str = Form(..., min_length=12, max_length=64),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = await service.save_private_media(
        db,
        image,
        client_uuid,
        current_user.id,
    )
    return StoryMediaResponse(
        id=media.id,
        client_uuid=media.client_uuid,
        media_url=f"/stories/media/{media.id}",
        content_type=media.content_type,
    )


@router.get("/media/{media_id}")
async def get_story_media(
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


@router.post("/{story_id}/progress", response_model=StoryProgressResponse)
async def save_progress(
    story_id: int,
    data: StoryProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.save_progress(db, story_id, data, current_user.id)


@router.put("/{story_id}/favorite", response_model=StoryFavoriteResponse)
async def set_story_favorite(
    story_id: int,
    data: StoryFavoriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.set_favorite(
        db,
        story_id,
        data.child_id,
        data.is_favorite,
        current_user.id,
    )


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story(
    story_id: int,
    child_id: Optional[int] = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_story_detail(
        db,
        story_id,
        current_user.id,
        child_id,
    )

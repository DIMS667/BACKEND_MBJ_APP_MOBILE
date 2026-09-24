from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.modules.auth.models import User

from . import service
from .schemas import (
    ChildStoriesProgressResponse,
    PublicStoryDetailResponse,
    PublicStoryResponse,
    StoryDetailResponse,
    StoryFavoriteRequest,
    StoryFavoriteResponse,
    StoryProgressCreate,
    StoryProgressResponse,
    StoryResponse,
)


router = APIRouter()


@router.get("/public", response_model=list[PublicStoryResponse])
async def get_public_stories(
    category: Optional[str] = Query(default=None, max_length=40),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_public_stories(db, category)


@router.get("/public/{story_id}", response_model=PublicStoryDetailResponse)
async def get_public_story_detail(
    story_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_public_story_detail(db, story_id)


@router.get("/", response_model=list[StoryResponse])
async def get_stories(
    category: Optional[str] = Query(default=None, max_length=40),
    child_id: Optional[int] = Query(default=None, gt=0),
    favorites_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_all_stories(
        db,
        current_user.id,
        category,
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

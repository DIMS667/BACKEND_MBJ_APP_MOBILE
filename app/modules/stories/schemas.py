from pydantic import BaseModel
from typing import Optional, List


# ─── Page ────────────────────────────────────────────────────────
class StoryPageResponse(BaseModel):
    id: int
    story_id: int
    page_number: int
    text: str
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    animation_type: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Histoire (liste) ─────────────────────────────────────────────
class StoryResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    category: str
    difficulty_level: int
    is_offline_available: bool
    total_pages: int

    model_config = {"from_attributes": True}


# ─── Histoire (détail complet avec pages) ────────────────────────
class StoryDetailResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    category: str
    difficulty_level: int
    is_offline_available: bool
    total_pages: int
    pages: List[StoryPageResponse] = []

    model_config = {"from_attributes": True}


# ─── Progression ─────────────────────────────────────────────────
class StoryProgressCreate(BaseModel):
    child_id: int
    last_page: int
    is_completed: bool = False


class StoryProgressResponse(BaseModel):
    id: int
    story_id: int
    child_id: int
    last_page: int
    is_completed: bool
    read_count: int

    model_config = {"from_attributes": True}


# ─── Progression globale enfant ───────────────────────────────────
class ChildStoriesProgressResponse(BaseModel):
    child_id: int
    total_stories: int
    completed_stories: int
    in_progress_stories: int
    progress: List[StoryProgressResponse]
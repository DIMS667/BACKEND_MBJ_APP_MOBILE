from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class StoryChoiceInput(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    pictogram_url: Optional[str] = Field(default=None, max_length=500)
    next_page_number: int = Field(ge=1, le=30)
    sort_order: int = Field(default=0, ge=0, le=10)


class StoryChoiceResponse(StoryChoiceInput):
    id: int

    model_config = {"from_attributes": True}


class StoryPageInput(BaseModel):
    page_number: int = Field(ge=1, le=30)
    text: str = Field(min_length=2, max_length=500)
    image_url: Optional[str] = Field(default=None, max_length=500)
    pictogram_url: Optional[str] = Field(default=None, max_length=500)
    audio_url: Optional[str] = Field(default=None, max_length=500)
    animation_type: str = Field(default="fade", pattern="^(fade|slide|none)$")
    local_page_key: Optional[str] = Field(default=None, max_length=64)
    next_page_number: Optional[int] = Field(default=None, ge=1, le=30)
    choices: list[StoryChoiceInput] = Field(default_factory=list, max_length=3)


class StoryPageResponse(BaseModel):
    id: int
    story_id: int
    page_number: int
    text: str
    image_url: Optional[str] = None
    pictogram_url: Optional[str] = None
    audio_url: Optional[str] = None
    animation_type: str = "fade"
    local_page_key: Optional[str] = None
    next_page_number: Optional[int] = None
    choices: list[StoryChoiceResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StoryResponse(BaseModel):
    id: int
    title: str
    description: str = ""
    cover_url: str = ""
    category: str
    is_offline_available: bool
    total_pages: int
    is_custom: bool = False
    owner_id: Optional[int] = None
    child_id: Optional[int] = None
    client_uuid: Optional[str] = None
    is_favorite: bool = False

    model_config = {"from_attributes": True}


class StoryDetailResponse(StoryResponse):
    pages: list[StoryPageResponse] = Field(default_factory=list)


class CustomStoryUpsert(BaseModel):
    client_uuid: str = Field(min_length=12, max_length=64)
    child_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    category: str = Field(min_length=2, max_length=40)
    cover_url: Optional[str] = Field(default=None, max_length=500)
    pages: list[StoryPageInput] = Field(min_length=2, max_length=30)

    @model_validator(mode="after")
    def validate_story_graph(self):
        numbers = sorted(page.page_number for page in self.pages)
        expected = list(range(1, len(self.pages) + 1))
        if numbers != expected:
            raise ValueError("Les pages doivent être numérotées sans interruption.")

        for page in self.pages:
            if page.next_page_number is not None and (
                page.next_page_number <= page.page_number
                or page.next_page_number > len(self.pages)
            ):
                raise ValueError("La page suivante configurée est invalide.")
            for choice in page.choices:
                if choice.next_page_number <= page.page_number:
                    raise ValueError(
                        "Un choix doit mener vers une page suivante pour éviter les boucles."
                    )
                if choice.next_page_number > len(self.pages):
                    raise ValueError("Un choix pointe vers une page inexistante.")
        return self


class StoryProgressCreate(BaseModel):
    child_id: int = Field(gt=0)
    last_page: int = Field(ge=1, le=30)
    is_completed: bool = False
    selected_choices: dict[str, str] = Field(default_factory=dict)


class StoryProgressResponse(BaseModel):
    id: int
    story_id: int
    child_id: int
    last_page: int
    is_completed: bool
    read_count: int
    selected_choices: dict[str, str] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChildStoriesProgressResponse(BaseModel):
    child_id: int
    total_stories: int
    completed_stories: int
    in_progress_stories: int
    progress: list[StoryProgressResponse]


class StoryFavoriteRequest(BaseModel):
    child_id: int = Field(gt=0)
    is_favorite: bool


class StoryFavoriteResponse(BaseModel):
    story_id: int
    child_id: int
    is_favorite: bool


class StoryMediaResponse(BaseModel):
    id: int
    client_uuid: str
    media_url: str
    content_type: str


class StorySyncSummary(BaseModel):
    story: StoryDetailResponse
    server_state: dict[str, Any] = Field(default_factory=dict)

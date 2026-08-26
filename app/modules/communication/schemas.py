from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


CLIENT_UUID_PATTERN = r"^[A-Za-z0-9._-]+$"


class PictoCategoryResponse(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    color: str
    order: int
    is_default: bool = True
    child_id: Optional[int] = None
    client_uuid: Optional[str] = None

    model_config = {"from_attributes": True}


class CustomCategoryUpsert(BaseModel):
    client_uuid: str = Field(
        min_length=12,
        max_length=64,
        pattern=CLIENT_UUID_PATTERN,
    )
    child_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=50)
    color: str = Field(
        default="#4A90D9",
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class PictogramResponse(BaseModel):
    id: int
    category_id: int
    label: str
    image_url: str
    audio_url: str = ""
    is_default: bool
    is_favorite: bool = False
    child_id: Optional[int] = None
    client_uuid: Optional[str] = None

    model_config = {"from_attributes": True}


class CustomPictogramUpsert(BaseModel):
    client_uuid: str = Field(
        min_length=12,
        max_length=64,
        pattern=CLIENT_UUID_PATTERN,
    )
    child_id: int = Field(gt=0)
    category_id: int = Field(gt=0)
    label: str = Field(min_length=2, max_length=80)
    image_url: str = Field(min_length=1, max_length=500)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("image_url")
    @classmethod
    def validate_private_image_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/pictos/media/"):
            raise ValueError("Une image privée valide est requise.")
        return normalized


class PictogramMediaResponse(BaseModel):
    id: int
    client_uuid: str
    media_url: str
    content_type: str


class ToggleFavoriteRequest(BaseModel):
    child_id: int = Field(gt=0)


class SetFavoriteRequest(ToggleFavoriteRequest):
    is_favorite: bool


class ToggleFavoriteResponse(BaseModel):
    picto_id: int
    child_id: int
    is_favorite: bool


class SpeechRequest(BaseModel):
    child_id: int = Field(gt=0)
    picto_ids: List[int] = Field(default_factory=list, max_length=30)
    sentence_text: str = Field(min_length=1, max_length=500)

    @field_validator("sentence_text")
    @classmethod
    def normalize_sentence(cls, value: str) -> str:
        return " ".join(value.strip().split())


class SpeechResponse(BaseModel):
    sentence_text: str
    audio_url: str


class SentenceHistoryResponse(BaseModel):
    id: int
    child_id: int
    sentence_pictos: List[int]
    sentence_text: str
    audio_url: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}

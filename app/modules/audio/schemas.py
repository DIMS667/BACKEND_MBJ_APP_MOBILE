from pydantic import BaseModel
from typing import Optional, List


# ─── Catégorie ───────────────────────────────────────────────────
class AudioCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Fichier audio ───────────────────────────────────────────────
class AudioFileResponse(BaseModel):
    id: int
    category_id: int
    title: str
    file_url: str
    duration_seconds: Optional[int] = None
    language: str
    is_local: bool
    category: AudioCategoryResponse

    model_config = {"from_attributes": True}


# ─── Liste avec catégorie ────────────────────────────────────────
class AudioListResponse(BaseModel):
    total: int
    files: List[AudioFileResponse]
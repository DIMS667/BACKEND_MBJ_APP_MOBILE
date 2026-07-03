from pydantic import BaseModel
from typing import Optional, List


# ─── Catégorie ───────────────────────────────────────────────────
class PictoCategoryResponse(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    color: str
    order: int

    model_config = {"from_attributes": True}


# ─── Pictogramme ─────────────────────────────────────────────────
class PictogramResponse(BaseModel):
    id: int
    category_id: int
    label: str
    image_url: str
    audio_url: Optional[str] = None
    is_default: bool
    is_favorite: bool = False  # calculé dynamiquement

    model_config = {"from_attributes": True}


# ─── Favoris ─────────────────────────────────────────────────────
class ToggleFavoriteRequest(BaseModel):
    child_id: int


class ToggleFavoriteResponse(BaseModel):
    picto_id: int
    child_id: int
    is_favorite: bool


# ─── Synthèse vocale ─────────────────────────────────────────────
class SpeechRequest(BaseModel):
    child_id: int
    picto_ids: List[int]      # IDs des pictos dans l'ordre
    sentence_text: str        # texte de la phrase construite


class SpeechResponse(BaseModel):
    sentence_text: str
    audio_url: str


# ─── Historique ──────────────────────────────────────────────────
class SentenceHistoryResponse(BaseModel):
    id: int
    child_id: int
    sentence_pictos: List[int]
    sentence_text: str
    audio_url: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ─── Emotion ─────────────────────────────────────────────────────
class EmotionResponse(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    color: str
    is_positive: bool

    model_config = {"from_attributes": True}


# ─── Enregistrement ──────────────────────────────────────────────
class EmotionRecordCreate(BaseModel):
    child_id: int
    emotion_id: int
    context: Optional[str] = None


class EmotionRecordResponse(BaseModel):
    id: int
    child_id: int
    emotion_id: int
    context: Optional[str] = None
    created_at: datetime
    emotion: EmotionResponse

    model_config = {"from_attributes": True}


# ─── Statistiques ────────────────────────────────────────────────
class EmotionStatItem(BaseModel):
    emotion_name: str
    color: str
    count: int
    percentage: float


class EmotionStatsResponse(BaseModel):
    child_id: int
    total_records: int
    period_days: int
    stats: List[EmotionStatItem]
    most_frequent: Optional[str] = None


# ─── Activités apaisantes ────────────────────────────────────────
class CalmingActivityResponse(BaseModel):
    id: int
    name: str
    type: str
    description: Optional[str] = None
    content_url: Optional[str] = None
    duration_seconds: int
    icon_url: Optional[str] = None

    model_config = {"from_attributes": True}
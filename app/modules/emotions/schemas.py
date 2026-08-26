from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


EmotionContextKey = Literal[
    "maison",
    "ecole",
    "repas",
    "transport",
    "bruit",
    "soin",
    "jeu",
    "changement",
    "attente",
    "avec_autres",
    "seul",
    "autre",
]
EmotionIntensity = Literal["doux", "moyen", "fort"]
MAX_FUTURE_CLOCK_SKEW = timedelta(minutes=5)


def _normalize_event_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("L'horodatage doit inclure un fuseau horaire.")
    normalized = value.astimezone(timezone.utc)
    if normalized > datetime.now(timezone.utc) + MAX_FUTURE_CLOCK_SKEW:
        raise ValueError("L'horodatage ne peut pas être dans le futur.")
    return normalized


class _ClientEventBase(BaseModel):
    client_uuid: str = Field(..., min_length=8, max_length=64)
    recorded_at: datetime

    @field_validator("client_uuid")
    @classmethod
    def normalize_client_uuid(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("L'identifiant client est invalide.")
        return normalized

    @field_validator("recorded_at")
    @classmethod
    def require_utc_aware_datetime(cls, value: datetime) -> datetime:
        return _normalize_event_datetime(value)


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
    child_id: int = Field(..., gt=0)
    emotion_id: int = Field(..., gt=0)
    context: Optional[str] = Field(default=None, max_length=255)
    client_uuid: Optional[str] = Field(default=None, min_length=8, max_length=64)
    context_key: Optional[EmotionContextKey] = None
    intensity: Optional[EmotionIntensity] = None
    recorded_at: Optional[datetime] = None

    @field_validator("context", "client_uuid")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("recorded_at")
    @classmethod
    def normalize_optional_datetime(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return None
        return _normalize_event_datetime(value)


class EmotionRecordSync(_ClientEventBase):
    child_id: int = Field(..., gt=0)
    emotion_id: int = Field(..., gt=0)
    context: Optional[str] = Field(default=None, max_length=255)
    context_key: Optional[EmotionContextKey] = None
    intensity: Optional[EmotionIntensity] = None

    @field_validator("context")
    @classmethod
    def normalize_context(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class EmotionRecordResponse(BaseModel):
    id: int
    child_id: int
    emotion_id: int
    client_uuid: str
    context: Optional[str] = None
    context_key: Optional[str] = None
    intensity: Optional[EmotionIntensity] = None
    recorded_at: datetime
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
    display_order: int = 0
    is_active: bool = True
    feedback_count: int = 0
    helped_count: int = 0
    last_helped_at: Optional[datetime] = None
    personalization_score: float = 0.5
    personalized: bool = False

    model_config = {"from_attributes": True}


class CalmingFeedbackSync(_ClientEventBase):
    child_id: int = Field(..., gt=0)
    record_client_uuid: str = Field(..., min_length=8, max_length=64)
    activity_id: int = Field(..., gt=0)
    helped: bool

    @field_validator("record_client_uuid")
    @classmethod
    def normalize_record_client_uuid(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("L'identifiant de l'enregistrement est invalide.")
        return normalized


class CalmingFeedbackResponse(BaseModel):
    id: int
    client_uuid: str
    child_id: int
    emotion_record_id: int
    record_client_uuid: str
    activity_id: int
    helped: bool
    recorded_at: datetime
    created_at: datetime

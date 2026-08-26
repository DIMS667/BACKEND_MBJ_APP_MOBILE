from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


CLIENT_UUID_PATTERN = r"^[A-Za-z0-9._-]+$"


# ─── Etape ───────────────────────────────────────────────────────
class RoutineStepCreate(BaseModel):
    order: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=100)
    image_url: Optional[str] = None
    audio_url: Optional[str] = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Le titre de l’étape est requis.")
        return normalized


class RoutineStepUpdate(BaseModel):
    order: Optional[int] = None
    title: Optional[str] = None
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


class RoutineStepSync(BaseModel):
    client_uuid: str = Field(
        min_length=1,
        max_length=64,
        pattern=CLIENT_UUID_PATTERN,
    )
    title: str = Field(..., min_length=1, max_length=100)
    image_url: Optional[str] = None
    audio_url: Optional[str] = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Le titre de l’étape est requis.")
        return normalized


class RoutineStepResponse(BaseModel):
    id: int
    routine_id: int
    order: int
    title: str
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    is_completed: bool
    is_default: bool = False
    client_uuid: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Routine ─────────────────────────────────────────────────────
class RoutineCreate(BaseModel):
    child_id: int = Field(gt=0)
    title: str = Field(..., min_length=1, max_length=100)
    icon_url: Optional[str] = None
    type: Literal["custom"] = "custom"
    steps: List[RoutineStepCreate] = Field(..., min_length=1, max_length=20)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Le titre de la routine est requis.")
        return normalized

    @field_validator("steps")
    @classmethod
    def validate_step_order(
        cls,
        value: List[RoutineStepCreate],
    ) -> List[RoutineStepCreate]:
        orders = [step.order for step in value]
        if len(orders) != len(set(orders)):
            raise ValueError("Chaque étape doit avoir un ordre unique.")
        if orders and sorted(orders) != list(range(1, len(orders) + 1)):
            raise ValueError("Les étapes doivent être numérotées sans trou.")
        return value


class RoutineUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    icon_url: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def normalize_optional_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Le titre de la routine est requis.")
        return normalized


class RoutineResponse(BaseModel):
    id: int
    child_id: int
    title: str
    icon_url: Optional[str] = None
    type: str
    is_active: bool
    is_default: bool = False
    steps: List[RoutineStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ─── Session ─────────────────────────────────────────────────────
class RoutineSessionResponse(BaseModel):
    id: int
    routine_id: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    steps_completed: int
    total_steps: int
    is_completed: bool

    model_config = {"from_attributes": True}


# ─── Validation étape ────────────────────────────────────────────
class ValidateStepResponse(BaseModel):
    step_id: int
    is_completed: bool
    routine_completed: bool
    steps_completed: int
    total_steps: int
    message: str  # message bienveillant

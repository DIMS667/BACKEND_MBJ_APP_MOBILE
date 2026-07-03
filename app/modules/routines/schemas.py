from pydantic import BaseModel, Field
from typing import Optional, List


# ─── Etape ───────────────────────────────────────────────────────
class RoutineStepCreate(BaseModel):
    order: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=100)
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


class RoutineStepUpdate(BaseModel):
    order: Optional[int] = None
    title: Optional[str] = None
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


class RoutineStepResponse(BaseModel):
    id: int
    routine_id: int
    order: int
    title: str
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    is_completed: bool

    model_config = {"from_attributes": True}


# ─── Routine ─────────────────────────────────────────────────────
class RoutineCreate(BaseModel):
    child_id: int
    title: str = Field(..., min_length=1, max_length=100)
    icon_url: Optional[str] = None
    type: str = "custom"  # morning / evening / school / custom
    steps: List[RoutineStepCreate] = []


class RoutineUpdate(BaseModel):
    title: Optional[str] = None
    icon_url: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None


class RoutineResponse(BaseModel):
    id: int
    child_id: int
    title: str
    icon_url: Optional[str] = None
    type: str
    is_active: bool
    steps: List[RoutineStepResponse] = []

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
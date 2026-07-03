from pydantic import BaseModel, Field
from typing import Optional, List


# ─── Sensory Profile ────────────────────────────────────────────
class SensoryProfileBase(BaseModel):
    noise_sensitive: bool = False
    light_sensitive: bool = False
    color_sensitive: bool = False
    motion_sensitive: bool = False


class SensoryProfileCreate(SensoryProfileBase):
    pass


class SensoryProfileUpdate(SensoryProfileBase):
    pass


class SensoryProfileResponse(SensoryProfileBase):
    id: int
    child_id: int

    model_config = {"from_attributes": True}


# ─── Preferences ────────────────────────────────────────────────
class ChildPreferencesBase(BaseModel):
    favorite_activities: List[str] = []
    color_theme: str = "blue"
    avatar_id: Optional[str] = None


class ChildPreferencesCreate(ChildPreferencesBase):
    pass


class ChildPreferencesUpdate(ChildPreferencesBase):
    pass


class ChildPreferencesResponse(ChildPreferencesBase):
    id: int
    child_id: int

    model_config = {"from_attributes": True}


# ─── Child ──────────────────────────────────────────────────────
class ChildCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    age: int = Field(..., ge=1) # aucune limite
    photo_url: Optional[str] = None


class ChildUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    age: Optional[int] = Field(None, ge=3, le=12)
    photo_url: Optional[str] = None
    level: Optional[int] = None


class ChildResponse(BaseModel):
    id: int
    parent_id: int
    first_name: str
    age: int
    photo_url: Optional[str] = None
    level: int
    sensory_profile: Optional[SensoryProfileResponse] = None
    preferences: Optional[ChildPreferencesResponse] = None

    model_config = {"from_attributes": True}
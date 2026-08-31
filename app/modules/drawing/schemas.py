from typing import Optional
from pydantic import BaseModel


class DrawingResponse(BaseModel):
    id: int
    child_id: int
    template_key: Optional[str] = None
    title: Optional[str] = None
    image_url: str
    created_at: str

    model_config = {"from_attributes": True}

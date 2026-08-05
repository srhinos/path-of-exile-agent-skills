from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Flask(BaseModel):
    """Simplified flask representation for craft/analysis contexts."""

    model_config = ConfigDict(validate_assignment=True)

    slot: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base_type: str = Field(min_length=1)
    quality: int = Field(default=0, ge=0, le=30)
    mods: list[str] = []

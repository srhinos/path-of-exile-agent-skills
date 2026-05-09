from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Flask(BaseModel):
    """Simplified flask representation for craft/analysis contexts."""

    model_config = ConfigDict(validate_assignment=True)

    slot: str
    name: str
    base_type: str
    quality: int = 0
    mods: list[str] = []

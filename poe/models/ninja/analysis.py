from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SlotCost(BaseModel):
    """Cost of a single equipment slot."""

    model_config = ConfigDict(validate_assignment=True)

    slot: str
    item_name: str
    chaos_value: float = 0.0
    divine_value: float | None = None
    is_unique: bool = False


class BuildCost(BaseModel):
    """Total build cost with per-slot breakdown."""

    model_config = ConfigDict(validate_assignment=True)

    total_chaos: float = 0.0
    total_divine: float | None = None
    slots: list[SlotCost] = []
    most_expensive: SlotCost | None = None
    character_name: str = ""
    class_name: str = ""
    league: str = ""


class UpgradeSuggestion(BaseModel):
    """A suggested upgrade for a build slot."""

    model_config = ConfigDict(validate_assignment=True)

    slot: str
    current_item: str
    current_cost: float = 0.0
    suggested_item: str = ""
    suggested_cost: float = 0.0
    savings: float = 0.0

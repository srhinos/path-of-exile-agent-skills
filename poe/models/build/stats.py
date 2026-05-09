from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, Field, field_validator


class StatEntry(BaseModel):
    """A single player stat parsed from the build XML's PlayerStat elements."""

    stat: str = Field(min_length=1)
    value: float

    @field_validator("value")
    @classmethod
    def _validate_value_finite(cls, v: float) -> float:
        if not isfinite(v):
            raise ValueError("value must be finite (not NaN or +/-inf)")
        return v


class StatBlock(BaseModel):
    """Filtered collection of stats, returned by BuildService.stats().

    Category is "off", "def", or "all" — controls which stats are included.
    """

    category: str = "all"
    stats: dict[str, float] = {}


class StatDiff(BaseModel):
    """A single stat's values across two builds, with computed diff and pct change."""

    stat: str
    value1: float
    value2: float
    diff: float
    pct: float | None = None

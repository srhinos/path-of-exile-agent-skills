from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator

from poe.constants import HIT_RATE_PATTERN, VALID_AFFIXES, VALID_AFFIXES_OR_EMPTY
from poe.types import CraftMethod, MatchMode

VALID_METHODS = frozenset(CraftMethod)
VALID_MATCH_MODES = frozenset(MatchMode)


def _ensure_finite(v: float) -> float:
    if not isfinite(v):
        raise ValueError("value must be finite (not NaN or +/-inf)")
    return v


class ModWeight(BaseModel):
    """A fossil or essence modifier that scales a mod's spawn weight."""

    tag: str = Field(min_length=1)
    multiplier: float

    @field_validator("multiplier")
    @classmethod
    def _validate_multiplier(cls, v: float) -> float:
        return _ensure_finite(v)


class Mod(BaseModel):
    """A rollable mod from the mod pool.

    Returned inside ModPoolResult.mods from SimService.get_mods().
    """

    mod_id: str
    name: str
    affix: str
    group: str
    weight: int = Field(ge=0)
    tags: list[str] = []

    @field_validator("affix")
    @classmethod
    def _validate_affix(cls, v: str) -> str:
        if v not in VALID_AFFIXES:
            raise ValueError(f"affix must be 'prefix' or 'suffix', got {v!r}")
        return v


class ModTier(BaseModel):
    """A specific tier of a mod, showing ilvl requirement and stat ranges."""

    tier: int = Field(ge=1)
    ilvl: int = Field(ge=0, le=100)
    values: list = []
    weight: int = Field(default=0, ge=0)
    available: bool = True


class Fossil(BaseModel):
    """A fossil with its mod weight multipliers and blocked tags.

    Returned inside FossilListResult from SimService.get_fossils().
    """

    name: str = Field(min_length=1)
    mod_weights: dict[str, float] = {}
    blocked: list[str] = []

    @field_validator("mod_weights")
    @classmethod
    def _validate_weights_finite(cls, v: dict[str, float]) -> dict[str, float]:
        for k, val in v.items():
            if not isfinite(val):
                raise ValueError(f"mod_weights[{k!r}] must be finite, got {val!r}")
        return v


class Essence(BaseModel):
    """An essence with its guaranteed mod(s) for a base item.

    Returned inside EssenceListResult from SimService.get_essences().
    """

    name: str = Field(min_length=1)
    tier: str = ""
    mods: list[dict] = []


class BenchCraft(BaseModel):
    """A crafting bench option available for a base item."""

    name: str = Field(min_length=1)
    mod: str = ""
    cost: str = ""


class CurrencyPrices(BaseModel):
    """Currency/fossil/essence prices in chaos equivalents from poe.ninja."""

    currency: dict[str, float] = {}
    fossils: dict[str, float] = {}
    essences: dict[str, float] = {}


class IdentifiedMod(BaseModel):
    """A mod on an item matched against the crafting database."""

    text: str
    mod_id: str = ""
    tier: int = Field(default=0, ge=0)
    affix: str = ""

    @field_validator("affix")
    @classmethod
    def _validate_affix(cls, v: str) -> str:
        if v not in VALID_AFFIXES_OR_EMPTY:
            raise ValueError(f"affix must be one of {sorted(VALID_AFFIXES_OR_EMPTY)}, got {v!r}")
        return v


# --- Service response models ---


class ModPoolResult(BaseModel):
    """Response from SimService.get_mods() — rollable mods for a base item."""

    base: str
    ilvl: int
    influences: list[str] = []
    filter: str = "all"
    total_mods: int = 0
    mods: list[dict] = []


class ModTierResult(BaseModel):
    """Response from SimService.get_tiers() — tier breakdown for a mod."""

    mod_id: str
    base: str
    ilvl: int
    tiers: list[dict] = []


class FossilListResult(BaseModel):
    """Response from SimService.get_fossils()."""

    filter: str | None = None
    count: int = 0
    fossils: list[dict] = []


class EssenceListResult(BaseModel):
    """Response from SimService.get_essences()."""

    base: str = "all"
    count: int = 0
    essences: list[dict] = []


class BenchCraftListResult(BaseModel):
    """Response from SimService.get_bench_crafts()."""

    base: str
    count: int = 0
    crafts: list[dict] = []


class BaseItemSearchResult(BaseModel):
    """Response from SimService.search_bases() — matching base items."""

    query: str
    count: int = 0
    items: list[dict] = []


class SimulationResult(BaseModel):
    """Response from SimService.simulate() — full simulation with context."""

    model_config = ConfigDict(validate_assignment=True)

    base: str
    ilvl: int = Field(ge=0, le=100)
    method: str
    targets: list[str]
    fossils: list[str] | None = None
    essence: str | None = None
    match_mode: str = "all"
    iterations: int = Field(default=0, ge=0)
    hit_rate: str = ""
    avg_attempts: float | None = 0.0
    cost_per_attempt: float | None = 0.0
    avg_cost_chaos: float | None = 0.0
    percentiles: dict[str, int] = {}

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"method must be a valid CraftMethod, got {v!r}")
        return v

    @field_validator("match_mode")
    @classmethod
    def _validate_match_mode(cls, v: str) -> str:
        if v not in VALID_MATCH_MODES:
            raise ValueError(f"match_mode must be one of {sorted(VALID_MATCH_MODES)}, got {v!r}")
        return v

    @field_validator("hit_rate")
    @classmethod
    def _validate_hit_rate(cls, v: str) -> str:
        if v and not HIT_RATE_PATTERN.match(v):
            raise ValueError(f"hit_rate must match pattern N% or N.N% (e.g. '12.5%'), got {v!r}")
        return v

    @field_validator("avg_attempts", "cost_per_attempt", "avg_cost_chaos")
    @classmethod
    def _validate_finite_optional(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not isfinite(v):
            raise ValueError("value must be finite or None")
        if v < 0:
            raise ValueError("value must be non-negative")
        return v


class ItemAnalysisResult(BaseModel):
    """Response from SimService.analyze_item() — item + crafting potential.

    item contains the equipped item data, analysis contains open affix
    counts, available mods, and bench craft options.
    """

    slot: str
    item: dict = {}
    analysis: dict = {}

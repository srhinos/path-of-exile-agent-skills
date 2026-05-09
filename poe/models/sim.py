from __future__ import annotations

from pydantic import BaseModel


class ModWeight(BaseModel):
    """A fossil or essence modifier that scales a mod's spawn weight."""

    tag: str
    multiplier: float


class Mod(BaseModel):
    """A rollable mod from the mod pool.

    Returned inside ModPoolResult.mods from SimService.get_mods().
    """

    mod_id: str
    name: str
    affix: str
    group: str
    weight: int
    tags: list[str] = []


class ModTier(BaseModel):
    """A specific tier of a mod, showing ilvl requirement and stat ranges."""

    tier: int
    ilvl: int
    values: list = []
    weight: int = 0
    available: bool = True


class Fossil(BaseModel):
    """A fossil with its mod weight multipliers and blocked tags.

    Returned inside FossilListResult from SimService.get_fossils().
    """

    name: str
    mod_weights: dict[str, float] = {}
    blocked: list[str] = []


class Essence(BaseModel):
    """An essence with its guaranteed mod(s) for a base item.

    Returned inside EssenceListResult from SimService.get_essences().
    """

    name: str
    tier: str = ""
    mods: list[dict] = []


class BenchCraft(BaseModel):
    """A crafting bench option available for a base item."""

    name: str
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
    tier: int = 0
    affix: str = ""


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

    base: str
    ilvl: int
    method: str
    targets: list[str]
    fossils: list[str] | None = None
    essence: str | None = None
    match_mode: str = "all"
    iterations: int = 0
    hit_rate: str = ""
    avg_attempts: float | None = 0.0
    cost_per_attempt: float | None = 0.0
    avg_cost_chaos: float | None = 0.0
    percentiles: dict[str, int] = {}


class ItemAnalysisResult(BaseModel):
    """Response from SimService.analyze_item() — item + crafting potential.

    item contains the equipped item data, analysis contains open affix
    counts, available mods, and bench craft options.
    """

    slot: str
    item: dict = {}
    analysis: dict = {}

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from poe.models.build.tree import TreeSocket
from poe.types import Influence, Rarity

VALID_INFLUENCES: frozenset[str] = frozenset(i.value for i in Influence)
VALID_RARITIES: frozenset[str] = frozenset(r.value for r in Rarity)

_INFLUENCE_BY_CASEFOLD: dict[str, str] = {i.value.casefold(): i.value for i in Influence}
_RARITY_BY_CASEFOLD: dict[str, str] = {r.value.casefold(): r.value for r in Rarity}


def _normalize_rarity(v: str) -> str:
    if not v:
        return v
    return _RARITY_BY_CASEFOLD.get(v.casefold(), v)


def _normalize_influences(v: list[str]) -> list[str]:
    return [_INFLUENCE_BY_CASEFOLD.get(inf.casefold(), inf) for inf in v]


class ItemMod(BaseModel):
    """A single mod line on an item, parsed from PoB XML.

    Tracks mod text plus metadata flags (prefix/suffix, crafted, fractured,
    influence). Used inside Item.implicits and Item.explicits.
    """

    model_config = ConfigDict(validate_assignment=True)

    text: str
    mod_id: str = ""
    is_prefix: bool = False
    is_suffix: bool = False
    is_implicit: bool = False
    is_crafted: bool = False
    is_custom: bool = False
    is_fractured: bool = False
    is_exarch: bool = False
    is_eater: bool = False
    is_enchant: bool = False
    is_scourge: bool = False
    is_crucible: bool = False
    is_synthesis: bool = False
    is_mutated: bool = False
    tags: list[str] = []
    range_value: float | None = Field(default=None, ge=0.0, le=1.0)
    variant: str = ""

    @model_validator(mode="after")
    def _check_affix_exclusive(self) -> ItemMod:
        if self.is_prefix and self.is_suffix:
            raise ValueError("ItemMod cannot be both is_prefix and is_suffix")
        return self


class Item(BaseModel):
    """A PoB item with parsed mod structure, as stored in the build XML.

    Represents a single item in the build's item list (not yet associated
    with a slot). Parsed by xml.parser, written by xml.writer.
    Open prefix/suffix counts are computed from the slot arrays.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: int = Field(gt=0)
    text: str
    variant: str = ""
    variant_alt: str = ""
    variant_alt2: str = ""
    variant_alt3: str = ""
    variant_alt4: str = ""
    variant_alt5: str = ""
    selected_variant: int = Field(default=0, ge=0)
    rarity: str = ""
    name: str = ""
    base_type: str = ""
    influences: list[str] = []
    is_crafted: bool = False
    is_synthesised: bool = False
    is_fractured: bool = False
    is_corrupted: bool = False
    is_mirrored: bool = False
    is_split: bool = False
    has_veiled_prefix: bool = False
    has_veiled_suffix: bool = False
    quality: int = Field(default=0, ge=0, le=30)
    sockets: str = ""
    level_req: int = Field(default=0, ge=0)
    item_level: int = Field(default=0, ge=0, le=100)
    armour: int = Field(default=0, ge=0)
    evasion: int = Field(default=0, ge=0)
    energy_shield: int = Field(default=0, ge=0)
    ward: int = Field(default=0, ge=0)

    @field_validator("rarity", mode="before")
    @classmethod
    def _normalize_rarity(cls, v: str) -> str:
        return _normalize_rarity(v) if isinstance(v, str) else v

    @field_validator("influences", mode="before")
    @classmethod
    def _normalize_influences(cls, v: list[str]) -> list[str]:
        if isinstance(v, list):
            return _normalize_influences(v)
        return v

    @model_validator(mode="after")
    def _validate_rarity_and_influences(self) -> Item:
        if self.rarity and self.rarity not in VALID_RARITIES:
            raise ValueError(
                f"Invalid rarity: {self.rarity!r}. Must be one of {sorted(VALID_RARITIES)}"
            )
        for inf in self.influences:
            if inf not in VALID_INFLUENCES:
                raise ValueError(
                    f"Invalid influence: {inf!r}. Must be one of {sorted(VALID_INFLUENCES)}"
                )
        return self

    catalyst_type: str = ""
    catalyst_quality: int = Field(default=0, ge=0)
    unique_id: str = ""
    talisman_tier: int = Field(default=0, ge=0)
    cluster_jewel_skill: str = ""
    cluster_jewel_node_count: int = Field(default=0, ge=0)
    jewel_radius: str = ""
    limited_to: int = Field(default=0, ge=0)
    item_class: str = ""
    foil_type: str = ""
    prefix_slots: list[str | None] = []
    suffix_slots: list[str | None] = []
    implicits: list[ItemMod] = []
    explicits: list[ItemMod] = []
    mod_ranges: dict[str, float] = {}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def open_prefixes(self) -> int:
        return sum(1 for s in self.prefix_slots if s is None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def open_suffixes(self) -> int:
        return sum(1 for s in self.suffix_slots if s is None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def filled_prefixes(self) -> int:
        return sum(1 for s in self.prefix_slots if s is not None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def filled_suffixes(self) -> int:
        return sum(1 for s in self.suffix_slots if s is not None)


class ItemSlot(BaseModel):
    """Binds an item ID to a named equipment slot within an ItemSet."""

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(min_length=1)
    item_id: int = Field(gt=0)
    active: bool = True
    item_pb_url: str = ""


class ItemSet(BaseModel):
    """A set of slot-to-item bindings. Builds can have multiple item sets.

    Parsed from XML <ItemSet> elements. The active set is tracked by
    BuildDocument.active_item_set.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default="1", min_length=1)
    title: str = ""
    slots: list[ItemSlot] = []
    socket_id_urls: list[TreeSocket] = []
    use_second_weapon_set: bool = False


class ItemSummary(BaseModel):
    """Lightweight item view for search results and listings.

    Subset of Item fields — no mods, no prefix/suffix tracking.
    """

    model_config = ConfigDict(validate_assignment=True)

    slot: str
    name: str
    base_type: str
    rarity: str
    influences: list[str] = []
    sockets: str = ""
    quality: int = Field(default=0, ge=0, le=30)

    @field_validator("rarity", mode="before")
    @classmethod
    def _normalize_rarity(cls, v: str) -> str:
        return _normalize_rarity(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def _validate_rarity(self) -> ItemSummary:
        if self.rarity and self.rarity not in VALID_RARITIES:
            raise ValueError(
                f"Invalid rarity: {self.rarity!r}. Must be one of {sorted(VALID_RARITIES)}"
            )
        return self


class ItemSetSummary(BaseModel):
    """Summary of an item set for ItemsService.list_sets()."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    slot_count: int = 0
    active: bool = False


class ItemSetList(BaseModel):
    """Response from ItemsService.list_sets() — all item sets with active indicator."""

    model_config = ConfigDict(validate_assignment=True)

    active_item_set: str
    sets: list[ItemSetSummary] = []


class EquippedItem(Item):
    """An Item placed in a specific equipment slot.

    Inherits all Item fields and adds slot. Constructed via
    EquippedItem(slot=name, **item.model_dump()). Returned by
    ItemsService.list_items(), FlasksService.list_flasks(), etc.
    """

    slot: str


def filter_to_active_variant(item: Item) -> Item:
    """Return a copy of the item with non-active-variant mods removed.

    PoB unique items with variants (Watcher's Eye, Impresence, Combat Focus,
    etc.) store all variant mods in the item text, tagged with {variant:N}.
    Parser preserves all variants for round-trip safety. Display/analysis
    consumers should call this to see only the mods relevant to the
    selected variant.
    """
    if not item.variant and not item.selected_variant:
        return item
    selected = str(item.selected_variant) if item.selected_variant else item.variant
    alt_variants = {
        item.variant_alt,
        item.variant_alt2,
        item.variant_alt3,
        item.variant_alt4,
        item.variant_alt5,
    }
    active_variants = {selected} | {v for v in alt_variants if v}
    active_variants.discard("")
    if not active_variants:
        return item

    def _matches(mod: ItemMod) -> bool:
        if not mod.variant:
            return True
        return any(v.strip() in active_variants for v in mod.variant.split(","))

    filtered = item.model_copy(deep=True)
    filtered.explicits = [m for m in filtered.explicits if _matches(m)]
    filtered.implicits = [m for m in filtered.implicits if _matches(m)]
    return filtered


class ItemDiff(BaseModel):
    """A single field difference between two items in the same slot."""

    model_config = ConfigDict(validate_assignment=True)

    slot: str
    field: str
    old_value: str = ""
    new_value: str = ""

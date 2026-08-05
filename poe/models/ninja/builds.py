from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DefensiveStats(BaseModel):
    """Defensive stats shared between PoE1 and PoE2 characters."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    life: int = 0
    energy_shield: int = Field(0, alias="energyShield")
    mana: int = 0
    evasion_rating: int = Field(0, alias="evasionRating")
    armour: int = 0
    ward: int = 0
    strength: int = 0
    dexterity: int = 0
    intelligence: int = 0
    fire_resistance: int = Field(0, alias="fireResistance")
    cold_resistance: int = Field(0, alias="coldResistance")
    lightning_resistance: int = Field(0, alias="lightningResistance")
    chaos_resistance: int = Field(0, alias="chaosResistance")
    fire_resistance_over_cap: int = Field(0, alias="fireResistanceOverCap")
    cold_resistance_over_cap: int = Field(0, alias="coldResistanceOverCap")
    lightning_resistance_over_cap: int = Field(0, alias="lightningResistanceOverCap")
    chaos_resistance_over_cap: int = Field(0, alias="chaosResistanceOverCap")
    fire_resistance_max: int = Field(0, alias="fireResistanceMax")
    cold_resistance_max: int = Field(0, alias="coldResistanceMax")
    lightning_resistance_max: int = Field(0, alias="lightningResistanceMax")
    chaos_resistance_max: int = Field(0, alias="chaosResistanceMax")
    block_chance: int = Field(0, alias="blockChance")
    spell_block_chance: int = Field(0, alias="spellBlockChance")
    spell_suppression_chance: int = Field(0, alias="spellSuppressionChance")
    spell_dodge_chance: int = Field(0, alias="spellDodgeChance")
    endurance_charges: int = Field(0, alias="enduranceCharges")
    frenzy_charges: int = Field(0, alias="frenzyCharges")
    power_charges: int = Field(0, alias="powerCharges")
    spirit: int = 0
    physical_max_hit_taken: int = Field(0, alias="physicalMaximumHitTaken")
    fire_max_hit_taken: int = Field(0, alias="fireMaximumHitTaken")
    cold_max_hit_taken: int = Field(0, alias="coldMaximumHitTaken")
    lightning_max_hit_taken: int = Field(0, alias="lightningMaximumHitTaken")
    chaos_max_hit_taken: int = Field(0, alias="chaosMaximumHitTaken")
    lowest_max_hit_taken: int = Field(0, alias="lowestMaximumHitTaken")
    effective_health_pool: int = Field(0, alias="effectiveHealthPool")
    life_regen: int = Field(0, alias="lifeRegen")
    physical_taken_as: dict | int = Field(0, alias="physicalTakenAs")
    deflect_chance: int = Field(0, alias="deflectChance")
    movement_speed: int = Field(0, alias="movementSpeed")
    item_rarity: int = Field(0, alias="itemRarity")
    energy_shield_regen: int = Field(0, alias="energyShieldRegen")
    evade_chance: int = Field(0, alias="evadeChance")
    life_reserved: int = Field(0, alias="lifeReserved")
    mana_reserved: int = Field(0, alias="manaReserved")
    physical_damage_reduction: int = Field(0, alias="physicalDamageReduction")


class SkillDps(BaseModel):
    """DPS breakdown for a skill."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = ""
    dps: int = 0
    dot_dps: int = Field(0, alias="dotDps")
    damage_types: list[int] = Field(default_factory=list, alias="damageTypes")
    dot_damage_types: list[int] = Field(default_factory=list, alias="dotDamageTypes")
    damage: list[int] = Field(default_factory=list)


class CharacterSkillGem(BaseModel):
    """A gem within a skill group."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    name: str = ""
    level: int = 0
    quality: int = 0
    is_built_in_support: bool = Field(default=False, alias="isBuiltInSupport")
    item_data: dict = Field(default_factory=dict, alias="itemData")


class CharacterSkill(BaseModel):
    """A skill group (linked gems)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    all_gems: list[CharacterSkillGem] = Field(default_factory=list, alias="allGems")
    dps: list[SkillDps] = Field(default_factory=list)
    item_slot: int = Field(0, alias="itemSlot")


class CharacterItem(BaseModel):
    """An equipped item from poe.ninja character API."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    item_slot: int = Field(0, alias="itemSlot")
    item_data: dict = Field(default_factory=dict, alias="itemData")


class CharacterFlask(BaseModel):
    """An equipped flask."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    item_slot: int = Field(0, alias="itemSlot")
    item_data: dict = Field(default_factory=dict, alias="itemData")


class CharacterCharm(BaseModel):
    """An equipped charm (PoE2 only)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    item_slot: int = Field(0, alias="itemSlot")
    item_data: dict = Field(default_factory=dict, alias="itemData")


class CharacterJewel(BaseModel):
    """An equipped jewel."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    item_slot: int = Field(0, alias="itemSlot")
    item_data: dict = Field(default_factory=dict, alias="itemData")


class Keystone(BaseModel):
    """An allocated keystone passive."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = ""
    icon: str = ""
    stats: list[str] = Field(default_factory=list)


class Mastery(BaseModel):
    """An allocated mastery passive."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = ""
    group: str = ""


class CharacterResponse(BaseModel):
    """Unified character response for both PoE1 and PoE2."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    account: str = ""
    name: str = ""
    league: str = ""
    level: int = 0
    class_name: str = Field("", alias="class")
    base_class: str | int = Field("", alias="baseClass")
    ascendancy_class_id: str = Field("", alias="ascendancyClassId")
    ascendancy_class_name: str = Field("", alias="ascendancyClassName")
    secondary_ascendancy_class_id: str | None = Field(None, alias="secondaryAscendancyClassId")
    secondary_ascendancy_class_name: str | None = Field(None, alias="secondaryAscendancyClassName")
    defensive_stats: DefensiveStats | None = Field(None, alias="defensiveStats")
    skills: list[CharacterSkill] = Field(default_factory=list)
    items: list[CharacterItem] = Field(default_factory=list)
    flasks: list[CharacterFlask] = Field(default_factory=list)
    jewels: list[CharacterJewel] = Field(default_factory=list)
    charms: list[CharacterCharm] = Field(default_factory=list)
    # Normalized to dict regardless of whether the API sends list or dict.
    # The bare `dict | list` type previously made every consumer
    # isinstance-check or crash on the wrong shape — a schema-drift footgun.
    cluster_jewels: dict = Field(default_factory=dict, alias="clusterJewels")
    passive_selection: list[int] = Field(default_factory=list, alias="passiveSelection")
    passive_tree_name: str = Field("", alias="passiveTreeName")
    atlas_tree_name: str = Field("", alias="atlasTreeName")
    keystones: list[Keystone] = Field(default_factory=list, alias="keyStones")
    masteries: list[Mastery] = Field(default_factory=list)
    runegrafts: list[dict] = Field(default_factory=list)
    tattoos: list[dict] = Field(default_factory=list)
    bandit_choice: str | None = Field(None, alias="banditChoice")
    pantheon_major: str | None = Field(None, alias="pantheonMajor")
    pantheon_minor: str | None = Field(None, alias="pantheonMinor")
    pob_export: str = Field("", alias="pathOfBuildingExport")
    use_second_weapon_set: bool = Field(default=False, alias="useSecondWeaponSet")
    item_provided_gems: list = Field(default_factory=list, alias="itemProvidedGems")
    hashes_ex: list[int] = Field(default_factory=list, alias="hashesEx")
    economy: dict = Field(default_factory=dict)
    status: int = 0
    last_seen_utc: str = Field("", alias="lastSeenUtc")
    updated_utc: str = Field("", alias="updatedUtc")
    last_checked_utc: str = Field("", alias="lastCheckedUtc")
    # poe.ninja added these in mid-2026; the schema-drift integration
    # test surfaced them as unmodeled. Stored as opaque blobs because
    # downstream consumers don't (yet) inspect them — keep the shape
    # available so a future caller can render breakdowns. Accept either
    # list or dict; the API has sent both shapes across deploys.
    breakdown_sources: list | dict = Field(default_factory=list, alias="breakdownSources")
    stat_breakdowns: list | dict = Field(default_factory=dict, alias="statBreakdowns")

    @field_validator("cluster_jewels", mode="before")
    @classmethod
    def _normalize_cluster_jewels(cls, v: object) -> dict:
        # poe.ninja sometimes ships cluster_jewels as a list (when no jewels
        # are present) and sometimes as a dict keyed by jewel id. Normalize
        # to dict so consumers don't have to isinstance-check.
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            return {str(i): entry for i, entry in enumerate(v)}
        if v is None:
            return {}
        return {}


class TooltipMod(BaseModel):
    """A single modifier in a tooltip."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    text: str = ""
    optional: bool = False


class TooltipResponse(BaseModel):
    """Tooltip response for items, keystones, anointments, etc."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    name: str = ""
    implicit_mods: list[TooltipMod] = Field(default_factory=list, alias="implicitMods")
    explicit_mods: list[TooltipMod] = Field(default_factory=list, alias="explicitMods")
    mutated_mods: list[TooltipMod] = Field(default_factory=list, alias="mutatedMods")


class MetaSummary(BaseModel):
    """Meta overview with top builds and trends."""

    model_config = ConfigDict(validate_assignment=True)

    game: str = "poe1"
    league: str = ""
    total_builds: int = 0
    top_builds: list[dict] = Field(default_factory=list)
    rising: list[dict] = Field(default_factory=list)
    declining: list[dict] = Field(default_factory=list)


class DimensionEntry(BaseModel):
    """A resolved dimension entry with human-readable name and count."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    count: int
    percentage: float = 0.0


class ResolvedDimension(BaseModel):
    """A categorical dimension with resolved string values."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    entries: list[DimensionEntry] = Field(default_factory=list)


class IntegerRange(BaseModel):
    """A numeric stat range from search results."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    min_value: int = 0
    max_value: int = 0

    @model_validator(mode="after")
    def _check_min_le_max(self) -> Self:
        if self.min_value > self.max_value:
            msg = (
                f"IntegerRange {self.id!r} has min_value={self.min_value} > "
                f"max_value={self.max_value}; downstream percentile math would "
                "mask this with 50.0 fallback"
            )
            raise ValueError(msg)
        return self


class SearchCharacter(BaseModel):
    """A character from search results with all available stats."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    account: str
    level: int = 0
    life: int = 0
    energy_shield: int = 0
    dps: str = ""
    ehp: str = ""
    class_id: int = 0
    skills: list[str] = Field(default_factory=list)
    keystones: list[str] = Field(default_factory=list)


class SearchResults(BaseModel):
    """Parsed and resolved builds search results."""

    model_config = ConfigDict(validate_assignment=True)

    total: int = 0
    characters: list[SearchCharacter] = Field(default_factory=list)
    dimensions: list[ResolvedDimension] = Field(default_factory=list)
    integer_ranges: list[IntegerRange] = Field(default_factory=list)
    game: str = "poe1"

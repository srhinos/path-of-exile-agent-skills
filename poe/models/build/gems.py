from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Gem(BaseModel):
    """A single gem socketed in a skill group, parsed from PoB XML.

    name_spec is the display name. quality_id tracks alternate quality
    (Anomalous, Divergent, Phantasmal). skill_part and skill_minion
    select sub-skills for DPS calculations.
    """

    model_config = ConfigDict(validate_assignment=True)

    name_spec: str
    skill_id: str = ""
    gem_id: str = ""
    variant_id: str = ""
    level: int = 20
    quality: int = 0
    quality_id: str = "Default"
    enabled: bool = True
    enable_global1: bool = True
    enable_global2: bool = True
    count: int = 1
    skill_part: str = ""
    skill_part_calcs: str = ""
    skill_minion: str = ""
    skill_minion_skill: str = ""
    skill_minion_skill_calcs: str = ""
    skill_minion_item_set: str = ""
    skill_minion_item_set_calcs: str = ""
    skill_stage_count: str = ""
    skill_stage_count_calcs: str = ""
    skill_mine_count: str = ""
    skill_mine_count_calcs: str = ""


class GemGroup(BaseModel):
    """A group of linked gems forming a skill setup.

    Maps to a PoB <Skill> XML element. Returned directly by
    GemsService.list_gems(). The slot field references the equipment
    slot this skill is socketed in (if any).
    """

    model_config = ConfigDict(validate_assignment=True)

    slot: str = ""
    label: str = ""
    enabled: bool = True
    gems: list[Gem] = []
    include_in_full_dps: bool = False
    main_active_skill: int = 1
    main_active_skill_calcs: int = 0
    group_count: int = 0
    source: str = ""


class GemSet(BaseModel):
    """A named collection of gem groups (PoB supports multiple skill sets)."""

    model_config = ConfigDict(validate_assignment=True)

    id: int
    title: str = ""
    groups: list[GemGroup] = []


class SkillSetSummary(BaseModel):
    """Compact skill set info for GemsService.list_sets()."""

    model_config = ConfigDict(validate_assignment=True)

    id: int
    active: bool = False


class SkillSetList(BaseModel):
    """Response from GemsService.list_sets() — all skill sets with active indicator."""

    model_config = ConfigDict(validate_assignment=True)

    active_skill_set: int
    sets: list[SkillSetSummary] = []


class GemSummary(BaseModel):
    """Lightweight gem view for search results. Subset of Gem fields."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    level: int = 20
    quality: int = 0
    enabled: bool = True
    quality_id: str = "Default"

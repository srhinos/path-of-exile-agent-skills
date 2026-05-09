from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from poe.constants import VERSION_PATTERN
from poe.models.build.config import BuildConfig
from poe.models.build.gems import GemGroup
from poe.models.build.items import Item, ItemSet
from poe.models.build.stats import StatEntry
from poe.models.build.tree import TreeSpec


class BuildMetadata(BaseModel):
    """Lightweight build identity returned by BuildService.list_builds().

    Contains just enough to identify and describe a build file without
    parsing its full contents. Also used as the build descriptor inside
    BuildComparison.
    """

    name: str
    file_path: str = ""
    class_name: str = ""
    ascendancy: str = ""
    level: int = 1
    version: str = ""


class BuildNotes(BaseModel):
    """Notes text attached to a build, returned by BuildService.notes_get()."""

    build_name: str
    notes: str = ""


class ValidationIssue(BaseModel):
    """A single issue found during build validation.

    Severity levels: critical, high, medium. Categories include
    resistances, life_pool, defenses, attributes, flasks.
    """

    severity: str
    category: str
    message: str
    detail: str = ""


class ValidationResult(BaseModel):
    """Full result from BuildService.validate(), wrapping all issues found."""

    build: str
    issues: list[ValidationIssue] = []
    issue_count: int = 0


class MutationResult(BaseModel):
    """Generic response from any write operation (create, delete, edit, etc.).

    Common fields cover clone-on-write tracking. Per-operation fields
    (path, deleted, item_id, etc.) are passed as extras via ConfigDict.
    Used by all services for mutation returns.
    """

    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    warning: str | None = None
    cloned_from: str | None = None
    working_copy: str | None = None


class BuildDocument(BaseModel):
    """Complete parsed PoB build — the central domain object.

    Produced by xml.parser.parse_build_file(). Contains all build data:
    character info, passive tree specs, skill gems, items, config, and
    cached player stats. Returned directly by BuildService.analyze().
    """

    class_name: str = ""
    ascend_class_name: str = ""
    level: int = Field(default=1, ge=1, le=100)
    bandit: str | None = None
    view_mode: str = "TREE"
    target_version: str = "3_0"
    main_socket_group: int = 1
    pantheon_major: str = ""
    pantheon_minor: str = ""
    character_level_auto_mode: bool = False
    spectres: list[str] = []
    timeless_data: dict = {}
    minion_stats: list[StatEntry] = []
    full_dps_skills: list[dict] = []
    player_stats: list[StatEntry] = []
    active_spec: int = Field(default=1, ge=1)

    @field_validator("target_version")
    @classmethod
    def _validate_target_version(cls, v: str) -> str:
        if not VERSION_PATTERN.match(v):
            raise ValueError(f"target_version must match X_Y format (e.g. '3_25'), got {v!r}")
        return v

    specs: list[TreeSpec] = []
    active_skill_set: int = 1
    default_gem_level: int = 0
    default_gem_quality: int = 0
    sort_gems_by_dps: bool = False
    sort_gems_by_dps_field: str = ""
    show_alt_quality_gems: bool = False
    show_support_gem_types: str = ""
    show_legacy_gems: bool = False
    skill_set_titles: dict[int, str] = {}
    skill_groups: list[GemGroup] = []
    skill_set_ids: list[int] = []
    skill_sets: dict[int, list[GemGroup]] = {}
    items: list[Item] = []
    active_item_set: str = "1"
    items_use_second_weapon_set: bool = False
    items_show_stat_differences: bool = False
    item_sets: list[ItemSet] = []
    active_config_set: str = "1"
    config_sets: list[BuildConfig] = []
    notes: str = ""
    import_link: str = ""
    import_last_realm: str = ""
    import_last_character_hash: str = ""
    import_last_account_hash: str = ""
    import_export_party: str = ""
    passthrough_sections: dict[str, str] = {}

    def get_stat(self, name: str) -> float | None:
        for s in self.player_stats:
            if s.stat == name:
                return s.value
        return None

    def get_active_spec(self) -> TreeSpec | None:
        idx = self.active_spec - 1
        if 0 <= idx < len(self.specs):
            return self.specs[idx]
        return self.specs[-1] if self.specs else None

    def get_active_config(self) -> BuildConfig | None:
        for cs in self.config_sets:
            if cs.id == self.active_config_set:
                return cs
        return self.config_sets[0] if self.config_sets else None

    def get_equipped_items(self, item_set_id: str | None = None) -> list[tuple[str, Item]]:
        """Return (slot_name, Item) pairs for the active (or specified) item set."""
        item_map = {i.id: i for i in self.items}
        target_id = item_set_id or self.active_item_set
        target_set = None
        for s in self.item_sets:
            if s.id == target_id:
                target_set = s
                break
        if not target_set and self.item_sets:
            target_set = self.item_sets[0]
        if not target_set:
            return []
        return [
            (slot.name, item_map[slot.item_id])
            for slot in target_set.slots
            if slot.item_id and slot.item_id in item_map
        ]


class BuildComparison(BaseModel):
    """Side-by-side stat and config comparison of two builds.

    Returned by BuildService.compare(). stat_comparison maps stat names
    to per-build values and diff. config_diff shows only differing keys.
    """

    build1: BuildMetadata
    build2: BuildMetadata
    stat_comparison: dict[str, dict] = {}
    config_diff: dict[str, dict] = {}

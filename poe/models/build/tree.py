from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from poe.constants import VERSION_PATTERN


class MasteryMapping(BaseModel):
    """A mastery effect selection: which effect is chosen on which node."""

    model_config = ConfigDict(validate_assignment=True)

    node_id: int = Field(ge=0)
    effect_id: int = Field(ge=0)


class TreeSocket(BaseModel):
    """A jewel socket on the passive tree, binding a node to an item.

    item_id == 0 represents an empty socket (node has a jewel slot but
    nothing socketed).
    """

    model_config = ConfigDict(validate_assignment=True)

    node_id: int = Field(ge=0)
    item_id: int = Field(ge=0)


class TreeOverride(BaseModel):
    """A passive node overridden by a cluster jewel or timeless jewel."""

    model_config = ConfigDict(validate_assignment=True)

    node_id: int
    name: str
    icon: str = ""
    text: str = ""
    effect_image: str = ""


class TreeSpec(BaseModel):
    """A passive tree allocation stored in the build XML.

    Builds can have multiple specs (up to 16 in PoB). Each spec tracks
    allocated nodes, mastery choices, jewel sockets, and tree version.
    Parsed by xml.parser, written by xml.writer.
    """

    model_config = ConfigDict(validate_assignment=True)

    title: str = ""
    tree_version: str = ""
    nodes: list[int] = []
    url: str = ""
    class_id: int = Field(default=0, ge=0)
    ascend_class_id: int = Field(default=0, ge=0)
    secondary_ascend_class_id: int = 0
    mastery_effects: list[MasteryMapping] = []
    sockets: list[TreeSocket] = []
    overrides: list[TreeOverride] = []

    @field_validator("nodes")
    @classmethod
    def _validate_nodes_unique(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError("nodes must be unique")
        return v

    @field_validator("mastery_effects")
    @classmethod
    def _dedupe_mastery_effects(cls, v: list[MasteryMapping]) -> list[MasteryMapping]:
        seen: set[int] = set()
        result: list[MasteryMapping] = []
        for m in v:
            if m.node_id in seen:
                continue
            seen.add(m.node_id)
            result.append(m)
        return result

    @field_validator("tree_version")
    @classmethod
    def _validate_tree_version(cls, v: str) -> str:
        if v and not VERSION_PATTERN.match(v):
            raise ValueError(f"tree_version must match X_Y format (e.g. '3_25'), got {v!r}")
        return v


class TreeSummary(BaseModel):
    """Compact spec info for TreeService.get_specs() listings.

    Intentionally lighter than TreeSpec — no node lists or mastery details,
    just enough to show in a spec picker.
    """

    index: int = Field(ge=1)
    title: str
    tree_version: str = ""
    node_count: int = Field(default=0, ge=0)
    class_id: int = 0
    ascend_class_id: int = 0
    active: bool = False


class TreeSpecList(BaseModel):
    """Response from TreeService.get_specs() — all specs with active indicator."""

    active_spec: int
    specs: list[TreeSummary] = []


class TreeDetail(TreeSpec):
    """Full spec detail returned by TreeService.get_tree().

    Inherits all TreeSpec fields and adds context: which spec index this
    is and the computed node count.
    """

    spec_index: int
    node_count: int = 0


class TreeComparison(BaseModel):
    """Node-level diff between two builds, returned by TreeService.compare_trees().

    Splits nodes into build1-only, build2-only, and shared sets.
    Also diffs mastery selections and class/ascendancy choices.
    """

    build1_only: list[int] = []
    build2_only: list[int] = []
    shared: list[int] = []
    build1_count: int = Field(default=0, ge=0)
    build2_count: int = Field(default=0, ge=0)
    mastery_diff: dict = {}
    class_diff: dict = {}


class TreeDiff(BaseModel):
    """Directional diff (added/removed) between two tree specs."""

    added_nodes: list[int] = []
    removed_nodes: list[int] = []
    added_masteries: list[MasteryMapping] = []
    removed_masteries: list[MasteryMapping] = []

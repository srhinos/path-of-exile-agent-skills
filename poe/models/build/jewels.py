from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from poe.models.build.items import EquippedItem


class Jewel(BaseModel):
    """A jewel's tree socket binding, used during XML parsing.

    Maps a tree node to an item ID. Lighter than EquippedJewel —
    only tracks the binding, not the full item data.
    """

    model_config = ConfigDict(validate_assignment=True)

    node_id: int = Field(ge=0)
    item_id: int = Field(gt=0)
    name: str = ""
    base_type: str = ""
    rarity: str = ""
    mods: list[str] = []


class EquippedJewel(EquippedItem):
    """A jewel equipped in a build, with its passive tree socket location.

    Inherits all Item fields via EquippedItem(Item) and adds tree_node
    for the passive tree socket it occupies. Returned inside
    JewelListResult from JewelsService.list_jewels().
    """

    tree_node: int | None = None


class JewelListResult(BaseModel):
    """Response from JewelsService.list_jewels() — jewels split by type.

    Regular jewels (Crimson, Viridian, Cobalt, Prismatic, etc.) are in
    jewels. Cluster jewels (Large/Medium/Small) are in cluster_jewels.
    """

    model_config = ConfigDict(validate_assignment=True)

    jewels: list[EquippedJewel] = []
    cluster_jewels: list[EquippedJewel] = []

from __future__ import annotations

import re

CLAUDE_SUBFOLDER = "Claude"
POB_XML_EXTENSION = ".xml"
MIN_SEARCH_TERM_LENGTH = 2

VERSION_PATTERN = re.compile(r"^\d+_\d+$")
HIT_RATE_PATTERN = re.compile(r"^\d+(\.\d+)?%$")

PERCENTAGE_MAX = 100

VALID_AFFIXES = frozenset({"prefix", "suffix"})
VALID_AFFIXES_OR_EMPTY = frozenset({"", "prefix", "suffix", "implicit"})

VALID_CONFIG_INPUT_TYPES: frozenset[str] = frozenset({"boolean", "number", "string"})

NINJA_LEAGUE_LIST_KEYS: tuple[str, ...] = (
    "economy_leagues",
    "old_economy_leagues",
    "build_leagues",
    "old_build_leagues",
    "leagues",
    "old_leagues",
)

ITEM_INT_FIELD_BOUNDS: dict[str, tuple[int, int | None]] = {
    "armour": (0, None),
    "evasion": (0, None),
    "energy_shield": (0, None),
    "ward": (0, None),
    # Quality caps at 50 to cover corrupted/imbued items (Hillock can roll
    # +10 over base 30; perfect catalysts and corrupt-implicit catalyst
    # items push past 30). Round-tripping a real PoB export with quality > 30
    # would silently truncate to 30 if the cap stayed there.
    "quality": (0, 50),
    "level_req": (0, None),
    "item_level": (0, 100),
    "catalyst_quality": (0, None),
    "talisman_tier": (0, None),
    "cluster_jewel_node_count": (0, None),
    "limited_to": (0, None),
}

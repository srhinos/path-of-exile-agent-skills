from __future__ import annotations

import re

from poe.types import Rarity

DEFAULT_ILVL = 84
DEFAULT_ITERATIONS = 10000
DEFAULT_MAX_ATTEMPTS = 1000
DEFAULT_WORKERS = 4

# Pre-compiled regexes used by data._normalize_stat_template to collapse
# stat-translation templates and user queries into the same comparable key.
STAT_TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{\d+\}")
STAT_TEMPLATE_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")
STAT_TEMPLATE_NON_ALNUM_RE = re.compile(r"[^a-z0-9# ]+")
STAT_TEMPLATE_WHITESPACE_RE = re.compile(r"\s+")

ESSENCE_TIER_PREFIXES: dict[str, int] = {
    "whispering": 1,
    "muttering": 2,
    "weeping": 3,
    "wailing": 4,
    "screaming": 5,
    "shrieking": 6,
    "deafening": 7,
}

RESONATOR_BY_SOCKETS: dict[int, tuple[str, int]] = {
    1: ("Primitive Alchemical Resonator", 1),
    2: ("Potent Alchemical Resonator", 2),
    3: ("Powerful Alchemical Resonator", 5),
    4: ("Prime Alchemical Resonator", 10),
}
MAX_RESONATOR_SOCKETS = 4

FOSSIL_WEIGHT_DIVISOR = 100

INFLUENCE_TAG_MAP: dict[str, str] = {
    "shaper": "Shaper",
    "elder": "Elder",
    "crusader": "Crusader",
    "adjudicator": "Warlord",
    "basilisk": "Hunter",
    "eyrie": "Redeemer",
}

# Eldritch influences (Searing Exarch, Eater of Worlds) are added via
# eldritch implicits, not via spawn-weight tags. They are valid Influence
# enum values but get_mod_pool() must skip them — there are no
# {tag}_searing_exarch spawn-weight entries in mods.json.
ELDRITCH_INFLUENCES: frozenset[str] = frozenset({"Searing Exarch", "Eater of Worlds"})

# RePoE base_items.json tags 2h axes only as ("axe", "two_hand_weapon", ...),
# but mods.json spawn-weights use "2h_axe_shaper" etc. The pipeline strips
# the influence suffix and looks up the residual in base_tags — without
# these derivations the four namespaces below never resolve onto bases,
# making conqueror-influence weapon mods unrollable on their intended
# weapon types (700+ mod/base pairs).
WEAPON_CLASS_DERIVED_TAGS: dict[str, tuple[str, ...]] = {
    "Two Hand Axe": ("2h_axe",),
    "Two Hand Mace": ("2h_mace",),
    "Two Hand Sword": ("2h_sword",),
    "Rune Dagger": ("rune_dagger",),
}

MAX_PREFIXES_BY_CLASS: dict[str, int] = {
    "Jewel": 2,
    "AbyssJewel": 2,
    "Flask": 1,
}
MAX_SUFFIXES_BY_CLASS: dict[str, int] = {
    "Jewel": 2,
    "AbyssJewel": 2,
    "Flask": 1,
}
DEFAULT_MAX_PREFIXES = 3
DEFAULT_MAX_SUFFIXES = 3

CURRENCY_PATH_NAMES: dict[str, str] = {
    "Metadata/Items/Currency/CurrencyUpgradeToMagic": "Orb of Transmutation",
    "Metadata/Items/Currency/CurrencyRerollMagic": "Orb of Alteration",
    "Metadata/Items/Currency/CurrencyRerollRare": "Chaos Orb",
    "Metadata/Items/Currency/CurrencyAddModToRare": "Exalted Orb",
    "Metadata/Items/Currency/CurrencyConvertToNormal": "Orb of Scouring",
    "Metadata/Items/Currency/CurrencyCorrupt": "Vaal Orb",
    "Metadata/Items/Currency/CurrencyDivine": "Divine Orb",
    "Metadata/Items/Currency/CurrencyUpgradeToRare": "Orb of Alchemy",
    "Metadata/Items/Currency/CurrencyUpgradeMagicToRare": "Regal Orb",
    "Metadata/Items/Currency/CurrencyRerollImplicit": "Blessed Orb",
    "Metadata/Items/Currency/CurrencyRemoveMod": "Orb of Annulment",
    "Metadata/Items/Currency/CurrencyMirror": "Mirror of Kalandra",
    "Metadata/Items/Currency/CurrencyUpgradeRandomly": "Orb of Chance",
    "Metadata/Items/Currency/CurrencyRerollSocketNumbers": "Jeweller's Orb",
    "Metadata/Items/Currency/CurrencyRerollSocketColours": "Chromatic Orb",
    "Metadata/Items/Currency/CurrencyRerollSocketLinks": "Orb of Fusing",
    "Metadata/Items/Currency/CurrencyGemQuality": "Gemcutter's Prism",
    "Metadata/Items/Currency/CurrencyFlaskQuality": "Glassblower's Bauble",
    "Metadata/Items/Currency/CurrencyMapQuality": "Cartographer's Chisel",
    "Metadata/Items/Currency/CurrencyPassiveRefund": "Orb of Regret",
    "Metadata/Items/Currency/CurrencyAddModToMagic": "Orb of Augmentation",
    "Metadata/Items/Currency/CurrencyArmourQuality": "Armourer's Scrap",
    "Metadata/Items/Currency/CurrencyModValues": "Divine Orb",
}

# Method → rarity-it-produces. Values use the Rarity enum (uppercase) so
# this dict and the multistep gate share a single namespace with the
# rest of the codebase. A future refactor that swaps a comparison to use
# Rarity.RARE would silently break a free-form lowercase namespace.
RARITY_PRODUCED: dict[str, Rarity] = {
    "chaos": Rarity.RARE,
    "alchemy": Rarity.RARE,
    "fossil": Rarity.RARE,
    "harvest": Rarity.RARE,
    "alt": Rarity.MAGIC,
    "transmutation": Rarity.MAGIC,
    "scour": Rarity.NORMAL,
}

RARITY_REQUIRED: dict[str, Rarity] = {
    "regal": Rarity.MAGIC,
    "augmentation": Rarity.MAGIC,
    "exalt": Rarity.RARE,
}

MOD_DOMAIN_FOR_BASE_DOMAIN: dict[str, frozenset[str]] = {
    "item": frozenset({"item", "crafted", "unveiled", "delve"}),
    "flask": frozenset({"flask"}),
    "abyss_jewel": frozenset({"abyss_jewel"}),
    "affliction_jewel": frozenset({"affliction_jewel", "misc"}),
    "misc": frozenset({"misc"}),
}

RECOMBINATOR_TRANSFER_CHANCE = 0.5
TAINTED_OUTCOME_CHANCE = 0.5
VALUE_RANGE_LENGTH = 2

PLAYER_ITEM_DOMAINS = frozenset(
    {
        "item",
        "crafted",
        "flask",
        "abyss_jewel",
        "affliction_jewel",
        "misc",
        "unveiled",
        "delve",
        "watchstone",
        "heist_trinket",
    }
)

INFLUENCE_SUFFIXES: frozenset[str] = frozenset(INFLUENCE_TAG_MAP)

BASE_ITEM_DOMAINS = frozenset(
    {
        "item",
        "flask",
        "abyss_jewel",
        "affliction_jewel",
        "misc",
    }
)

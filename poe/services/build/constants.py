from __future__ import annotations

import re

STALE_STATS_WARNING = (
    "PlayerStats are stale until the build is recalculated in PoB or via 'poe build engine load'."
)

CLASS_IDS: dict[str, int] = {
    "Scion": 0,
    "Marauder": 1,
    "Ranger": 2,
    "Witch": 3,
    "Duelist": 4,
    "Templar": 5,
    "Shadow": 6,
}

CLASS_ID_TO_NAME: dict[int, str] = {v: k for k, v in CLASS_IDS.items()}

ASCENDANCY_IDS: dict[str, tuple[int, int]] = {
    "Ascendant": (0, 1),
    "Juggernaut": (1, 1),
    "Berserker": (1, 2),
    "Chieftain": (1, 3),
    "Raider": (2, 1),
    "Deadeye": (2, 2),
    "Pathfinder": (2, 3),
    "Necromancer": (3, 1),
    "Elementalist": (3, 2),
    "Occultist": (3, 3),
    "Slayer": (4, 1),
    "Gladiator": (4, 2),
    "Champion": (4, 3),
    "Inquisitor": (5, 1),
    "Hierophant": (5, 2),
    "Guardian": (5, 3),
    "Assassin": (6, 1),
    "Trickster": (6, 2),
    "Saboteur": (6, 3),
    "Warden": (2, 4),
    "Reliquarian": (3, 4),
}

ASCENDANCY_ID_TO_NAME: dict[tuple[int, int], str] = {v: k for k, v in ASCENDANCY_IDS.items()}
ASCENDANCY_ID_TO_NAME[(0, 0)] = ""

VALID_BANDITS: frozenset[str] = frozenset({"None", "Alira", "Kraityn", "Oak"})

VALID_PANTHEON_MAJOR: frozenset[str] = frozenset(
    {
        "",
        "None",
        "TheBrineKing",
        "Lunaris",
        "Solaris",
        "Arakaali",
    }
)

VALID_PANTHEON_MINOR: frozenset[str] = frozenset(
    {
        "",
        "None",
        "Abberath",
        "Garukhan",
        "Gruthkul",
        "Yugul",
        "Shakari",
        "Tukohama",
        "Ralakesh",
        "Ryslatha",
    }
)

DEFAULT_TREE_VERSION = "3_28"

RES_CAP = 75
HP_CRITICAL = 2500
HP_LOW = 3500
SUPPRESS_CAP = 100
BLOCK_THRESHOLD = 30
SPELL_BLOCK_THRESHOLD = 20
FLASK_SLOTS = 5
ACCURACY_LOW = 90
AILMENT_IMMUNITY_CAP = 100
STUN_AVOIDANCE_PARTIAL = 50
OVERCAPPED_RES_THRESHOLD = 109
MOVE_SPEED_LOW = 0
MAX_CHARACTER_LEVEL = 100
BASE64_PAD = 4

GEAR_SLOTS = ("Helmet", "Body Armour", "Gloves", "Boots", "Amulet", "Ring 1", "Ring 2", "Belt")

FLASK_SLOT_NAMES: tuple[str, ...] = ("Flask 1", "Flask 2", "Flask 3", "Flask 4", "Flask 5")

POB_CONFIG_KEYS: dict[str, dict[str, str]] = {
    "useFrenzyCharges": {"type": "boolean", "desc": "Enable Frenzy Charges"},
    "usePowerCharges": {"type": "boolean", "desc": "Enable Power Charges"},
    "useEnduranceCharges": {"type": "boolean", "desc": "Enable Endurance Charges"},
    "conditionLowLife": {"type": "boolean", "desc": "Are you on Low Life?"},
    "conditionFullLife": {"type": "boolean", "desc": "Are you on Full Life?"},
    "conditionLowMana": {"type": "boolean", "desc": "Are you on Low Mana?"},
    "conditionFullEnergyShield": {"type": "boolean", "desc": "Are you on Full Energy Shield?"},
    "conditionLeeching": {"type": "boolean", "desc": "Are you Leeching?"},
    "conditionUsingFlask": {"type": "boolean", "desc": "Do you have a Flask active?"},
    "conditionOnConsecratedGround": {"type": "boolean", "desc": "Are you on Consecrated Ground?"},
    "conditionFocused": {"type": "boolean", "desc": "Are you Focused?"},
    "conditionOnslaught": {"type": "boolean", "desc": "Do you have Onslaught?"},
    "buffUnholyMight": {"type": "boolean", "desc": "Do you have Unholy Might?"},
    "buffPhasing": {"type": "boolean", "desc": "Do you have Phasing?"},
    "buffFortify": {"type": "boolean", "desc": "Do you have Fortify?"},
    "buffTailwind": {"type": "boolean", "desc": "Do you have Tailwind?"},
    "buffElusive": {"type": "boolean", "desc": "Do you have Elusive?"},
    "enemyCondNearbyRareCruiser": {"type": "boolean", "desc": "Is the enemy near a Rare/Unique?"},
    "enemyIsBoss": {"type": "string", "desc": "Boss type (None, Boss, Shaper, Uber)"},
    "enemyPhysicalHitDamage": {"type": "number", "desc": "Enemy physical hit damage"},
    "enemyLevel": {"type": "number", "desc": "Enemy level"},
    "enemyColdResist": {"type": "number", "desc": "Enemy cold resistance"},
    "enemyFireResist": {"type": "number", "desc": "Enemy fire resistance"},
    "enemyLightningResist": {"type": "number", "desc": "Enemy lightning resistance"},
    "enemyChaosResist": {"type": "number", "desc": "Enemy chaos resistance"},
    "enemyCondHexproof": {"type": "boolean", "desc": "Is the enemy Hexproof?"},
}

CONFIG_PRESETS: dict[str, dict[str, str | bool | float]] = {
    "mapping": {
        "useFrenzyCharges": True,
        "usePowerCharges": True,
        "useEnduranceCharges": True,
        "conditionOnslaught": True,
        "conditionUsingFlask": True,
        "enemyIsBoss": "None",
    },
    "boss": {
        "useFrenzyCharges": True,
        "usePowerCharges": True,
        "enemyIsBoss": "Boss",
        "conditionUsingFlask": True,
    },
    "sirus": {
        "useFrenzyCharges": True,
        "usePowerCharges": True,
        "enemyIsBoss": "Sirus",
        "conditionUsingFlask": True,
        "enemyPhysicalHitDamage": 5000.0,
    },
    "shaper": {
        "useFrenzyCharges": True,
        "usePowerCharges": True,
        "enemyIsBoss": "Shaper",
        "conditionUsingFlask": True,
    },
}

JEWEL_BASE_TYPES: frozenset[str] = frozenset(
    {
        "Cobalt Jewel",
        "Crimson Jewel",
        "Viridian Jewel",
        "Prismatic Jewel",
        "Murderous Eye Jewel",
        "Searching Eye Jewel",
        "Hypnotic Eye Jewel",
        "Ghastly Eye Jewel",
        "Large Cluster Jewel",
        "Medium Cluster Jewel",
        "Small Cluster Jewel",
        "Timeless Jewel",
    }
)

SLOT_TYPE_MAP: dict[str, list[str]] = {
    "weapon": ["Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap"],
    "armour": ["Helmet", "Body Armour", "Gloves", "Boots"],
    "jewellery": ["Amulet", "Ring 1", "Ring 2", "Belt"],
    "flask": ["Flask 1", "Flask 2", "Flask 3", "Flask 4", "Flask 5"],
}

INFLUENCE_LINES: dict[str, str] = {
    "Shaper Item": "Shaper",
    "Elder Item": "Elder",
    "Crusader Item": "Crusader",
    "Hunter Item": "Hunter",
    "Redeemer Item": "Redeemer",
    "Warlord Item": "Warlord",
    "Searing Exarch Item": "Searing Exarch",
    "Eater of Worlds Item": "Eater of Worlds",
}

INFLUENCE_TO_LINE: dict[str, str] = {v: k for k, v in INFLUENCE_LINES.items()}

METADATA_PREFIXES = (
    "Crafted:",
    "Prefix:",
    "Suffix:",
    "Quality:",
    "Sockets:",
    "LevelReq:",
    "Implicits:",
    "Armour:",
    "ArmourBasePercentile:",
    "Evasion:",
    "EvasionBasePercentile:",
    "Energy Shield:",
    "EnergyShieldBasePercentile:",
    "Ward:",
    "WardBasePercentile:",
    "Variant:",
    "Selected Variant:",
    "Has Variant:",
    "Has Alt Variant",
    "Selected Alt Variant",
    "AltVariant:",
    "League:",
    "{variant:",
    "Catalyst:",
    "CatalystQuality:",
    "Item Level:",
    "Unique ID:",
    "Talisman Tier:",
    "Cluster Jewel Skill:",
    "Cluster Jewel Node Count:",
    "Radius:",
    "Limited to:",
    "Item Class:",
    "Foil Unique",
    "Fractured Item",
    "Corrupted",
    "Mirrored",
    "Split",
    "Has Veiled",
    "Source:",
)

PREFIX_RE = re.compile(r"^Prefix:\s*(.*)")
SUFFIX_RE = re.compile(r"^Suffix:\s*(.*)")
SLOT_MOD_RE = re.compile(r"^\{range:([^}]*)\}(.+)$")

POB_COLOR_RE = re.compile(r"\^x[0-9A-Fa-f]{6}|\^[0-9]")

MAGIC_SUFFIX_RE = re.compile(r"\s+of\s+(?:the\s+)?\S[\w\s]*$", re.IGNORECASE)
FLASK_SIZE_PREFIXES = (
    r"(?:Divine |Eternal |Hallowed |Sanctified |Sulphur |Silver |"
    r"Grand |Greater |Large |Medium |Small |Colossal |Giant )?"
)
FLASK_TYPES = (
    r"(?:Life|Mana|Hybrid|Utility|Bismuth|Diamond|Jade|Quartz|"
    r"Granite|Basalt|Quicksilver|Stibnite|Amethyst|Ruby|Sapphire|"
    r"Topaz|Aquamarine|Gold|Iron|Silver|Sulphur) Flask"
)
FLASK_BASE_RE = re.compile(
    rf"({FLASK_SIZE_PREFIXES}{FLASK_TYPES})",
    re.IGNORECASE,
)

MOD_KEYWORD_NOISE = frozenset(
    {"base", "local", "additional", "display", "old", "new", "is", "has", "per", "while"}
)
MIN_KEYWORD_LENGTH = 3

AFFIX_NO_MATCH = object()

CATEGORY_ALIASES: dict[str, str] = {
    "offence": "off",
    "offense": "off",
    "defence": "def",
    "defense": "def",
}

ENGINE_OFF_TERMS = frozenset(
    {"DPS", "Damage", "Hit", "Crit", "Speed", "AverageHit", "AverageBurst"}
)
ENGINE_DEF_TERMS = frozenset(
    {
        "Life",
        "Mana",
        "EnergyShield",
        "Armour",
        "Evasion",
        "Resist",
        "Block",
        "Dodge",
        "Suppress",
        "EHP",
        "DamageReduction",
        "Regen",
        "Ward",
    }
)

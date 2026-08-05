from __future__ import annotations

NINJA_BASE_URL = "https://poe.ninja"
NINJA_POE1_API = f"{NINJA_BASE_URL}/poe1/api"
NINJA_POE2_API = f"{NINJA_BASE_URL}/poe2/api"
NINJA_LEGACY_API = f"{NINJA_BASE_URL}/api"

NINJA_USER_AGENT = "poe-cli/0.1.0 (+https://github.com/srhinos/poe-cli)"

NINJA_CONNECT_TIMEOUT = 10.0
NINJA_READ_TIMEOUT = 30.0
NINJA_MAX_RESPONSE_BYTES = 50 * 1024 * 1024

NINJA_RATE_LIMIT_REQUESTS = 10
NINJA_RATE_LIMIT_WINDOW = 60

NINJA_TTL_INDEX_STATE = 5 * 60
NINJA_TTL_ECONOMY = 15 * 60
NINJA_TTL_BUILDS = 30 * 60
NINJA_TTL_HISTORY = 4 * 3600
# Dictionary entries (skill-name / keystone slug → display name) are stable
# across PoE patches but not eternal; ninja occasionally re-deploys with
# corrections. 30 days is a long enough cap that disconnected use stays
# usable but a stale-forever bug can't survive a month.
NINJA_TTL_DICTIONARY = 30 * 86400

# Bumped whenever a Pydantic model schema change invalidates cached data.
# is_fresh treats a meta with a different schema_version as stale, forcing
# a refetch instead of feeding stale JSON to a strict validator that may
# now reject (or silently produce wrong defaults for) the old shape.
NINJA_CACHE_SCHEMA_VERSION = 2

NINJA_LOW_CONFIDENCE_THRESHOLD = 5

NINJA_GAMES: frozenset[str] = frozenset({"poe1", "poe2"})

NINJA_LANGUAGES: frozenset[str] = frozenset(
    {
        "en",
        "de",
        "fr",
        "es",
        "pt",
        "ru",
        "ja",
        "zh",
    }
)

NINJA_POE1_STASH_TYPES: frozenset[str] = frozenset(
    {
        "BaseType",
        "Beast",
        "BlightedMap",
        "BlightRavagedMap",
        "ClusterJewel",
        "ForbiddenJewel",
        "Incubator",
        "IncursionTemple",
        "Invitation",
        "Map",
        "Memory",
        "ShrineBelt",
        "SkillGem",
        "UniqueAccessory",
        "UniqueArmour",
        "UniqueFlask",
        "UniqueJewel",
        "UniqueMap",
        "UniqueRelic",
        "UniqueTincture",
        "UniqueWeapon",
        "ValdoMap",
        "Vial",
        "Wombgift",
    }
)

NINJA_POE1_EXCHANGE_TYPES: frozenset[str] = frozenset(
    {
        "AllflameEmber",
        "Artifact",
        "Astrolabe",
        "Currency",
        "DeliriumOrb",
        "DivinationCard",
        "DjinnCoin",
        "Essence",
        "Fossil",
        "Fragment",
        "Oil",
        "Omen",
        "Resonator",
        "Runegraft",
        "Scarab",
        "Tattoo",
    }
)

NINJA_POE1_CURRENCY_STASH_TYPES: frozenset[str] = frozenset(
    {
        "Currency",
        "Fragment",
    }
)

NINJA_POE2_EXCHANGE_TYPES: frozenset[str] = frozenset(
    {
        "Abyss",
        "Breach",
        "Currency",
        "Delirium",
        "Essences",
        "Expedition",
        "Fragments",
        "Idols",
        "LineageSupportGems",
        "Ritual",
        "Runes",
        "SoulCores",
        "UncutGems",
    }
)

NINJA_ENDPOINTS = {
    "poe1_index_state": "/poe1/api/data/index-state",
    "poe2_index_state": "/poe2/api/data/index-state",
    "poe1_build_index_state": "/poe1/api/data/build-index-state",
    "poe2_build_index_state": "/poe2/api/data/build-index-state",
    "poe1_atlas_tree_index_state": "/poe1/api/data/atlas-tree-index-state",
    "poe1_currency_overview": "/poe1/api/economy/stash/current/currency/overview",
    "poe1_item_overview": "/poe1/api/economy/stash/current/item/overview",
    "poe1_exchange_overview": "/poe1/api/economy/exchange/current/overview",
    "poe2_exchange_overview": "/poe2/api/economy/exchange/current/overview",
    "currency_history": "/poe1/api/economy/exchange/current/details",
    "item_history": "/poe1/api/economy/stash/current/item/history",
}

SIGNED_INT64_MAX = 0x7FFFFFFFFFFFFFFF
UNSIGNED_INT64_OVERFLOW = 0x10000000000000000

# A protobuf int64 varint is at most 10 bytes; each byte contributes 7
# bits of payload. shift starts at 0 and increments by 7 per continuation
# byte, so a tenth payload byte puts shift at 63 and the eleventh (which
# the spec forbids) would push shift past this ceiling.
VARINT_MAX_SHIFT_BITS = 70

WIRE_VARINT = 0
WIRE_64BIT = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_32BIT = 5

WIRE_64BIT_LEN = 8
WIRE_32BIT_LEN = 4

# HTTP retry config (was inline in client.py)
HTTP_TOO_MANY_REQUESTS = 429
HTTP_CLIENT_ERROR_MIN = 400
HTTP_SERVER_ERROR_MIN = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_GATEWAY_TIMEOUT = 504
MAX_429_RETRIES = 3
MAX_5XX_RETRIES = 2
RETRY_BASE_DELAY = 2.0
RETRYABLE_5XX: frozenset[int] = frozenset(
    {HTTP_BAD_GATEWAY, HTTP_SERVICE_UNAVAILABLE, HTTP_GATEWAY_TIMEOUT}
)

NINJA_DETAILS_BASE = "https://poe.ninja"

CURRENCY_ALIASES: dict[str, str] = {
    "chaos": "chaos orb",
    "exalted": "exalted orb",
    "exalt": "exalted orb",
    "divine": "divine orb",
    "mirror": "mirror of kalandra",
    "vaal": "vaal orb",
    "alchemy": "orb of alchemy",
    "alch": "orb of alchemy",
    "alteration": "orb of alteration",
    "alt": "orb of alteration",
    "fusing": "orb of fusing",
    "jeweller": "jeweller's orb",
    "chromatic": "chromatic orb",
    "regret": "orb of regret",
    "scouring": "orb of scouring",
    "blessed": "blessed orb",
    "regal": "regal orb",
    "annul": "orb of annulment",
    "annulment": "orb of annulment",
    "ancient": "ancient orb",
    "transmute": "orb of transmutation",
    "augment": "orb of augmentation",
    "chance": "orb of chance",
}

CRAFTING_TYPE_MAP: dict[str, list[tuple[str, str]]] = {
    "currency": [("Currency", "poe1_exchange")],
    "fossils": [("Fossil", "poe1_exchange")],
    "essences": [("Essence", "poe1_exchange")],
    "resonators": [("Resonator", "poe1_exchange")],
    "beasts": [("Beast", "poe1_stash_item")],
    "fragments": [("Fragment", "poe1_exchange")],
    "scarabs": [("Scarab", "poe1_exchange")],
    "oils": [("Oil", "poe1_exchange")],
}

TYPE_CANONICAL: dict[str, str] = {
    t.lower(): t
    for t in NINJA_POE1_CURRENCY_STASH_TYPES | NINJA_POE1_STASH_TYPES | NINJA_POE1_EXCHANGE_TYPES
}

POE2_TYPE_CANONICAL: dict[str, str] = {t.lower(): t for t in NINJA_POE2_EXCHANGE_TYPES}

HEATMAP_MANDATORY_THRESHOLD = 0.5
HEATMAP_FLEX_THRESHOLD = 0.1

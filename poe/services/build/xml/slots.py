from __future__ import annotations

# All valid PoB equipment slot names in display order.
CANONICAL_SLOTS: tuple[str, ...] = (
    "Weapon 1",
    "Weapon 2",
    "Weapon 1 Swap",
    "Weapon 2 Swap",
    "Helmet",
    "Body Armour",
    "Gloves",
    "Boots",
    "Amulet",
    "Ring 1",
    "Ring 2",
    "Belt",
    "Flask 1",
    "Flask 2",
    "Flask 3",
    "Flask 4",
    "Flask 5",
    "Tincture 1",
    "Tincture 2",
)

# Slot type category mapping.
SLOT_CATEGORIES: dict[str, list[str]] = {
    "weapon": ["Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap"],
    "armour": ["Helmet", "Body Armour", "Gloves", "Boots"],
    "jewellery": ["Amulet", "Ring 1", "Ring 2", "Belt"],
    "flask": ["Flask 1", "Flask 2", "Flask 3", "Flask 4", "Flask 5"],
    "tincture": ["Tincture 1", "Tincture 2"],
}

# Lookup: lowercased alias → canonical slot name.
_SLOT_ALIASES: dict[str, str] = {}
for _slot in CANONICAL_SLOTS:
    _SLOT_ALIASES[_slot.casefold()] = _slot
# Common shorthand aliases.
_SLOT_ALIASES.update(
    {
        "helm": "Helmet",
        "hat": "Helmet",
        "chest": "Body Armour",
        "body": "Body Armour",
        "armor": "Body Armour",
        "armour": "Body Armour",
        "ring": "Ring 1",
        "ring1": "Ring 1",
        "ring2": "Ring 2",
        "weapon": "Weapon 1",
        "weapon1": "Weapon 1",
        "weapon2": "Weapon 2",
        "mainhand": "Weapon 1",
        "offhand": "Weapon 2",
        "main hand": "Weapon 1",
        "off hand": "Weapon 2",
        "glove": "Gloves",
        "boot": "Boots",
        "amulet": "Amulet",
        "belt": "Belt",
    }
)


def normalize_slot(user_input: str) -> str | None:
    """Normalize a user-provided slot name to the canonical PoB slot name.

    Returns the canonical name, or ``None`` if no match is found.
    Matching is case-insensitive and supports common aliases.
    """
    key = user_input.strip().casefold()
    if not key:
        return None
    if key in _SLOT_ALIASES:
        return _SLOT_ALIASES[key]
    # Substring match as fallback.
    for canonical in CANONICAL_SLOTS:
        if key in canonical.casefold():
            return canonical
    return None

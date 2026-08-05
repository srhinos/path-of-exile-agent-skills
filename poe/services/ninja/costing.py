from __future__ import annotations

from typing import TYPE_CHECKING

from poe.models.ninja.analysis import BuildCost, SlotCost, UpgradeSuggestion
from poe.services.ninja.errors import NinjaError

if TYPE_CHECKING:
    from poe.models.ninja.builds import CharacterItem, CharacterJewel, CharacterResponse
    from poe.services.ninja.economy import EconomyService


def _item_name(item: CharacterItem) -> str:
    return item.item_data.get("name", "")


def _item_type_line(item: CharacterItem) -> str:
    return item.item_data.get("typeLine", "")


def _item_rarity(item: CharacterItem | CharacterJewel) -> str:
    frame = item.item_data.get("frameType", 0)
    return {0: "normal", 1: "magic", 2: "rare", 3: "unique"}.get(frame, "")


def _item_slot(item: CharacterItem) -> str:
    return item.item_data.get("inventoryId", "") or "Unknown"


def cost_build(
    character: CharacterResponse,
    economy: EconomyService,
    league: str,
    *,
    game: str = "poe1",
) -> BuildCost:
    slots: list[SlotCost] = []

    for item in character.items:
        name = _item_name(item) or _item_type_line(item)
        if not name:
            continue
        price = _lookup_item_price(name, economy, league, game=game)
        slots.append(
            SlotCost(
                slot=_item_slot(item),
                item_name=name,
                chaos_value=price,
                is_unique=_item_rarity(item) == "unique",
            ),
        )

    for flask in character.flasks:
        name = flask.item_data.get("name", "") or flask.item_data.get("typeLine", "")
        if not name:
            continue
        price = _lookup_item_price(name, economy, league, game=game)
        slots.append(
            SlotCost(
                slot="Flask",
                item_name=name,
                chaos_value=price,
            ),
        )

    for jewel in character.jewels:
        name = jewel.item_data.get("name", "") or jewel.item_data.get("typeLine", "")
        if not name:
            continue
        price = _lookup_item_price(name, economy, league, game=game)
        slots.append(
            SlotCost(
                slot="Jewel",
                item_name=name,
                chaos_value=price,
                is_unique=_item_rarity(jewel) == "unique",
            ),
        )

    total = sum(s.chaos_value for s in slots)
    most_expensive = max(slots, key=lambda s: s.chaos_value) if slots else None

    return BuildCost(
        total_chaos=round(total, 2),
        slots=slots,
        most_expensive=most_expensive,
        character_name=character.name,
        class_name=character.class_name,
        league=league,
    )


def find_budget_alternatives(
    build_cost: BuildCost,
    economy: EconomyService,
    league: str,
    *,
    game: str = "poe1",
) -> list[UpgradeSuggestion]:
    suggestions: list[UpgradeSuggestion] = []

    unique_types = ["UniqueArmour", "UniqueWeapon", "UniqueAccessory", "UniqueFlask", "UniqueJewel"]
    all_prices: dict[str, float] = {}
    for item_type in unique_types:
        try:
            prices = economy.get_prices(league, item_type, game=game)
            for p in prices:
                all_prices[p.name.lower()] = p.chaos_value
        except (OSError, ValueError, KeyError, NinjaError):
            # NinjaError covers transient 5xx that survived client retries
            # plus schema mismatches; without it the workflow fails on the
            # first bad type instead of skipping it and continuing.
            continue

    for slot in build_cost.slots:
        if not slot.is_unique or slot.chaos_value <= 0:
            continue

        current_lower = slot.item_name.lower()
        cheaper = [
            (name, price)
            for name, price in all_prices.items()
            if price < slot.chaos_value and name != current_lower
        ]
        if not cheaper:
            continue

        cheaper.sort(key=lambda x: x[1], reverse=True)
        best = cheaper[0]
        suggestions.append(
            UpgradeSuggestion(
                slot=slot.slot,
                current_item=slot.item_name,
                current_cost=slot.chaos_value,
                suggested_item=best[0],
                suggested_cost=best[1],
                savings=round(slot.chaos_value - best[1], 2),
            ),
        )

    suggestions.sort(key=lambda s: s.savings, reverse=True)
    return suggestions


def _lookup_item_price(
    item_name: str,
    economy: EconomyService,
    league: str,
    *,
    game: str = "poe1",
) -> float:
    search_types = [
        "UniqueArmour",
        "UniqueWeapon",
        "UniqueAccessory",
        "UniqueFlask",
        "UniqueJewel",
    ]
    name_lower = item_name.lower()
    for item_type in search_types:
        try:
            prices = economy.get_prices(league, item_type, game=game)
            match = next((p for p in prices if p.name.lower() == name_lower), None)
            if match:
                return match.chaos_value
        except (OSError, ValueError, KeyError, NinjaError):
            continue
    return 0.0

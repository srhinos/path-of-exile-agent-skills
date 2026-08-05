from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from poe.models.ninja.analysis import BuildCost, SlotCost, UpgradeSuggestion
from poe.models.ninja.builds import (
    CharacterFlask,
    CharacterItem,
    CharacterJewel,
    CharacterResponse,
)
from poe.models.ninja.economy import PriceResult
from poe.services.ninja.costing import cost_build, find_budget_alternatives


def _mock_economy(prices_by_type: dict[str, list[PriceResult]] | None = None):
    economy = MagicMock()

    def get_prices(_league, item_type, **_kwargs):
        if prices_by_type and item_type in prices_by_type:
            return prices_by_type[item_type]
        return []

    economy.get_prices.side_effect = get_prices
    return economy


def _item(name: str, inventory_id: str = "", frame_type: int = 0) -> CharacterItem:
    return CharacterItem(
        itemSlot=0,
        itemData={
            "name": name,
            "typeLine": name,
            "inventoryId": inventory_id,
            "frameType": frame_type,
        },
    )


def _flask(name: str) -> CharacterFlask:
    return CharacterFlask(itemSlot=0, itemData={"name": name, "typeLine": name})


def _jewel(name: str) -> CharacterJewel:
    return CharacterJewel(itemSlot=0, itemData={"name": name, "typeLine": name})


def _make_character(**overrides) -> CharacterResponse:
    defaults = {
        "account": "test",
        "name": "TestChar",
        "league": "Mirage",
        "level": 95,
        "class": "Pathfinder",
        "items": [
            _item("Headhunter", "Belt", frame_type=3),
            _item("Hyrri's Ire", "BodyArmour", frame_type=3),
        ],
        "flasks": [
            _flask("Dying Sun"),
        ],
        "jewels": [
            _jewel("Watcher's Eye"),
        ],
    }
    defaults.update(overrides)
    return CharacterResponse.model_validate(defaults)


MOCK_PRICES = {
    "UniqueArmour": [
        PriceResult(name="Hyrri's Ire", chaos_value=50.0),
        PriceResult(name="Cheap Armour", chaos_value=5.0),
    ],
    "UniqueAccessory": [
        PriceResult(name="Headhunter", chaos_value=15000.0),
        PriceResult(name="Cheap Belt", chaos_value=1.0),
    ],
    "UniqueFlask": [
        PriceResult(name="Dying Sun", chaos_value=200.0),
    ],
    "UniqueJewel": [
        PriceResult(name="Watcher's Eye", chaos_value=5000.0),
        PriceResult(name="Cheap Jewel", chaos_value=2.0),
    ],
}


class TestCostBuild:
    def test_total_cost(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")

        assert isinstance(result, BuildCost)
        assert result.total_chaos == 15000.0 + 50.0 + 200.0 + 5000.0

    def test_per_slot_breakdown(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")

        assert len(result.slots) == 4
        belt = next(s for s in result.slots if s.slot == "Belt")
        assert belt.item_name == "Headhunter"
        assert belt.chaos_value == 15000.0

    def test_most_expensive(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")

        assert result.most_expensive is not None
        assert result.most_expensive.item_name == "Headhunter"

    def test_character_metadata(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")

        assert result.character_name == "TestChar"
        assert result.class_name == "Pathfinder"
        assert result.league == "Mirage"

    def test_empty_build(self):
        char = _make_character(items=[], flasks=[], jewels=[])
        economy = _mock_economy()
        result = cost_build(char, economy, "Mirage")

        assert result.total_chaos == 0.0
        assert result.slots == []
        assert result.most_expensive is None

    def test_unpriced_items(self):
        char = _make_character(
            items=[_item("Unknown Item", "Helm")],
            flasks=[],
            jewels=[],
        )
        economy = _mock_economy()
        result = cost_build(char, economy, "Mirage")

        assert result.total_chaos == 0.0
        assert len(result.slots) == 1
        assert result.slots[0].chaos_value == 0.0

    def test_skips_unnamed_items(self):
        char = _make_character(
            items=[CharacterItem(itemSlot=0, itemData={"name": "", "typeLine": ""})],
            flasks=[],
            jewels=[],
        )
        economy = _mock_economy()
        result = cost_build(char, economy, "Mirage")
        assert result.slots == []


class TestBudgetAlternatives:
    def test_finds_cheaper_alternatives(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")

        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        assert len(suggestions) > 0

        hh_suggestion = next(
            (s for s in suggestions if s.current_item == "Headhunter"),
            None,
        )
        assert hh_suggestion is not None
        assert hh_suggestion.savings > 0
        assert hh_suggestion.suggested_cost < hh_suggestion.current_cost

    def test_sorted_by_savings(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")

        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        if len(suggestions) > 1:
            savings = [s.savings for s in suggestions]
            assert savings == sorted(savings, reverse=True)

    def test_no_alternatives_for_cheap_items(self):
        char = _make_character(
            items=[_item("Cheap Belt", "Belt", frame_type=3)],
            flasks=[],
            jewels=[],
        )
        economy = _mock_economy(
            {
                "UniqueAccessory": [PriceResult(name="Cheap Belt", chaos_value=1.0)],
            }
        )
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        assert suggestions == []


class TestCostBuildInvariants:
    def test_total_equals_sum_of_slots(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")
        slot_sum = sum(s.chaos_value for s in result.slots)
        assert result.total_chaos == pytest.approx(round(slot_sum, 2))

    def test_total_chaos_non_negative(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")
        assert result.total_chaos >= 0.0

    def test_total_chaos_finite(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")
        assert math.isfinite(result.total_chaos)

    def test_slot_chaos_non_negative_for_valid_prices(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")
        for s in result.slots:
            assert s.chaos_value >= 0.0

    def test_most_expensive_is_max(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")
        if result.slots:
            top = max(s.chaos_value for s in result.slots)
            assert result.most_expensive is not None
            assert result.most_expensive.chaos_value == top

    def test_slot_count_matches_priced_items(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        result = cost_build(char, economy, "Mirage")
        priced_inputs = (
            len([i for i in char.items if i.item_data.get("name") or i.item_data.get("typeLine")])
            + len(
                [f for f in char.flasks if f.item_data.get("name") or f.item_data.get("typeLine")]
            )
            + len(
                [j for j in char.jewels if j.item_data.get("name") or j.item_data.get("typeLine")]
            )
        )
        assert len(result.slots) == priced_inputs


class TestCostBuildEconomyErrors:
    @pytest.mark.parametrize("err", [OSError("net"), ValueError("bad"), KeyError("k")])
    def test_economy_errors_treated_as_unpriced(self, err):
        char = _make_character(
            items=[_item("Headhunter", "Belt", frame_type=3)],
            flasks=[],
            jewels=[],
        )
        economy = MagicMock()
        economy.get_prices.side_effect = err
        result = cost_build(char, economy, "Mirage")
        assert result.slots[0].chaos_value == 0.0


class TestBudgetAlternativesInvariants:
    def test_savings_equals_current_minus_suggested(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        for s in suggestions:
            assert s.savings == pytest.approx(round(s.current_cost - s.suggested_cost, 2))

    def test_suggested_cost_lower_than_current(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        for s in suggestions:
            assert s.suggested_cost < s.current_cost

    def test_savings_strictly_positive(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        for s in suggestions:
            assert s.savings > 0

    def test_suggested_item_not_same_as_current(self):
        char = _make_character()
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        for s in suggestions:
            assert s.suggested_item.lower() != s.current_item.lower()

    def test_savings_sorted_descending(self):
        char = _make_character(
            items=[
                _item("Headhunter", "Belt", frame_type=3),
                _item("Hyrri's Ire", "BodyArmour", frame_type=3),
            ],
            flasks=[],
            jewels=[_jewel("Watcher's Eye")],
        )
        economy = _mock_economy(MOCK_PRICES)
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        savings_list = [s.savings for s in suggestions]
        assert savings_list == sorted(savings_list, reverse=True)

    def test_skips_non_unique_slots(self):
        char = _make_character(
            items=[_item("Plain Item", "Belt", frame_type=2)],
            flasks=[],
            jewels=[],
        )
        economy = _mock_economy(
            {
                "UniqueAccessory": [
                    PriceResult(name="Plain Item", chaos_value=100.0),
                    PriceResult(name="Cheap", chaos_value=1.0),
                ],
            }
        )
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        assert suggestions == []

    def test_skips_zero_priced_slots(self):
        char = _make_character(
            items=[_item("Unknown", "Belt", frame_type=3)],
            flasks=[],
            jewels=[],
        )
        economy = _mock_economy(
            {
                "UniqueAccessory": [PriceResult(name="Cheap", chaos_value=1.0)],
            }
        )
        build_cost = cost_build(char, economy, "Mirage")
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        assert suggestions == []

    @pytest.mark.parametrize("err", [OSError("net"), ValueError("bad"), KeyError("k")])
    def test_economy_errors_swallowed(self, err):
        build_cost = BuildCost(
            total_chaos=100.0,
            slots=[
                SlotCost(
                    slot="Belt",
                    item_name="Headhunter",
                    chaos_value=100.0,
                    is_unique=True,
                ),
            ],
        )
        economy = MagicMock()
        economy.get_prices.side_effect = err
        suggestions = find_budget_alternatives(build_cost, economy, "Mirage")
        assert suggestions == []


class TestSlotCostSemanticInvariants:
    def test_accepts_negative_chaos(self):
        sc = SlotCost(slot="X", item_name="Y", chaos_value=-1.0)
        assert sc.chaos_value == -1.0

    def test_accepts_inf_chaos(self):
        sc = SlotCost(slot="X", item_name="Y", chaos_value=float("inf"))
        assert sc.chaos_value == float("inf")

    def test_default_not_unique(self):
        sc = SlotCost(slot="X", item_name="Y")
        assert sc.is_unique is False


class TestBuildCostSemanticInvariants:
    def test_default_no_most_expensive(self):
        bc = BuildCost()
        assert bc.most_expensive is None
        assert bc.slots == []
        assert bc.total_chaos == 0.0

    def test_accepts_negative_total(self):
        bc = BuildCost(total_chaos=-100.0)
        assert bc.total_chaos == -100.0


class TestUpgradeSuggestionSemanticInvariants:
    def test_savings_field_independent_of_other_fields(self):
        us = UpgradeSuggestion(
            slot="Belt",
            current_item="A",
            current_cost=10.0,
            suggested_item="B",
            suggested_cost=5.0,
            savings=999.0,
        )
        assert us.savings == 999.0


class TestCostBuildPoE2Pathway:
    def test_passes_game_to_economy(self):
        char = _make_character(
            items=[_item("Some Item", "Belt", frame_type=3)],
            flasks=[],
            jewels=[],
        )
        economy = MagicMock()
        economy.get_prices.return_value = []
        cost_build(char, economy, "Fate of the Vaal", game="poe2")
        for call in economy.get_prices.call_args_list:
            assert call.kwargs.get("game") == "poe2"

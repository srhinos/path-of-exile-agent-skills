from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from poe.models.ninja.builds import (
    CharacterCharm,
    CharacterResponse,
    DimensionEntry,
    ResolvedDimension,
    SearchResults,
)
from poe.models.ninja.economy import ItemLine
from poe.services.ninja.builds import _build_search_params
from poe.services.ninja.comparison import compare_to_meta
from poe.services.ninja.workflows import how_should_i_craft

POE2_CHARACTER_WITH_CHARMS = {
    "account": "Poe2Player",
    "name": "CharmUser",
    "league": "Fate of the Vaal",
    "level": 80,
    "class": "Blood Mage",
    "defensiveStats": {
        "life": 4000,
        "energyShield": 1000,
        "spirit": 200,
        "fireResistance": 75,
        "coldResistance": 75,
        "lightningResistance": 75,
        "chaosResistance": 20,
        "spellSuppressionChance": 0,
    },
    "skills": [],
    "items": [],
    "flasks": [],
    "jewels": [],
    "charms": [
        {
            "itemSlot": 1,
            "itemData": {
                "name": "Charm of Haste",
                "typeLine": "Gold Charm",
                "explicitMods": ["+10% Movement Speed"],
            },
        },
        {
            "itemSlot": 2,
            "itemData": {
                "name": "Charm of Life",
                "typeLine": "Ruby Charm",
                "explicitMods": ["+50 to Life"],
            },
        },
    ],
    "keystones": [],
    "passives": [10, 20],
    "pathOfBuildingExport": "eNp9XYZW",
}


class TestPoE2Charms:
    def test_charms_parsed(self):
        resp = CharacterResponse.model_validate(POE2_CHARACTER_WITH_CHARMS)
        assert len(resp.charms) == 2
        assert resp.charms[0].item_data["name"] == "Charm of Haste"
        assert resp.charms[0].item_data["explicitMods"] == ["+10% Movement Speed"]

    def test_charm_model(self):
        charm = CharacterCharm(
            itemSlot=1,
            itemData={"name": "Test Charm", "typeLine": "Gold Charm"},
        )
        assert charm.item_data["name"] == "Test Charm"

    def test_empty_charms_poe1(self):
        poe1 = {
            "account": "test",
            "name": "Poe1Char",
            "class": "Pathfinder",
            "level": 95,
        }
        resp = CharacterResponse.model_validate(poe1)
        assert resp.charms == []


class TestAtlasHeatmapParam:
    def test_atlas_heatmap_poe1(self):
        params = _build_search_params(
            overview="mirage",
            game="poe1",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=True,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=None,
        )
        assert params["atlasheatmap"] == "true"

    def test_atlas_heatmap_not_on_poe2(self):
        params = _build_search_params(
            overview="vaal",
            game="poe2",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=True,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=None,
        )
        assert "atlasheatmap" not in params


class TestLinkedGemsParam:
    def test_linked_gems_poe2(self):
        params = _build_search_params(
            overview="vaal",
            game="poe2",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=False,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems={"Life Remnants": "Harmonic Remnants II"},
        )
        assert params["linkedgems-Life Remnants"] == "Harmonic Remnants II"

    def test_linked_gems_ignored_poe1(self):
        params = _build_search_params(
            overview="mirage",
            game="poe1",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=False,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems={"Life Remnants": "Harmonic Remnants II"},
        )
        assert "linkedgems-Life Remnants" not in params


class TestMissingItemLineFields:
    def test_art_filename(self):
        data = {
            "id": 1,
            "name": "Test",
            "artFilename": "art.png",
            "implicitModifiers": [],
            "explicitModifiers": [],
        }
        item = ItemLine.model_validate(data)
        assert item.art_filename == "art.png"

    def test_prophecy_text(self):
        data = {
            "id": 1,
            "name": "Test",
            "prophecyText": "Something will happen",
            "implicitModifiers": [],
            "explicitModifiers": [],
        }
        item = ItemLine.model_validate(data)
        assert item.prophecy_text == "Something will happen"

    def test_mutated_modifiers(self):
        data = {
            "id": 1,
            "name": "Test",
            "mutatedModifiers": [{"text": "Mutated mod", "optional": False}],
            "implicitModifiers": [],
            "explicitModifiers": [],
        }
        item = ItemLine.model_validate(data)
        assert len(item.mutated_modifiers) == 1
        assert item.mutated_modifiers[0].text == "Mutated mod"


class TestMasteryAnointmentGapDetection:
    def test_missing_mastery_detected(self):
        char = CharacterResponse.model_validate(
            {
                "account": "test",
                "name": "TestChar",
                "class": "Pathfinder",
                "level": 95,
                "masteries": [{"name": "Life Mastery", "effect": "+50 to Life"}],
            }
        )
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="mastery",
                    entries=[
                        DimensionEntry(name="Life Mastery", count=900, percentage=90.0),
                        DimensionEntry(name="Mana Mastery", count=850, percentage=85.0),
                    ],
                ),
            ],
        )
        result = compare_to_meta(char, meta)
        assert len(result.missing_masteries) == 1
        assert result.missing_masteries[0].name == "Mana Mastery"

    def test_no_missing_masteries(self):
        char = CharacterResponse.model_validate(
            {
                "account": "test",
                "name": "TestChar",
                "class": "Pathfinder",
                "level": 95,
                "masteries": [
                    {"name": "Life Mastery", "effect": ""},
                    {"name": "Mana Mastery", "effect": ""},
                ],
            }
        )
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="mastery",
                    entries=[
                        DimensionEntry(name="Life Mastery", count=900, percentage=90.0),
                        DimensionEntry(name="Mana Mastery", count=850, percentage=85.0),
                    ],
                ),
            ],
        )
        result = compare_to_meta(char, meta)
        assert result.missing_masteries == []

    def test_missing_anointment_detected(self):
        char = CharacterResponse.model_validate(
            {
                "account": "test",
                "name": "TestChar",
                "class": "Pathfinder",
                "level": 95,
            }
        )
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="anointed",
                    entries=[
                        DimensionEntry(name="Whispers of Doom", count=820, percentage=82.0),
                    ],
                ),
            ],
        )
        result = compare_to_meta(char, meta)
        assert len(result.missing_anointments) == 1
        assert result.missing_anointments[0].name == "Whispers of Doom"


class TestCW3Workflow:
    def test_how_should_i_craft(self):
        economy = MagicMock()
        economy.get_crafting_prices.return_value = MagicMock(
            currency={"Chaos Orb": 1.0, "Exalted Orb": 17.5},
            fossils={"Pristine Fossil": 3.0},
            essences={"Deafening Essence of Woe": 10.0},
            resonators={"Primitive Resonator": 1.0},
        )
        result = how_should_i_craft(economy, "Mirage")
        assert result.workflow == "how_should_i_craft"
        assert result.success is True
        assert "currency" in result.data
        assert "fossils" in result.data

    def test_how_should_i_craft_failure(self):
        economy = MagicMock()
        economy.get_crafting_prices.side_effect = ValueError("fail")
        result = how_should_i_craft(economy, "Mirage")
        assert len(result.errors) > 0


class TestPoE2CharmsInvariants:
    def test_charm_count_preserved(self):
        resp = CharacterResponse.model_validate(POE2_CHARACTER_WITH_CHARMS)
        assert len(resp.charms) == len(POE2_CHARACTER_WITH_CHARMS["charms"])

    def test_charm_slot_index_preserved(self):
        resp = CharacterResponse.model_validate(POE2_CHARACTER_WITH_CHARMS)
        slots = [c.item_slot for c in resp.charms]
        assert slots == [1, 2]

    @pytest.mark.parametrize(
        "missing_field",
        ["charms", "skills", "items", "flasks", "jewels"],
    )
    def test_optional_collections_default_to_empty(self, missing_field):
        data = {
            "account": "test",
            "name": "Char",
            "class": "Pathfinder",
            "level": 95,
        }
        resp = CharacterResponse.model_validate(data)
        assert getattr(resp, missing_field) == []


class TestAtlasHeatmapParametrized:
    @pytest.mark.parametrize("game", ["poe1"])
    def test_atlas_heatmap_set_for_supported_games(self, game):
        params = _build_search_params(
            overview="x",
            game=game,
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=True,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=None,
        )
        assert params.get("atlasheatmap") == "true"

    @pytest.mark.parametrize("game", ["poe2"])
    def test_atlas_heatmap_omitted_for_unsupported_games(self, game):
        params = _build_search_params(
            overview="x",
            game=game,
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=True,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=None,
        )
        assert "atlasheatmap" not in params

    def test_atlas_heatmap_false_omits_param(self):
        params = _build_search_params(
            overview="x",
            game="poe1",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=False,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=None,
        )
        assert "atlasheatmap" not in params


class TestLinkedGemsParametrized:
    @pytest.mark.parametrize(
        "linked_gems",
        [
            {"Life Remnants": "Harmonic Remnants II"},
            {"A": "B", "C": "D"},
        ],
    )
    def test_linked_gems_all_keys_emitted_poe2(self, linked_gems):
        params = _build_search_params(
            overview="x",
            game="poe2",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=False,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=linked_gems,
        )
        for key, value in linked_gems.items():
            assert params[f"linkedgems-{key}"] == value

    def test_empty_linked_gems_dict_emits_nothing_poe2(self):
        params = _build_search_params(
            overview="x",
            game="poe2",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=False,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems={},
        )
        assert not any(k.startswith("linkedgems-") for k in params)

    def test_none_linked_gems_emits_nothing(self):
        params = _build_search_params(
            overview="x",
            game="poe2",
            snapshot_type="exp",
            time_machine=None,
            heatmap=False,
            atlas_heatmap=False,
            class_filter=None,
            skill=None,
            item=None,
            keystone=None,
            mastery=None,
            anointment=None,
            weapon_mode=None,
            bandit=None,
            pantheon=None,
            linked_gems=None,
        )
        assert not any(k.startswith("linkedgems-") for k in params)


class TestItemLineSemanticInvariants:
    def test_default_modifiers_empty_lists(self):
        item = ItemLine.model_validate({"id": 1, "name": "X"})
        assert item.implicit_modifiers == []
        assert item.explicit_modifiers == []
        assert item.mutated_modifiers == []

    def test_chaos_value_can_be_negative(self):
        item = ItemLine.model_validate({"id": 1, "name": "X", "chaosValue": -5.0})
        assert item.chaos_value == -5.0

    def test_listing_count_can_be_negative(self):
        item = ItemLine.model_validate({"id": 1, "name": "X", "listingCount": -1})
        assert item.listing_count == -1

    def test_extra_fields_allowed(self):
        item = ItemLine.model_validate({"id": 1, "name": "X", "newField": "ignored"})
        assert item.name == "X"


class TestMetaComparisonInvariants:
    def test_missing_only_when_above_threshold(self):
        char = CharacterResponse.model_validate(
            {
                "account": "a",
                "name": "C",
                "class": "Pathfinder",
                "level": 90,
                "masteries": [],
            }
        )
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="mastery",
                    entries=[
                        DimensionEntry(name="LowPopMastery", count=10, percentage=1.0),
                    ],
                ),
            ],
        )
        result = compare_to_meta(char, meta)
        assert all(m.meta_pct >= 80.0 for m in result.missing_masteries)

    def test_missing_anointments_only_above_threshold(self):
        char = CharacterResponse.model_validate(
            {"account": "a", "name": "C", "class": "Pathfinder", "level": 90}
        )
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="anointed",
                    entries=[
                        DimensionEntry(name="LowPopAnoint", count=10, percentage=1.0),
                    ],
                ),
            ],
        )
        result = compare_to_meta(char, meta)
        assert all(a.meta_pct >= 80.0 for a in result.missing_anointments)


class TestHowShouldICraftInvariants:
    def test_currency_sorted_ascending(self):
        economy = MagicMock()
        economy.get_crafting_prices.return_value = MagicMock(
            currency={"Z": 100.0, "A": 1.0, "M": 10.0},
            fossils={},
            essences={},
            resonators={},
        )
        result = how_should_i_craft(economy, "Mirage")
        prices = list(result.data["currency"].values())
        assert prices == sorted(prices)

    def test_partial_failure_reports_errors(self):
        economy = MagicMock()
        economy.get_crafting_prices.side_effect = ValueError("oops")
        result = how_should_i_craft(economy, "Mirage")
        assert any("crafting_prices" in e for e in result.errors)

    def test_workflow_name_constant(self):
        economy = MagicMock()
        economy.get_crafting_prices.return_value = MagicMock(
            currency={}, fossils={}, essences={}, resonators={}
        )
        result = how_should_i_craft(economy, "Mirage")
        assert result.workflow == "how_should_i_craft"


class TestCharacterCharmModel:
    def test_defaults_when_empty(self):
        c = CharacterCharm.model_validate({})
        assert c.item_slot == 0
        assert c.item_data == {}

    def test_item_slot_int(self):
        c = CharacterCharm(itemSlot=5, itemData={"name": "Test", "typeLine": "X"})
        assert c.item_slot == 5
        assert isinstance(c.item_slot, int)

    def test_extra_fields_allowed(self):
        c = CharacterCharm.model_validate({"itemSlot": 1, "itemData": {}, "newField": "ignored"})
        assert c.item_slot == 1

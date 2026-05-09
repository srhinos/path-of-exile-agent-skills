from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from poe.models.ninja.builds import (
    CharacterResponse,
    DimensionEntry,
    IntegerRange,
    MetaSummary,
    ResolvedDimension,
    SearchResults,
)
from poe.services.ninja.errors import NinjaError
from poe.services.ninja.workflows import (
    WorkflowResult,
    budget_upgrade,
    fix_my_build,
    how_should_i_craft,
    what_build_to_play,
    what_changed,
    what_to_farm,
)


def _mock_char():
    return CharacterResponse.model_validate(
        {
            "account": "test",
            "name": "TestChar",
            "class": "Pathfinder",
            "level": 95,
            "defensiveStats": {
                "life": 5000,
                "fireResistance": 75,
                "coldResistance": 75,
                "lightningResistance": 75,
                "chaosResistance": 40,
                "spellSuppressionChance": 100,
            },
            "keyStones": [{"name": "Acrobatics"}],
            "skills": [{"allGems": [{"name": "Lightning Arrow"}]}],
            "items": [
                {
                    "itemSlot": 0,
                    "itemData": {"name": "Headhunter", "inventoryId": "Belt", "rarity": "unique"},
                },
            ],
            "flasks": [],
            "jewels": [],
        }
    )


def _mock_search():
    return SearchResults(
        total=1000,
        dimensions=[
            ResolvedDimension(
                id="keypassives",
                entries=[DimensionEntry(name="Acrobatics", count=900, percentage=90.0)],
            ),
        ],
        integer_ranges=[IntegerRange(id="level", min_value=70, max_value=100)],
    )


def _mock_builds(char=None, search=None, meta=None):
    svc = MagicMock()
    svc.get_character.return_value = char or _mock_char()
    svc.search.return_value = search or _mock_search()
    svc.get_meta_summary.return_value = meta or MetaSummary(
        game="poe1",
        league="Mirage",
        total_builds=100000,
        top_builds=[{"class": "Pathfinder", "skill": "LA", "percentage": 5.0, "trend": 1}],
        rising=[{"class": "Pathfinder", "skill": "LA", "percentage": 5.0, "trend": 1}],
    )
    return svc


def _mock_economy():
    economy = MagicMock()
    economy.get_prices.return_value = []
    return economy


class TestFixMyBuild:
    def test_success(self):
        result = fix_my_build("test", "TestChar", _mock_builds(), _mock_economy(), "Mirage")
        assert result.workflow == "fix_my_build"
        assert result.success is True
        assert "character" in result.data
        assert result.data["character"]["name"] == "TestChar"

    def test_character_not_found(self):
        builds = _mock_builds()
        builds.get_character.return_value = None
        result = fix_my_build("test", "Missing", builds, _mock_economy(), "Mirage")
        assert result.success is False

    def test_partial_failure_search(self):
        builds = _mock_builds()
        builds.search.side_effect = ValueError("network error")
        result = fix_my_build("test", "TestChar", builds, _mock_economy(), "Mirage")
        assert result.success is True
        assert "character" in result.data
        assert len(result.errors) > 0
        assert "meta_search" in result.errors[0]

    def test_includes_comparison(self):
        result = fix_my_build("test", "TestChar", _mock_builds(), _mock_economy(), "Mirage")
        assert "comparison" in result.data


class TestWhatToFarm:
    def test_success(self):
        atlas = MagicMock()
        atlas.estimate_profit.return_value = [
            {"name": "Scarab", "expected_value": 5.0},
        ]
        atlas.get_popular_nodes.return_value = [
            DimensionEntry(name="Node1", count=500, percentage=50.0),
        ]
        result = what_to_farm(atlas, _mock_economy(), "Mirage")
        assert result.workflow == "what_to_farm"
        assert "top_strategies" in result.data
        assert "popular_atlas_nodes" in result.data

    def test_partial_failure(self):
        atlas = MagicMock()
        atlas.estimate_profit.side_effect = ValueError("fail")
        atlas.get_popular_nodes.return_value = []
        result = what_to_farm(atlas, _mock_economy(), "Mirage")
        assert len(result.errors) > 0


class TestWhatBuildToPlay:
    def test_success(self):
        result = what_build_to_play(_mock_builds())
        assert result.workflow == "what_build_to_play"
        assert result.data["total_builds"] == 100000
        assert len(result.data["top_builds"]) > 0

    def test_with_budget(self):
        result = what_build_to_play(_mock_builds(), budget_chaos=500.0)
        assert result.data["budget_chaos"] == 500.0


class TestBudgetUpgrade:
    def test_success(self):
        result = budget_upgrade(
            "test", "TestChar", _mock_builds(), _mock_economy(), "Mirage", 100.0
        )
        assert result.workflow == "budget_upgrade"
        assert result.data["budget_chaos"] == 100.0

    def test_character_not_found(self):
        builds = _mock_builds()
        builds.get_character.return_value = None
        result = budget_upgrade("test", "Missing", builds, _mock_economy(), "Mirage", 100.0)
        assert result.success is False


class TestWhatChanged:
    def test_success(self):
        builds = _mock_builds()
        old_search = SearchResults(
            total=900,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[
                        DimensionEntry(name="OldClass", count=400, percentage=44.0),
                    ],
                ),
            ],
        )
        new_search = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[
                        DimensionEntry(name="NewClass", count=500, percentage=50.0),
                    ],
                ),
            ],
        )
        builds.search.side_effect = [new_search, old_search]
        result = what_changed(builds)
        assert result.workflow == "what_changed"
        assert "added" in result.data or "removed" in result.data

    def test_partial_failure(self):
        builds = _mock_builds()
        builds.search.side_effect = ValueError("fail")
        result = what_changed(builds)
        assert len(result.errors) > 0


class TestWorkflowResultInvariants:
    def test_default_success_true(self):
        wr = WorkflowResult(workflow="x")
        assert wr.success is True
        assert wr.data == {}
        assert wr.errors == []

    def test_workflow_name_required(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WorkflowResult()


class TestFixMyBuildErrors:
    def test_swallows_value_error_in_costing(self):
        builds = _mock_builds()
        economy = _mock_economy()
        economy.get_prices.side_effect = ValueError("boom")
        result = fix_my_build("test", "TestChar", builds, economy, "Mirage")
        assert result.success is True
        assert "character" in result.data

    def test_workflow_name_set(self):
        result = fix_my_build("test", "TestChar", _mock_builds(), _mock_economy(), "Mirage")
        assert result.workflow == "fix_my_build"

    def test_propagates_unexpected_exceptions(self):
        builds = _mock_builds()
        builds.get_character.side_effect = NinjaError("not caught")
        with pytest.raises(NinjaError):
            fix_my_build("test", "TestChar", builds, _mock_economy(), "Mirage")

    @pytest.mark.parametrize("game", ["poe1", "poe2"])
    def test_passes_game_through(self, game):
        builds = _mock_builds()
        fix_my_build("test", "TestChar", builds, _mock_economy(), "Mirage", game=game)
        builds.get_character.assert_called_with("test", "TestChar", game=game)


class TestWhatToFarmEdgeCases:
    def test_empty_profits_and_nodes(self):
        atlas = MagicMock()
        atlas.estimate_profit.return_value = []
        atlas.get_popular_nodes.return_value = []
        result = what_to_farm(atlas, _mock_economy(), "Mirage")
        assert result.workflow == "what_to_farm"
        assert "top_strategies" not in result.data
        assert "popular_atlas_nodes" not in result.data

    def test_ninja_error_in_estimate_profit_propagates(self):
        atlas = MagicMock()
        atlas.estimate_profit.side_effect = NinjaError("no scarab prices")
        atlas.get_popular_nodes.return_value = []
        with pytest.raises(NinjaError):
            what_to_farm(atlas, _mock_economy(), "Mirage")

    def test_truncates_top_strategies_to_ten(self):
        atlas = MagicMock()
        atlas.estimate_profit.return_value = [
            {"name": f"S{i}", "expected_value": float(i)} for i in range(50)
        ]
        atlas.get_popular_nodes.return_value = []
        result = what_to_farm(atlas, _mock_economy(), "Mirage")
        assert len(result.data["top_strategies"]) == 10


class TestWhatBuildToPlayEdgeCases:
    def test_empty_meta(self):
        builds = _mock_builds(meta=MetaSummary(game="poe1"))
        result = what_build_to_play(builds)
        assert result.workflow == "what_build_to_play"
        assert result.data.get("total_builds") == 0

    @pytest.mark.parametrize("game", ["poe1", "poe2"])
    def test_passes_game(self, game):
        builds = _mock_builds()
        what_build_to_play(builds, game=game)
        builds.get_meta_summary.assert_called_with(game=game)

    def test_budget_optional(self):
        result = what_build_to_play(_mock_builds())
        assert "budget_chaos" not in result.data


class TestBudgetUpgradeMore:
    def test_workflow_name(self):
        result = budget_upgrade("a", "b", _mock_builds(), _mock_economy(), "L", 100.0)
        assert result.workflow == "budget_upgrade"

    def test_budget_recorded_even_on_failure(self):
        builds = _mock_builds()
        builds.get_character.return_value = None
        result = budget_upgrade("a", "b", builds, _mock_economy(), "L", 250.5)
        assert result.success is False
        assert result.data["budget_chaos"] == 250.5

    def test_budget_is_finite_non_negative(self):
        result = budget_upgrade("a", "b", _mock_builds(), _mock_economy(), "L", 0.0)
        assert result.data["budget_chaos"] >= 0.0


class TestHowShouldICraft:
    def test_workflow_name(self):
        economy = _mock_economy()
        economy.get_crafting_prices.return_value = MagicMock(
            currency={"Chaos": 1.0, "Divine": 200.0},
            fossils={"Pristine": 5.0},
            essences={"Greed": 2.0},
            resonators={"Primitive": 1.5},
        )
        result = how_should_i_craft(economy, "L")
        assert result.workflow == "how_should_i_craft"

    def test_currency_sorted_ascending(self):
        economy = _mock_economy()
        economy.get_crafting_prices.return_value = MagicMock(
            currency={"Divine": 200.0, "Chaos": 1.0, "Exalted": 50.0},
            fossils={},
            essences={},
            resonators={},
        )
        result = how_should_i_craft(economy, "L")
        currency_values = list(result.data["currency"].values())
        assert currency_values == sorted(currency_values)

    def test_partial_failure_recorded(self):
        economy = _mock_economy()
        economy.get_crafting_prices.side_effect = ValueError("boom")
        result = how_should_i_craft(economy, "L")
        assert any("crafting_prices" in e for e in result.errors)


class TestWhatChangedEdgeCases:
    def test_when_only_current_succeeds(self):
        builds = _mock_builds()
        builds.search.side_effect = [_mock_search(), ValueError("old failed")]
        result = what_changed(builds)
        assert any("old_snapshot" in e for e in result.errors)
        assert "added" not in result.data

    @pytest.mark.parametrize(
        "old_time",
        ["week-1", "week-2", "month-1"],
    )
    def test_passes_old_time_machine(self, old_time):
        builds = _mock_builds()
        what_changed(builds, old_time_machine=old_time)
        kwargs_list = [c.kwargs for c in builds.search.call_args_list]
        time_machines = [k.get("time_machine") for k in kwargs_list]
        assert old_time in time_machines

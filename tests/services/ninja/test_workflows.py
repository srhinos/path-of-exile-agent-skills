from __future__ import annotations

from unittest.mock import MagicMock

from poe.models.ninja.builds import (
    CharacterResponse,
    DimensionEntry,
    IntegerRange,
    MetaSummary,
    ResolvedDimension,
    SearchResults,
)
from poe.services.ninja.workflows import (
    budget_upgrade,
    fix_my_build,
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

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from poe.models.ninja.builds import (
    CharacterResponse,
    DefensiveStats,
    DimensionEntry,
    MetaSummary,
    ResolvedDimension,
    SearchCharacter,
    SearchResults,
)
from poe.services.ninja.builds import BuildsService
from poe.services.ninja.errors import NetworkError, NinjaError


def _make_builds_service(tmp_path, *, get_json_side_effect=None):
    client = MagicMock(no_cache=False)
    if get_json_side_effect:
        client.get_json.side_effect = get_json_side_effect
    discovery = MagicMock()
    return BuildsService(client, discovery, base_dir=tmp_path)


class TestGetCharacter:
    def test_returns_none_on_404(self, tmp_path):
        svc = _make_builds_service(
            tmp_path,
            get_json_side_effect=NetworkError("404 Not Found"),
        )
        svc._discovery.get_current_snapshot.return_value = MagicMock(
            version="v1", snapshot_name="snap"
        )
        result = svc.get_character("unknown_account", "unknown_char")
        assert result is None


class TestGetGenericTooltip:
    def test_returns_none_on_404(self, tmp_path):
        svc = _make_builds_service(
            tmp_path,
            get_json_side_effect=NetworkError("404 Not Found"),
        )
        result = svc.get_generic_tooltip("SomeNode", "keystone")
        assert result is None

    def test_returns_data_on_success(self, tmp_path):
        tooltip_data = {
            "type": "keystone",
            "name": "Iron Reflexes",
            "lines": [{"text": "Converts all Evasion Rating to Armour"}],
        }
        svc = _make_builds_service(
            tmp_path,
            get_json_side_effect=lambda *a, **kw: tooltip_data,
        )
        result = svc.get_generic_tooltip("Iron Reflexes", "keystone")
        assert result is not None


class TestGetCharacterMore:
    def test_returns_none_when_no_snapshot(self, tmp_path):
        svc = _make_builds_service(tmp_path)
        svc._discovery.get_current_snapshot.return_value = None
        assert svc.get_character("acc", "char") is None

    def test_returns_none_on_ninja_error(self, tmp_path):
        svc = _make_builds_service(
            tmp_path,
            get_json_side_effect=NinjaError("any kind of ninja error"),
        )
        svc._discovery.get_current_snapshot.return_value = MagicMock(
            version="v1", snapshot_name="snap"
        )
        assert svc.get_character("acc", "char") is None

    def test_returns_character_on_success(self, tmp_path):
        char_data = {
            "account": "acc",
            "name": "Char",
            "class": "Pathfinder",
            "level": 95,
        }
        svc = _make_builds_service(
            tmp_path,
            get_json_side_effect=lambda *a, **kw: char_data,
        )
        svc._discovery.get_current_snapshot.return_value = MagicMock(
            version="v1", snapshot_name="snap"
        )
        result = svc.get_character("acc", "Char")
        assert result is not None
        assert result.name == "Char"
        assert result.account == "acc"
        assert result.class_name == "Pathfinder"
        assert result.level >= 1

    @pytest.mark.parametrize("game", ["poe1", "poe2"])
    def test_path_prefix_per_game(self, tmp_path, game):
        captured = {}

        def fake_get_json(path, **_kwargs):
            captured["path"] = path
            return {"account": "a", "name": "c", "class": "X", "level": 50}

        svc = _make_builds_service(tmp_path, get_json_side_effect=fake_get_json)
        svc._discovery.get_current_snapshot.return_value = MagicMock(
            version="v9", snapshot_name="snap"
        )
        svc.get_character("a", "c", game=game)
        expected_prefix = "/poe2/" if game == "poe2" else "/poe1/"
        assert captured["path"].startswith(expected_prefix)

    def test_poe1_includes_type_param_poe2_does_not(self, tmp_path):
        captured = {}

        def fake_get_json(_path, params=None):
            captured.setdefault("calls", []).append(dict(params or {}))
            return {"account": "a", "name": "c", "class": "X", "level": 50}

        svc = _make_builds_service(tmp_path, get_json_side_effect=fake_get_json)
        svc._discovery.get_current_snapshot.return_value = MagicMock(
            version="v9", snapshot_name="snap"
        )
        svc.get_character("a", "c", game="poe1", snapshot_type="exp")
        svc.get_character("a", "c", game="poe2", snapshot_type="exp")
        assert "type" in captured["calls"][0]
        assert "type" not in captured["calls"][1]


class TestGetTooltip:
    def test_returns_none_when_no_snapshot(self, tmp_path):
        svc = _make_builds_service(tmp_path)
        svc._discovery.get_current_snapshot.return_value = None
        assert svc.get_tooltip("slug") is None

    def test_returns_data_on_success(self, tmp_path):
        svc = _make_builds_service(
            tmp_path,
            get_json_side_effect=lambda *a, **kw: {"name": "Iron Reflexes"},
        )
        svc._discovery.get_current_snapshot.return_value = MagicMock(
            version="v1", snapshot_name="snap"
        )
        result = svc.get_tooltip("iron-reflexes")
        assert result is not None
        assert result.name == "Iron Reflexes"


class TestGetMetaSummary:
    def test_returns_empty_when_no_league_builds(self, tmp_path):
        svc = _make_builds_service(tmp_path)
        state = MagicMock()
        state.league_builds = []
        svc._discovery.get_build_index_state.return_value = state
        result = svc.get_meta_summary()
        assert isinstance(result, MetaSummary)
        assert result.total_builds == 0
        assert result.top_builds == []

    def test_separates_rising_declining(self, tmp_path):
        svc = _make_builds_service(tmp_path)
        rising_stat = MagicMock(class_name="A", skill="X", percentage=5.0, trend=2)
        declining_stat = MagicMock(class_name="B", skill="Y", percentage=3.0, trend=-1)
        flat_stat = MagicMock(class_name="C", skill="Z", percentage=2.0, trend=0)
        league_build = MagicMock()
        league_build.league_name = "Mirage"
        league_build.total = 1000
        league_build.statistics = [rising_stat, declining_stat, flat_stat]
        state = MagicMock()
        state.league_builds = [league_build]
        svc._discovery.get_build_index_state.return_value = state

        result = svc.get_meta_summary()

        assert result.league == "Mirage"
        assert result.total_builds == 1000
        assert len(result.top_builds) == 3
        assert len(result.rising) == 1
        assert result.rising[0]["class"] == "A"
        assert len(result.declining) == 1
        assert result.declining[0]["class"] == "B"

    @pytest.mark.parametrize("game", ["poe1", "poe2"])
    def test_game_propagated(self, tmp_path, game):
        svc = _make_builds_service(tmp_path)
        state = MagicMock()
        state.league_builds = []
        svc._discovery.get_build_index_state.return_value = state
        result = svc.get_meta_summary(game=game)
        assert result.game == game


class TestSearch:
    def test_returns_none_when_no_snapshot(self, tmp_path):
        svc = _make_builds_service(tmp_path)
        svc._discovery.get_current_snapshot.return_value = None
        assert svc.search() is None


class TestCharacterResponseSemanticInvariants:
    def test_default_level_is_zero(self):
        char = CharacterResponse()
        assert char.level == 0

    @pytest.mark.parametrize("level", [1, 50, 95, 100])
    def test_realistic_level_accepted(self, level):
        char = CharacterResponse.model_validate(
            {"account": "a", "name": "n", "class": "X", "level": level}
        )
        assert char.level == level
        assert char.level >= 1

    def test_class_name_non_empty_when_set(self):
        char = CharacterResponse.model_validate(
            {"account": "a", "name": "n", "class": "Pathfinder", "level": 90}
        )
        assert char.class_name != ""
        assert isinstance(char.class_name, str)

    def test_account_and_name_required_for_real_chars(self):
        char = CharacterResponse.model_validate(
            {"account": "Player#1234", "name": "AwesomeChar", "class": "Witch", "level": 100}
        )
        assert char.account
        assert char.name


class TestDefensiveStatsSemanticInvariants:
    @pytest.mark.parametrize(
        "field",
        [
            "fire_resistance",
            "cold_resistance",
            "lightning_resistance",
            "chaos_resistance",
        ],
    )
    def test_resistances_are_int_typed(self, field):
        ds = DefensiveStats.model_validate({field.replace("_", ""): 75})
        assert isinstance(getattr(ds, field), int)

    def test_overcap_default_zero(self):
        ds = DefensiveStats()
        assert ds.fire_resistance_over_cap == 0
        assert ds.cold_resistance_over_cap == 0
        assert ds.lightning_resistance_over_cap == 0
        assert ds.chaos_resistance_over_cap == 0

    def test_life_and_es_non_negative_at_default(self):
        ds = DefensiveStats()
        assert ds.life >= 0
        assert ds.energy_shield >= 0

    def test_alias_population_round_trip(self):
        ds = DefensiveStats.model_validate(
            {
                "life": 5000,
                "energyShield": 1000,
                "fireResistance": 75,
                "coldResistance": 76,
                "lightningResistance": 77,
                "chaosResistance": -30,
                "spellSuppressionChance": 50,
            }
        )
        assert ds.life == 5000
        assert ds.energy_shield == 1000
        assert ds.fire_resistance == 75
        assert ds.cold_resistance == 76
        assert ds.lightning_resistance == 77
        assert ds.chaos_resistance == -30
        assert ds.spell_suppression_chance == 50


class TestSearchCharacterInvariants:
    def test_levels_and_pools_default_zero(self):
        sc = SearchCharacter(name="N", account="A")
        assert sc.level == 0
        assert sc.life == 0
        assert sc.energy_shield == 0
        assert sc.skills == []
        assert sc.keystones == []

    def test_round_trip_preserves_fields(self):
        sc = SearchCharacter(
            name="X",
            account="acc",
            level=92,
            life=5500,
            energy_shield=2200,
            dps="1.2M",
            class_id=3,
            skills=["LA", "GMP"],
            keystones=["Acrobatics"],
        )
        assert sc.name == "X"
        assert sc.account == "acc"
        assert sc.level == 92
        assert len(sc.skills) == 2
        assert "Acrobatics" in sc.keystones


class TestSearchResultsInvariants:
    def test_default_total_zero(self):
        sr = SearchResults()
        assert sr.total == 0
        assert sr.characters == []
        assert sr.dimensions == []
        assert sr.integer_ranges == []

    def test_dimension_entry_percentage_in_bounds_when_constructed_via_atlas_pattern(self):
        dims = [
            ResolvedDimension(
                id="x",
                entries=[
                    DimensionEntry(name="A", count=100, percentage=10.0),
                    DimensionEntry(name="B", count=50, percentage=5.0),
                ],
            )
        ]
        sr = SearchResults(total=1000, dimensions=dims)
        for dim in sr.dimensions:
            for entry in dim.entries:
                assert 0.0 <= entry.percentage <= 100.0
                assert entry.count >= 0

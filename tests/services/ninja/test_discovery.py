from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from poe.models.ninja.discovery import (
    AtlasTreeIndexState,
    BuildIndexState,
    Poe1IndexState,
    Poe2IndexState,
)
from poe.services.ninja.discovery import DiscoveryService, _camel_to_snake, _convert_keys

POE1_INDEX_STATE_FIXTURE = {
    "economyLeagues": [
        {"name": "Mirage", "url": "mirage", "displayName": "Mirage"},
        {"name": "Standard", "url": "standard", "displayName": "Standard"},
    ],
    "oldEconomyLeagues": [
        {"name": "Phrecia", "url": "phrecia", "displayName": "Phrecia"},
    ],
    "snapshotVersions": [
        {
            "url": "mirage",
            "type": "exp",
            "name": "Mirage",
            "timeMachineLabels": ["hour-3", "day-1", "week-1"],
            "version": "0309-20260316-12036",
            "snapshotName": "mirage",
            "overviewType": 0,
            "passiveTree": "PassiveTree-3.28",
            "atlasTree": "AtlasTree-3.28",
        },
        {
            "url": "mirage",
            "type": "depthsolo",
            "name": "Mirage",
            "timeMachineLabels": [],
            "version": "0310-20260316-12037",
            "snapshotName": "mirage",
            "overviewType": 0,
            "passiveTree": "PassiveTree-3.28",
            "atlasTree": "AtlasTree-3.28",
        },
    ],
    "buildLeagues": [
        {"name": "Mirage", "url": "mirage", "displayName": "Mirage"},
    ],
    "oldBuildLeagues": [],
}

POE2_INDEX_STATE_FIXTURE = {
    "economyLeagues": [
        {"name": "Fate of the Vaal", "url": "vaal", "displayName": "Fate of the Vaal"},
        {"name": "Standard", "url": "standard", "displayName": "Standard"},
    ],
    "oldEconomyLeagues": [],
    "snapshotVersions": [
        {
            "url": "vaal",
            "name": "Fate of the Vaal",
            "timeMachineLabels": [],
            "version": "0448-20260316-21307",
            "snapshotName": "fate-of-the-vaal",
            "overviewType": 0,
            "passiveTree": "PassiveTree-0.4",
        },
    ],
    "buildLeagues": [
        {
            "name": "Fate of the Vaal",
            "url": "vaal",
            "displayName": "Fate of the Vaal",
            "hardcore": False,
            "indexed": True,
        },
    ],
    "oldBuildLeagues": [],
}

BUILD_INDEX_STATE_FIXTURE = {
    "leagueBuilds": [
        {
            "leagueName": "Mirage",
            "leagueUrl": "mirage",
            "total": 124428,
            "status": 0,
            "statistics": [
                {"class": "Pathfinder", "skill": "Lightning Arrow", "percentage": 4.53, "trend": 1},
                {
                    "class": "Necromancer",
                    "skill": "Summon Raging Spirits",
                    "percentage": 3.21,
                    "trend": -1,
                },
            ],
        },
    ],
}

ATLAS_TREE_INDEX_STATE_FIXTURE = {
    "leagues": [
        {"leagueName": "Mirage", "leagueUrl": "mirage"},
    ],
    "oldLeagues": [
        {"leagueName": "Phrecia", "leagueUrl": "phrecia"},
    ],
    "snapshotVersions": [
        {"type": "atlastree", "version": "0501-20260316-48555", "snapshotName": "mirage"},
    ],
}


def _make_service(tmp_path, fixture_map=None):
    client = MagicMock(no_cache=False)

    def get_json_side_effect(path, **_kwargs):
        if fixture_map and path in fixture_map:
            return fixture_map[path]
        msg = f"Unmocked path: {path}"
        raise ValueError(msg)

    client.get_json.side_effect = get_json_side_effect
    return DiscoveryService(client, base_dir=tmp_path)


class TestCamelToSnake:
    def test_simple(self):
        assert _camel_to_snake("economyLeagues") == "economy_leagues"

    def test_already_snake(self):
        assert _camel_to_snake("economy_leagues") == "economy_leagues"

    def test_single_word(self):
        assert _camel_to_snake("name") == "name"

    def test_multiple_caps(self):
        assert _camel_to_snake("timeMachineLabels") == "time_machine_labels"


class TestConvertKeys:
    def test_dict(self):
        assert _convert_keys({"fooBar": 1}) == {"foo_bar": 1}

    def test_nested(self):
        result = _convert_keys({"outer": {"innerKey": 1}})
        assert result == {"outer": {"inner_key": 1}}

    def test_list_of_dicts(self):
        result = _convert_keys([{"someKey": 1}])
        assert result == [{"some_key": 1}]

    def test_primitives_unchanged(self):
        assert _convert_keys(42) == 42
        assert _convert_keys("hello") == "hello"


class TestPoe1IndexState:
    def test_parse_fixture(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        state = svc.get_poe1_index_state()

        assert isinstance(state, Poe1IndexState)
        assert len(state.economy_leagues) == 2
        assert state.economy_leagues[0].name == "Mirage"
        assert len(state.snapshot_versions) == 2
        assert state.snapshot_versions[0].type == "exp"
        assert state.snapshot_versions[0].version == "0309-20260316-12036"
        assert state.snapshot_versions[0].time_machine_labels == ["hour-3", "day-1", "week-1"]

    def test_caches_result(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        svc.get_poe1_index_state()
        svc.get_poe1_index_state()
        assert svc._client.get_json.call_count == 1

    def test_force_invalidates_cache(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        svc.get_poe1_index_state()
        svc.get_poe1_index_state(force=True)
        assert svc._client.get_json.call_count == 2


class TestPoe2IndexState:
    def test_parse_fixture(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE})
        state = svc.get_poe2_index_state()

        assert isinstance(state, Poe2IndexState)
        assert len(state.economy_leagues) == 2
        assert state.economy_leagues[0].name == "Fate of the Vaal"
        assert len(state.snapshot_versions) == 1
        assert state.snapshot_versions[0].passive_tree == "PassiveTree-0.4"

    def test_poe2_has_hardcore_flag(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE})
        state = svc.get_poe2_index_state()
        assert state.build_leagues[0].hardcore is False
        assert state.build_leagues[0].indexed is True


class TestBuildIndexState:
    def test_parse_fixture(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {"/poe1/api/data/build-index-state": BUILD_INDEX_STATE_FIXTURE},
        )
        state = svc.get_build_index_state(game="poe1")

        assert isinstance(state, BuildIndexState)
        assert len(state.league_builds) == 1
        lb = state.league_builds[0]
        assert lb.league_name == "Mirage"
        assert lb.total == 124428
        assert len(lb.statistics) == 2
        assert lb.statistics[0].class_name == "Pathfinder"
        assert lb.statistics[0].skill == "Lightning Arrow"
        assert lb.statistics[0].trend == 1


class TestAtlasTreeIndexState:
    def test_parse_fixture(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {"/poe1/api/data/atlas-tree-index-state": ATLAS_TREE_INDEX_STATE_FIXTURE},
        )
        state = svc.get_atlas_tree_index_state()

        assert isinstance(state, AtlasTreeIndexState)
        assert len(state.leagues) == 1
        assert state.leagues[0].league_name == "Mirage"
        assert len(state.old_leagues) == 1
        assert len(state.snapshot_versions) == 1
        assert state.snapshot_versions[0].type == "atlastree"


class TestGetCurrentLeague:
    def test_returns_non_standard_league(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        league = svc.get_current_league(game="poe1")
        assert league is not None
        assert league.name == "Mirage"

    def test_poe2_current_league(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE})
        league = svc.get_current_league(game="poe2")
        assert league is not None
        assert league.name == "Fate of the Vaal"

    def test_returns_first_if_only_standard(self, tmp_path):
        fixture = {
            "economyLeagues": [{"name": "Standard", "url": "standard"}],
            "oldEconomyLeagues": [],
            "snapshotVersions": [],
            "buildLeagues": [],
            "oldBuildLeagues": [],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": fixture})
        league = svc.get_current_league(game="poe1")
        assert league.name == "Standard"

    def test_returns_none_if_empty(self, tmp_path):
        fixture = {
            "economyLeagues": [],
            "oldEconomyLeagues": [],
            "snapshotVersions": [],
            "buildLeagues": [],
            "oldBuildLeagues": [],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": fixture})
        league = svc.get_current_league(game="poe1")
        assert league is None


class TestGetCurrentSnapshot:
    def test_poe1_exp(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        snap = svc.get_current_snapshot(game="poe1", snapshot_type="exp")
        assert snap.type == "exp"

    def test_poe1_depthsolo(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        snap = svc.get_current_snapshot(game="poe1", snapshot_type="depthsolo")
        assert snap.type == "depthsolo"

    def test_poe2_returns_first(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE})
        snap = svc.get_current_snapshot(game="poe2")
        assert snap.name == "Fate of the Vaal"


class TestValidateLeague:
    def test_valid_by_name(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("Mirage", game="poe1") is True

    def test_valid_by_url(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("mirage", game="poe1") is True

    def test_valid_old_league(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("Phrecia", game="poe1") is True

    def test_invalid_league(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("NotALeague", game="poe1") is False

    def test_case_insensitive(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("MIRAGE", game="poe1") is True


class TestDetectGame:
    def test_detects_poe1(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE,
                "/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE,
            },
        )
        assert svc.detect_game("Mirage") == "poe1"

    def test_detects_poe2(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE,
                "/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE,
            },
        )
        assert svc.detect_game("Fate of the Vaal") == "poe2"

    def test_defaults_to_poe1(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE,
                "/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE,
            },
        )
        assert svc.detect_game("UnknownLeague") == "poe1"


class TestExtraFieldsIgnored:
    def test_poe1_index_state_ignores_extras(self, tmp_path):
        fixture = {**POE1_INDEX_STATE_FIXTURE, "newField": "ignored"}
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": fixture})
        state = svc.get_poe1_index_state()
        assert isinstance(state, Poe1IndexState)


class TestValidateLeagueNegativeCases:
    def test_unknown_league_returns_false(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("DefinitelyNotALeague", game="poe1") is False

    def test_empty_league_name_returns_false(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        # Empty name shouldn't match any league name or url.
        assert svc.validate_league("", game="poe1") is False

    def test_whitespace_only_league_returns_false(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        assert svc.validate_league("   ", game="poe1") is False

    def test_unknown_in_poe2_returns_false(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE})
        assert svc.validate_league("Mirage", game="poe2") is False

    def test_substring_match_does_not_validate(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        # "Mira" is a substring of "Mirage" but should NOT validate.
        assert svc.validate_league("Mira", game="poe1") is False


class TestSemanticPydanticInvariants:
    def test_poe1_index_state_economy_leagues_have_non_empty_names(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        state = svc.get_poe1_index_state()
        assert len(state.economy_leagues) > 0
        for league in state.economy_leagues:
            assert league.name
            assert league.url

    def test_poe2_index_state_has_at_least_one_league(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe2/api/data/index-state": POE2_INDEX_STATE_FIXTURE})
        state = svc.get_poe2_index_state()
        assert len(state.economy_leagues) > 0

    def test_snapshot_url_non_empty(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        state = svc.get_poe1_index_state()
        for snap in state.snapshot_versions:
            assert snap.url
            assert snap.version
            assert snap.snapshot_name

    def test_build_index_state_percentages_in_range(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {"/poe1/api/data/build-index-state": BUILD_INDEX_STATE_FIXTURE},
        )
        state = svc.get_build_index_state(game="poe1")
        for lb in state.league_builds:
            assert lb.total >= 0
            for stat in lb.statistics:
                assert 0.0 <= stat.percentage <= 100.0
                assert stat.skill or stat.class_name

    def test_atlas_tree_index_state_leagues_have_names(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {"/poe1/api/data/atlas-tree-index-state": ATLAS_TREE_INDEX_STATE_FIXTURE},
        )
        state = svc.get_atlas_tree_index_state()
        for lg in state.leagues:
            assert lg.league_name
            assert lg.league_url

    def test_default_field_values_for_missing_data(self, tmp_path):
        # Snapshots with no time machine labels default to empty list.
        fixture = {
            "economyLeagues": [{"name": "X", "url": "x"}],
            "oldEconomyLeagues": [],
            "snapshotVersions": [
                {
                    "url": "x",
                    "type": "exp",
                    "name": "X",
                    "version": "v1",
                    "snapshotName": "x",
                },
            ],
            "buildLeagues": [],
            "oldBuildLeagues": [],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": fixture})
        state = svc.get_poe1_index_state()
        snap = state.snapshot_versions[0]
        assert snap.time_machine_labels == []
        assert snap.passive_tree == ""


class TestDiscoveryBoundaryCoercion:
    def test_index_state_drops_leagues_with_empty_name(self, tmp_path, caplog):
        fixture = {
            "economyLeagues": [
                {"name": "Mirage", "url": "mirage"},
                {"name": "", "url": "broken"},
            ],
            "oldEconomyLeagues": [],
            "snapshotVersions": [],
            "buildLeagues": [],
            "oldBuildLeagues": [],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": fixture})
        with caplog.at_level("WARNING", logger="poe.ninja.discovery"):
            state = svc.get_poe1_index_state()
        assert [lg.name for lg in state.economy_leagues] == ["Mirage"]
        assert any("dropping" in r.message for r in caplog.records)

    def test_index_state_drops_leagues_with_empty_url(self, tmp_path, caplog):
        fixture = {
            "economyLeagues": [
                {"name": "Mirage", "url": "mirage"},
                {"name": "Broken", "url": ""},
            ],
            "oldEconomyLeagues": [],
            "snapshotVersions": [],
            "buildLeagues": [],
            "oldBuildLeagues": [],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": fixture})
        with caplog.at_level("WARNING", logger="poe.ninja.discovery"):
            state = svc.get_poe1_index_state()
        assert [lg.name for lg in state.economy_leagues] == ["Mirage"]
        assert any("dropping" in r.message for r in caplog.records)

    def test_atlas_tree_drops_leagues_with_empty_name(self, tmp_path, caplog):
        fixture = {
            "leagues": [
                {"leagueName": "Mirage", "leagueUrl": "mirage"},
                {"leagueName": "", "leagueUrl": "ghost"},
            ],
            "oldLeagues": [],
            "snapshotVersions": [],
        }
        svc = _make_service(
            tmp_path,
            {"/poe1/api/data/atlas-tree-index-state": fixture},
        )
        with caplog.at_level("WARNING", logger="poe.ninja.discovery"):
            state = svc.get_atlas_tree_index_state()
        assert [lg.league_name for lg in state.leagues] == ["Mirage"]
        assert any("dropping" in r.message for r in caplog.records)

    def test_build_index_clamps_negative_percentage(self, tmp_path, caplog):
        fixture = {
            "leagueBuilds": [
                {
                    "leagueName": "Mirage",
                    "leagueUrl": "mirage",
                    "total": 100,
                    "statistics": [
                        {"class": "Witch", "skill": "Fireball", "percentage": -1.0},
                    ],
                },
            ],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/build-index-state": fixture})
        with caplog.at_level("WARNING", logger="poe.ninja.discovery"):
            state = svc.get_build_index_state(game="poe1")
        assert state.league_builds[0].statistics[0].percentage == 0.0
        assert any("below 0" in r.message for r in caplog.records)

    def test_build_index_clamps_percentage_above_max(self, tmp_path, caplog):
        fixture = {
            "leagueBuilds": [
                {
                    "leagueName": "Mirage",
                    "leagueUrl": "mirage",
                    "total": 100,
                    "statistics": [
                        {"class": "Witch", "skill": "Fireball", "percentage": 999.0},
                    ],
                },
            ],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/build-index-state": fixture})
        with caplog.at_level("WARNING", logger="poe.ninja.discovery"):
            state = svc.get_build_index_state(game="poe1")
        assert state.league_builds[0].statistics[0].percentage == 100.0
        assert any("above" in r.message for r in caplog.records)

    def test_build_index_drops_stats_with_empty_class(self, tmp_path, caplog):
        fixture = {
            "leagueBuilds": [
                {
                    "leagueName": "Mirage",
                    "leagueUrl": "mirage",
                    "total": 100,
                    "statistics": [
                        {"class": "Witch", "skill": "Fireball", "percentage": 5.0},
                        {"class": "", "skill": "Ghost", "percentage": 1.0},
                    ],
                },
            ],
        }
        svc = _make_service(tmp_path, {"/poe1/api/data/build-index-state": fixture})
        with caplog.at_level("WARNING", logger="poe.ninja.discovery"):
            state = svc.get_build_index_state(game="poe1")
        skills = [s.skill for s in state.league_builds[0].statistics]
        assert skills == ["Fireball"]
        assert any("missing class" in r.message for r in caplog.records)


class TestDiscoveryCachingInvariants:
    def test_no_cache_skips_cache_read(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        svc.get_poe1_index_state()
        assert svc._client.get_json.call_count == 1
        # Flip no_cache and expect another fetch.
        svc._client.no_cache = True
        svc.get_poe1_index_state()
        assert svc._client.get_json.call_count == 2

    def test_cache_persists_to_disk(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        svc.get_poe1_index_state()
        # Cache file written by fetch.
        from poe.services.ninja import cache as ninja_cache

        cached = ninja_cache.read_cache(tmp_path, "poe1_index_state")
        assert cached is not None

    def test_force_refetches_after_cache_invalidation(self, tmp_path):
        svc = _make_service(tmp_path, {"/poe1/api/data/index-state": POE1_INDEX_STATE_FIXTURE})
        svc.get_poe1_index_state()
        # Force should clear the cache directory and re-fetch.
        svc.get_poe1_index_state(force=True)
        assert svc._client.get_json.call_count == 2


class TestCamelToSnakeCoverage:
    @pytest.mark.parametrize(
        ("inp", "expected"),
        [
            ("a", "a"),
            ("A", "a"),
            ("aB", "a_b"),
            ("ABC", "a_b_c"),
            ("snake_case", "snake_case"),
            ("camelCase", "camel_case"),
            ("PascalCase", "pascal_case"),
            ("nameURL", "name_u_r_l"),
            ("", ""),
        ],
    )
    def test_various_forms(self, inp, expected):
        assert _camel_to_snake(inp) == expected


class TestConvertKeysCoverage:
    def test_handles_empty_dict(self):
        assert _convert_keys({}) == {}

    def test_handles_empty_list(self):
        assert _convert_keys([]) == []

    def test_handles_none(self):
        assert _convert_keys(None) is None

    def test_handles_bool(self):
        assert _convert_keys(True) is True

    def test_deeply_nested(self):
        result = _convert_keys({"outerKey": [{"innerKey": [{"deepKey": 1}]}]})
        assert result == {"outer_key": [{"inner_key": [{"deep_key": 1}]}]}

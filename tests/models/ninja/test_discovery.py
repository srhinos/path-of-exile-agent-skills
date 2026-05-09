from __future__ import annotations

import pytest

from poe.models.ninja.discovery import (
    AtlasLeague,
    AtlasSnapshot,
    AtlasTreeIndexState,
    BuildIndexState,
    BuildStat,
    CacheStatusEntry,
    CacheStatusReport,
    LeagueBuild,
    LeagueInfo,
    Poe1Snapshot,
    Poe2Snapshot,
)


class TestBuildStat:
    def test_without_skill_field(self):
        data = {"class": "Monk", "percentage": 12.5, "trend": 3}
        stat = BuildStat.model_validate(data)
        assert stat.class_name == "Monk"
        assert stat.skill == ""
        assert stat.percentage == 12.5

    def test_with_skill_field(self):
        data = {"class": "Witch", "skill": "Fireball", "percentage": 5.0}
        stat = BuildStat.model_validate(data)
        assert stat.skill == "Fireball"


# ── Pydantic semantic invariants for ninja discovery (Pattern 5) ────────────


class TestBuildStatInvariants:
    def test_percentage_negative_clamps_to_zero(self):
        stat = BuildStat.model_validate({"class": "Witch", "percentage": -5.0})
        assert stat.percentage == 0.0

    def test_percentage_above_100_clamps_to_100(self):
        stat = BuildStat.model_validate({"class": "Witch", "percentage": 101.0})
        assert stat.percentage == 100.0

    def test_percentage_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            BuildStat.model_validate({"class": "Witch", "percentage": float("nan")})

    def test_class_name_empty_accepted(self):
        stat = BuildStat.model_validate({"class": "", "percentage": 5.0})
        assert stat.class_name == ""


class TestLeagueInfoInvariants:
    def test_minimum_construction(self):
        info = LeagueInfo(name="Standard", url="standard")
        assert info.name == "Standard"

    def test_name_empty_accepted(self):
        info = LeagueInfo(name="", url="x")
        assert info.name == ""

    def test_url_empty_accepted(self):
        info = LeagueInfo(name="x", url="")
        assert info.url == ""


class TestPoe1SnapshotInvariants:
    def test_minimum_construction(self):
        s = Poe1Snapshot(url="x", type="t", name="n", version="v", snapshot_name="sn")
        assert s.overview_type == 0

    def test_overview_type_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            Poe1Snapshot(
                url="x",
                type="t",
                name="n",
                version="v",
                snapshot_name="sn",
                overview_type=-1,
            )


class TestPoe2SnapshotInvariants:
    def test_minimum_construction(self):
        s = Poe2Snapshot(url="x", name="n", version="v", snapshot_name="sn")
        assert s.overview_type == 0


class TestLeagueBuildInvariants:
    def test_total_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            LeagueBuild(league_name="x", league_url="x", total=-1)


class TestBuildIndexStateInvariants:
    def test_default_empty(self):
        state = BuildIndexState()
        assert state.league_builds == []


class TestAtlasModels:
    def test_atlas_league_minimum(self):
        league = AtlasLeague(league_name="x", league_url="x")
        assert league.league_name == "x"

    def test_atlas_snapshot_default(self):
        s = AtlasSnapshot()
        assert s.overview_type == 0

    def test_atlas_index_state_default(self):
        s = AtlasTreeIndexState()
        assert s.leagues == []
        assert s.old_leagues == []


class TestCacheStatusEntryInvariants:
    def test_minimum_construction(self):
        entry = CacheStatusEntry(name="ninja_currency")
        assert entry.is_cached is False
        assert entry.is_fresh is False
        assert entry.age_seconds is None

    def test_name_empty_accepted(self):
        entry = CacheStatusEntry(name="")
        assert entry.name == ""

    def test_age_seconds_negative_clamps_to_zero(self):
        entry = CacheStatusEntry(name="x", age_seconds=-5.0)
        assert entry.age_seconds == 0.0

    def test_age_seconds_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            CacheStatusEntry(name="x", age_seconds=float("nan"))


class TestCacheStatusReportInvariants:
    def test_minimum_construction(self):
        report = CacheStatusReport(cache_dir="/tmp/cache")
        assert report.entries == []

    def test_cache_dir_empty_accepted(self):
        report = CacheStatusReport(cache_dir="")
        assert report.cache_dir == ""

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
    @pytest.mark.xfail(strict=True, reason="No validator: percentage should be 0..100")
    def test_percentage_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            BuildStat.model_validate({"class": "Witch", "percentage": -5.0})

    @pytest.mark.xfail(strict=True, reason="No validator: percentage 0..100")
    def test_percentage_rejects_above_100(self):
        with pytest.raises((ValueError, TypeError)):
            BuildStat.model_validate({"class": "Witch", "percentage": 101.0})

    @pytest.mark.xfail(strict=True, reason="No validator: percentage rejects NaN")
    def test_percentage_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            BuildStat.model_validate({"class": "Witch", "percentage": float("nan")})

    @pytest.mark.xfail(strict=True, reason="No validator: class_name rejects empty")
    def test_class_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            BuildStat.model_validate({"class": "", "percentage": 5.0})


class TestLeagueInfoInvariants:
    def test_minimum_construction(self):
        info = LeagueInfo(name="Standard", url="standard")
        assert info.name == "Standard"

    @pytest.mark.xfail(strict=True, reason="No validator: name rejects empty")
    def test_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            LeagueInfo(name="", url="x")

    @pytest.mark.xfail(strict=True, reason="No validator: url rejects empty")
    def test_url_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            LeagueInfo(name="x", url="")


class TestPoe1SnapshotInvariants:
    def test_minimum_construction(self):
        s = Poe1Snapshot(url="x", type="t", name="n", version="v", snapshot_name="sn")
        assert s.overview_type == 0

    @pytest.mark.xfail(strict=True, reason="No validator: overview_type rejects negative")
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
    @pytest.mark.xfail(strict=True, reason="No validator: total rejects negative")
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

    @pytest.mark.xfail(strict=True, reason="No validator: name rejects empty")
    def test_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            CacheStatusEntry(name="")

    @pytest.mark.xfail(strict=True, reason="No validator: age_seconds rejects negative")
    def test_age_seconds_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            CacheStatusEntry(name="x", age_seconds=-5.0)

    @pytest.mark.xfail(strict=True, reason="No validator: age_seconds rejects NaN")
    def test_age_seconds_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            CacheStatusEntry(name="x", age_seconds=float("nan"))


class TestCacheStatusReportInvariants:
    def test_minimum_construction(self):
        report = CacheStatusReport(cache_dir="/tmp/cache")
        assert report.entries == []

    @pytest.mark.xfail(strict=True, reason="No validator: cache_dir rejects empty")
    def test_cache_dir_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            CacheStatusReport(cache_dir="")

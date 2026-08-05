from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app
from poe.models.ninja.builds import DimensionEntry, ResolvedDimension, SearchResults
from poe.services.ninja.atlas import AtlasService, _classify_node
from poe.services.ninja.discovery import DiscoveryService
from tests.conftest import invoke_cli

FIXTURES = Path(__file__).parent / "fixtures"

ATLAS_TREE_INDEX_STATE = {
    "leagues": [{"leagueName": "Mirage", "leagueUrl": "mirage"}],
    "oldLeagues": [],
    "snapshotVersions": [
        {
            "type": "atlastree",
            "version": "0501-20260316-48555",
            "snapshotName": "mirage",
        },
    ],
}

INDEX_STATE = {
    "economyLeagues": [{"name": "Mirage", "url": "mirage"}],
    "oldEconomyLeagues": [],
    "snapshotVersions": [],
    "buildLeagues": [],
    "oldBuildLeagues": [],
}


def _make_atlas_service(tmp_path, fixture_map=None):
    client = MagicMock(no_cache=False)

    def get_json(path, **_kwargs):
        if fixture_map:
            for pattern, data in fixture_map.items():
                if pattern in path:
                    return data
        msg = f"Unmocked json: {path}"
        raise ValueError(msg)

    def get_protobuf(_path, **_kwargs):
        return (FIXTURES / "search_result.bin").read_bytes()

    client.get_json.side_effect = get_json
    client.get_protobuf.side_effect = get_protobuf

    discovery = DiscoveryService(client, base_dir=tmp_path)
    return AtlasService(client, discovery, base_dir=tmp_path)


class TestClassifyNode:
    def test_mandatory(self):
        assert _classify_node(60.0) == "mandatory"

    def test_flex(self):
        assert _classify_node(20.0) == "flex"

    def test_dead(self):
        assert _classify_node(5.0) == "dead"

    def test_boundary_mandatory(self):
        assert _classify_node(50.0) == "mandatory"

    def test_boundary_flex(self):
        assert _classify_node(10.0) == "flex"


class TestAtlasSearch:
    def test_search_returns_results(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )
        result = svc.search()
        assert result is not None
        assert result.total > 0
        assert result.game == "poe1"

    def test_search_with_mechanics_filter(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )
        result = svc.search(mechanics="Scarabs")
        assert result is not None

        call = svc._client.get_protobuf.call_args_list[0]
        assert call.kwargs["params"]["mechanics"] == "Scarabs"

    def test_search_with_negation(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )
        svc.search(mechanics="!Delirium")
        call = svc._client.get_protobuf.call_args_list[0]
        assert call.kwargs["params"]["mechanics"] == "!Delirium"

    def test_search_no_snapshots(self, tmp_path):
        empty = {**ATLAS_TREE_INDEX_STATE, "snapshotVersions": []}
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": empty,
            },
        )
        result = svc.search()
        assert result is None


class TestPopularNodes:
    def test_returns_top_nodes(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )
        nodes = svc.get_popular_nodes(top_n=5)
        assert len(nodes) <= 5
        if len(nodes) > 1:
            assert nodes[0].count >= nodes[1].count


class TestEstimateProfit:
    def test_profit_calculation(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )

        from poe.models.ninja.economy import PriceResult

        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Ambush Scarab", chaos_value=10.0),
        ]

        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[DimensionEntry(name="Ambush Scarab", count=200, percentage=20.0)],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)

        profits = svc.estimate_profit(mock_economy, "Mirage")
        assert len(profits) == 1
        assert profits[0]["name"] == "Ambush Scarab"
        assert profits[0]["expected_value"] == 2.0


class TestHeatmap:
    def test_heatmap_classification(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )

        mock_builds = MagicMock()
        mock_builds.search.return_value = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="passive",
                    entries=[
                        DimensionEntry(name="Life Node", count=800, percentage=80.0),
                        DimensionEntry(name="Flex Node", count=200, percentage=20.0),
                        DimensionEntry(name="Dead Node", count=10, percentage=1.0),
                    ],
                ),
            ],
        )

        heatmap = svc.get_heatmap(mock_builds)
        assert len(heatmap) == 3
        assert heatmap[0]["zone"] == "mandatory"
        assert heatmap[1]["zone"] == "flex"
        assert heatmap[2]["zone"] == "dead"

    def test_heatmap_empty(self, tmp_path):
        svc = _make_atlas_service(
            tmp_path,
            {
                "atlas-tree-index-state": ATLAS_TREE_INDEX_STATE,
            },
        )

        mock_builds = MagicMock()
        mock_builds.search.return_value = SearchResults(total=0, dimensions=[])

        heatmap = svc.get_heatmap(mock_builds)
        assert heatmap == []


class TestAtlasCli:
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_search_cli(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total" in data

    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_recommend_cli(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "recommend"])
        assert result.exit_code == 0


class TestAtlasSearchNewFilters:
    def test_travel_filter(self, tmp_path):
        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        svc.search(travel="long")
        call = svc._client.get_protobuf.call_args_list[0]
        assert call.kwargs["params"]["travel"] == "long"

    def test_blockers_filter(self, tmp_path):
        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        svc.search(blockers="test")
        call = svc._client.get_protobuf.call_args_list[0]
        assert call.kwargs["params"]["blockers"] == "test"

    def test_scarab_specializations_filter(self, tmp_path):
        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        svc.search(scarab_specializations="Ambush")
        call = svc._client.get_protobuf.call_args_list[0]
        assert call.kwargs["params"]["scarabspecializations"] == "Ambush"


class TestPopularNodesTopN:
    def test_top_n_parameter(self, tmp_path):
        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        nodes_3 = svc.get_popular_nodes(top_n=3)
        nodes_10 = svc.get_popular_nodes(top_n=10)
        assert len(nodes_3) <= 3
        assert len(nodes_10) <= 10


class TestAtlasProfitCli:
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_profit_cli(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            if "index-state" in path:
                return {
                    "economyLeagues": [{"name": "Mirage", "url": "mirage"}],
                    "oldEconomyLeagues": [],
                    "snapshotVersions": [],
                    "buildLeagues": [],
                    "oldBuildLeagues": [],
                }
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "profit", "Mirage", "--json"])
        assert result.exit_code == 0


class TestAtlasResolveLeague:
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_profit_with_league(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            if "index-state" in path:
                return {
                    "economyLeagues": [{"name": "Mirage", "url": "mirage"}],
                    "oldEconomyLeagues": [],
                    "snapshotVersions": [],
                    "buildLeagues": [],
                    "oldBuildLeagues": [],
                }
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "profit", "--json"])
        assert result.exit_code == 0

    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_profit_no_league(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            if "index-state" in path:
                return {
                    "economyLeagues": [],
                    "oldEconomyLeagues": [],
                    "snapshotVersions": [],
                    "buildLeagues": [],
                    "oldBuildLeagues": [],
                }
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "profit", "--json"])
        assert result.exit_code == 1


class TestAtlasSearchCliNoData:
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_search_no_data(self, mock_cls):
        client = MagicMock(no_cache=False)
        empty = {**ATLAS_TREE_INDEX_STATE, "snapshotVersions": []}

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return empty
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


# ── Added tests below ────────────────────────────────────────────────────────


class TestClassifyNodeFullRange:
    @pytest.mark.parametrize(
        ("pct", "expected"),
        [
            (100.0, "mandatory"),
            (75.0, "mandatory"),
            (50.0, "mandatory"),
            (49.99, "flex"),
            (25.0, "flex"),
            (10.01, "flex"),
            (10.0, "flex"),
            (9.99, "dead"),
            (0.0, "dead"),
        ],
    )
    def test_classify_node_thresholds(self, pct, expected):
        assert _classify_node(pct) == expected


class TestEstimateProfitInvariants:
    def test_expected_value_non_negative(self, tmp_path):
        from poe.models.ninja.economy import PriceResult

        svc = _make_atlas_service(
            tmp_path,
            {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE},
        )
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Ambush Scarab", chaos_value=10.0),
            PriceResult(name="Other Scarab", chaos_value=2.0),
        ]
        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[
                        DimensionEntry(name="Ambush Scarab", count=200, percentage=20.0),
                        DimensionEntry(name="Other Scarab", count=100, percentage=10.0),
                    ],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)
        profits = svc.estimate_profit(mock_economy, "Mirage")
        for p in profits:
            assert p["expected_value"] >= 0
            assert p["spawn_chance_pct"] >= 0
            assert p["price_chaos"] >= 0

    def test_expected_value_sorted_desc(self, tmp_path):
        from poe.models.ninja.economy import PriceResult

        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="A Scarab", chaos_value=1.0),
            PriceResult(name="B Scarab", chaos_value=10.0),
        ]
        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[
                        DimensionEntry(name="A Scarab", count=500, percentage=50.0),
                        DimensionEntry(name="B Scarab", count=100, percentage=10.0),
                    ],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)
        profits = svc.estimate_profit(mock_economy, "Mirage")
        evs = [p["expected_value"] for p in profits]
        assert evs == sorted(evs, reverse=True)


class TestEstimateProfitEmptyPrices:
    def test_empty_scarab_prices_raises(self, tmp_path):
        from poe.services.ninja.errors import NinjaError

        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = []
        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[DimensionEntry(name="Ambush Scarab", count=100, percentage=10.0)],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)
        with pytest.raises(NinjaError, match="scarab prices"):
            svc.estimate_profit(mock_economy, "Mirage")


class TestAtlasProfitCliEmptyPrices:
    @patch("poe.commands.ninja.atlas.commands.AtlasService")
    @patch("poe.commands.ninja.atlas.commands.EconomyService")
    @patch("poe.commands.ninja.atlas.commands.DiscoveryService")
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_empty_scarab_prices_propagates_error(
        self, mock_ninja_cls, mock_disc_cls, mock_econ_cls, mock_atlas_cls
    ):
        from poe.services.ninja.errors import NinjaError

        mock_disc = MagicMock()
        mock_disc.get_current_league.return_value = MagicMock(name="Mirage")
        mock_disc_cls.return_value = mock_disc

        mock_atlas = MagicMock()
        mock_atlas.estimate_profit.side_effect = NinjaError("No scarab prices found")
        mock_atlas_cls.return_value = mock_atlas

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "profit", "Mirage", "--json"])
        assert result.exit_code == 1
        assert isinstance(result.exception, NinjaError)


class TestAtlasSearchHumanOutput:
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_search_default_human(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "search"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json


class TestAtlasNoCacheFlag:
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_search_no_cache(self, mock_cls):
        client = MagicMock(no_cache=True)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "search", "--no-cache", "--json"])
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True

    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_recommend_no_cache(self, mock_cls):
        client = MagicMock(no_cache=True)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "recommend", "--no-cache", "--json"])
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True


class TestAtlasSearchAllFilters:
    @pytest.mark.parametrize(
        ("flag", "value", "expected_param"),
        [
            ("--mechanics", "Scarabs", "mechanics"),
            ("--beacons", "Strange", "beacons"),
            ("--keystones", "Wandering", "keystones"),
            ("--travel", "long", "travel"),
            ("--blockers", "test", "blockers"),
            ("--scarab-specializations", "Ambush", "scarabspecializations"),
        ],
    )
    @patch("poe.commands.ninja.atlas.commands.NinjaClient")
    def test_atlas_filter_passed_through(self, mock_cls, flag, value, expected_param):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "atlas-tree-index-state" in path:
                return ATLAS_TREE_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = (FIXTURES / "search_result.bin").read_bytes()
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "atlas", "search", flag, value, "--json"])
        assert result.exit_code == 0
        proto_calls = client.get_protobuf.call_args_list
        search_calls = [c for c in proto_calls if "/search" in c.args[0]]
        assert search_calls
        assert search_calls[0].kwargs["params"][expected_param] == value


class TestPopularNodesInvariants:
    def test_results_sorted_by_count_desc(self, tmp_path):
        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        nodes = svc.get_popular_nodes(top_n=10)
        if len(nodes) > 1:
            counts = [n.count for n in nodes]
            assert counts == sorted(counts, reverse=True)


class TestHeatmapInvariants:
    def test_zone_only_valid_values(self, tmp_path):
        svc = _make_atlas_service(tmp_path, {"atlas-tree-index-state": ATLAS_TREE_INDEX_STATE})
        mock_builds = MagicMock()
        mock_builds.search.return_value = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="passive",
                    entries=[
                        DimensionEntry(name="N1", count=900, percentage=90.0),
                        DimensionEntry(name="N2", count=300, percentage=30.0),
                        DimensionEntry(name="N3", count=10, percentage=1.0),
                    ],
                ),
            ],
        )
        heatmap = svc.get_heatmap(mock_builds)
        for row in heatmap:
            assert row["zone"] in {"mandatory", "flex", "dead"}
            assert row["count"] >= 0
            assert 0 <= row["allocation_pct"] <= 100

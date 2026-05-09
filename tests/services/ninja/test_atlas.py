from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from poe.models.ninja.builds import DimensionEntry, ResolvedDimension, SearchResults
from poe.models.ninja.economy import PriceResult
from poe.services.ninja.atlas import AtlasService
from poe.services.ninja.errors import NinjaError


def _make_atlas_service(tmp_path):
    client = MagicMock(no_cache=False)
    discovery = MagicMock()
    return AtlasService(client, discovery, base_dir=tmp_path)


class TestEstimateProfit:
    def test_matches_scarab_prices_by_prefix(self, tmp_path):
        svc = _make_atlas_service(tmp_path)

        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Ambush Scarab of Containment", chaos_value=5.0),
            PriceResult(name="Ambush Scarab of Chaos", chaos_value=15.0),
            PriceResult(name="Harbinger Scarab of Regency", chaos_value=20.0),
        ]

        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[
                        DimensionEntry(name="Ambush Scarabs", count=200, percentage=20.0),
                        DimensionEntry(name="Harbinger Scarabs", count=100, percentage=10.0),
                    ],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)

        profits = svc.estimate_profit(mock_economy, "TestLeague")
        priced = [p for p in profits if p["price_chaos"] > 0]
        assert len(priced) > 0

    def test_exact_match_still_works(self, tmp_path):
        svc = _make_atlas_service(tmp_path)

        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Ambush Scarab", chaos_value=10.0),
        ]

        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[
                        DimensionEntry(name="Ambush Scarab", count=200, percentage=20.0),
                    ],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)

        profits = svc.estimate_profit(mock_economy, "TestLeague")
        assert len(profits) == 1
        assert profits[0]["price_chaos"] == 10.0
        assert profits[0]["expected_value"] == 2.0


class TestEstimateProfitNegativePaths:
    def test_raises_when_no_scarab_prices(self, tmp_path):
        svc = _make_atlas_service(tmp_path)

        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = []

        scarab_result = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="scarabspecializations",
                    entries=[
                        DimensionEntry(name="Ambush Scarab", count=200, percentage=20.0),
                    ],
                ),
            ],
        )
        svc.search = MagicMock(return_value=scarab_result)

        with pytest.raises(NinjaError, match="No scarab prices"):
            svc.estimate_profit(mock_economy, "BadLeague")

    def test_raises_includes_league_name_in_message(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = []
        svc.search = MagicMock(
            return_value=SearchResults(
                total=10,
                dimensions=[
                    ResolvedDimension(
                        id="scarabspecializations",
                        entries=[DimensionEntry(name="X", count=1, percentage=10.0)],
                    )
                ],
            )
        )
        with pytest.raises(NinjaError) as exc_info:
            svc.estimate_profit(mock_economy, "MySpecificLeague")
        assert "MySpecificLeague" in str(exc_info.value)

    def test_returns_empty_when_no_search_results(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        svc.search = MagicMock(return_value=None)
        result = svc.estimate_profit(MagicMock(), "League")
        assert result == []

    def test_returns_empty_when_no_scarab_dimension(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        svc.search = MagicMock(
            return_value=SearchResults(
                total=10,
                dimensions=[
                    ResolvedDimension(
                        id="mechanics",
                        entries=[DimensionEntry(name="Delve", count=1, percentage=10.0)],
                    )
                ],
            )
        )
        result = svc.estimate_profit(MagicMock(), "League")
        assert result == []


class TestEstimateProfitInvariants:
    def test_profit_is_non_negative_finite(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Ambush Scarab", chaos_value=10.0),
            PriceResult(name="Harbinger Scarab", chaos_value=20.0),
        ]
        svc.search = MagicMock(
            return_value=SearchResults(
                total=1000,
                dimensions=[
                    ResolvedDimension(
                        id="scarabspecializations",
                        entries=[
                            DimensionEntry(name="Ambush Scarab", count=200, percentage=20.0),
                            DimensionEntry(name="Harbinger Scarab", count=100, percentage=10.0),
                        ],
                    )
                ],
            )
        )
        profits = svc.estimate_profit(mock_economy, "L")
        for p in profits:
            assert p["expected_value"] >= 0.0
            assert math.isfinite(p["expected_value"])
            assert p["price_chaos"] >= 0.0
            assert math.isfinite(p["price_chaos"])
            assert 0.0 <= p["spawn_chance_pct"] <= 100.0

    def test_results_sorted_by_expected_value_desc(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Cheap Scarab", chaos_value=1.0),
            PriceResult(name="Expensive Scarab", chaos_value=100.0),
        ]
        svc.search = MagicMock(
            return_value=SearchResults(
                total=1000,
                dimensions=[
                    ResolvedDimension(
                        id="scarabspecializations",
                        entries=[
                            DimensionEntry(name="Cheap Scarab", count=900, percentage=90.0),
                            DimensionEntry(name="Expensive Scarab", count=100, percentage=10.0),
                        ],
                    )
                ],
            )
        )
        profits = svc.estimate_profit(mock_economy, "L")
        evs = [p["expected_value"] for p in profits]
        assert evs == sorted(evs, reverse=True)


class TestScarabPrefixMatching:
    def test_prefix_match_excludes_unrelated_scarabs(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Ambush Scarab of Containment", chaos_value=5.0),
            PriceResult(name="Ambush Scarab of Hidden Compartments", chaos_value=15.0),
            PriceResult(name="Bloody Scarab", chaos_value=99.0),
            PriceResult(name="Harbinger Scarab", chaos_value=22.0),
        ]
        svc.search = MagicMock(
            return_value=SearchResults(
                total=1000,
                dimensions=[
                    ResolvedDimension(
                        id="scarabspecializations",
                        entries=[
                            DimensionEntry(name="Ambush Scarabs", count=500, percentage=50.0),
                        ],
                    )
                ],
            )
        )
        profits = svc.estimate_profit(mock_economy, "L")
        assert len(profits) == 1
        avg_ambush = (5.0 + 15.0) / 2
        assert profits[0]["price_chaos"] == round(avg_ambush, 1)

    def test_rstrip_s_does_not_overstrip_double_s(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Cross Scarab", chaos_value=10.0),
            PriceResult(name="Crocodile Scarab", chaos_value=200.0),
        ]
        svc.search = MagicMock(
            return_value=SearchResults(
                total=10,
                dimensions=[
                    ResolvedDimension(
                        id="scarabspecializations",
                        entries=[
                            DimensionEntry(name="Cross", count=1, percentage=10.0),
                        ],
                    )
                ],
            )
        )
        profits = svc.estimate_profit(mock_economy, "L")
        assert profits[0]["price_chaos"] == 10.0

    def test_no_matching_prefix_yields_zero_price(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        mock_economy = MagicMock()
        mock_economy.get_prices.return_value = [
            PriceResult(name="Harbinger Scarab", chaos_value=20.0),
        ]
        svc.search = MagicMock(
            return_value=SearchResults(
                total=1000,
                dimensions=[
                    ResolvedDimension(
                        id="scarabspecializations",
                        entries=[
                            DimensionEntry(name="Bloody Scarabs", count=100, percentage=10.0),
                        ],
                    )
                ],
            )
        )
        profits = svc.estimate_profit(mock_economy, "L")
        assert len(profits) == 1
        assert profits[0]["price_chaos"] == 0.0
        assert profits[0]["expected_value"] == 0.0


class TestGetPopularNodes:
    def test_returns_empty_when_search_returns_none(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        svc.search = MagicMock(return_value=None)
        assert svc.get_popular_nodes() == []

    def test_returns_empty_when_no_dimensions(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        svc.search = MagicMock(return_value=SearchResults(total=0, dimensions=[]))
        assert svc.get_popular_nodes() == []

    def test_top_n_respected_and_sorted(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        svc.search = MagicMock(
            return_value=SearchResults(
                total=1000,
                dimensions=[
                    ResolvedDimension(
                        id="passives",
                        entries=[
                            DimensionEntry(name="A", count=100, percentage=10.0),
                            DimensionEntry(name="B", count=500, percentage=50.0),
                            DimensionEntry(name="C", count=300, percentage=30.0),
                        ],
                    )
                ],
            )
        )
        result = svc.get_popular_nodes(top_n=2)
        assert len(result) == 2
        assert result[0].count >= result[1].count
        assert result[0].name == "B"


class TestGetHeatmap:
    def test_returns_empty_when_no_search(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        builds = MagicMock()
        builds.search.return_value = None
        assert svc.get_heatmap(builds) == []

    def test_returns_empty_when_no_node_dim(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        builds = MagicMock()
        builds.search.return_value = SearchResults(
            total=10,
            dimensions=[
                ResolvedDimension(
                    id="other",
                    entries=[DimensionEntry(name="X", count=1, percentage=10.0)],
                )
            ],
        )
        assert svc.get_heatmap(builds) == []

    @pytest.mark.parametrize(
        ("pct", "expected_zone"),
        [
            (95.0, "mandatory"),
            (50.0, "mandatory"),
            (49.9, "flex"),
            (25.0, "flex"),
            (10.0, "flex"),
            (9.9, "dead"),
            (0.0, "dead"),
        ],
    )
    def test_zone_classification(self, tmp_path, pct, expected_zone):
        svc = _make_atlas_service(tmp_path)
        builds = MagicMock()
        builds.search.return_value = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="passives",
                    entries=[DimensionEntry(name="N", count=1, percentage=pct)],
                )
            ],
        )
        result = svc.get_heatmap(builds)
        assert result[0]["zone"] == expected_zone

    def test_heatmap_invariants(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        builds = MagicMock()
        builds.search.return_value = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="passives",
                    entries=[
                        DimensionEntry(name="A", count=900, percentage=90.0),
                        DimensionEntry(name="B", count=500, percentage=50.0),
                        DimensionEntry(name="C", count=10, percentage=1.0),
                    ],
                )
            ],
        )
        result = svc.get_heatmap(builds)
        for row in result:
            assert 0.0 <= row["allocation_pct"] <= 100.0
            assert row["count"] >= 0
            assert row["zone"] in {"mandatory", "flex", "dead"}


class TestSearchEmpty:
    def test_returns_none_when_no_snapshot_versions(self, tmp_path):
        svc = _make_atlas_service(tmp_path)
        state = MagicMock()
        state.snapshot_versions = []
        svc._discovery.get_atlas_tree_index_state.return_value = state
        assert svc.search() is None

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app
from poe.models.ninja.history import (
    CurrencyHistoryResponse,
    HistoryPoint,
)
from poe.services.ninja.economy import EconomyService
from poe.services.ninja.history import (
    HistoryService,
    _detect_crash,
    _detect_spike,
    _moving_average,
    _trend_direction,
    _volatility,
    analyze_history,
)
from tests.conftest import invoke_cli


def _make_points(values: list[float]) -> list[HistoryPoint]:
    return [HistoryPoint(value=v, days_ago=i, count=10) for i, v in enumerate(values)]


def _make_366_points(base: float = 100.0) -> list[HistoryPoint]:
    return [HistoryPoint(value=base + i * 0.1, days_ago=i, count=10) for i in range(366)]


CURRENCY_HISTORY_RESPONSE = {
    "payCurrencyGraphData": [{"count": 50, "value": 0.058, "daysAgo": i} for i in range(366)],
    "receiveCurrencyGraphData": [
        {"count": 100, "value": 17.5 + i * 0.01, "daysAgo": i} for i in range(366)
    ],
}

_NOW = datetime.now(UTC)


def _iso(days_ago: int) -> str:
    return (_NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


CURRENCY_DETAILS_RESPONSE = {
    "item": {
        "id": "exalted",
        "name": "Exalted Orb",
        "detailsId": "exalted-orb",
        "category": "Currency",
        "image": "",
    },
    "pairs": [
        {
            "id": "chaos",
            "rate": 17.5,
            "volumePrimaryValue": 100,
            "history": [
                {
                    "timestamp": _iso(i),
                    "rate": 17.5 + i * 0.01,
                    "volumePrimaryValue": 100,
                }
                for i in range(366)
            ],
        },
    ],
    "core": {},
}

ITEM_HISTORY_RESPONSE = [{"count": 30, "value": 15000.0 - i * 10, "daysAgo": i} for i in range(366)]

CURRENCY_OVERVIEW = {
    "lines": [
        {
            "currencyTypeName": "Exalted Orb",
            "chaosEquivalent": 17.5,
            "detailsId": "exalted-orb",
        },
    ],
    "currencyDetails": [
        {"id": 42, "name": "Exalted Orb", "tradeId": "exalted-orb"},
    ],
}

ITEM_OVERVIEW = {
    "lines": [
        {
            "id": 100,
            "name": "Headhunter",
            "chaosValue": 15000.0,
            "sparkLine": {"data": [], "totalChange": 0.0},
            "lowConfidenceSparkLine": None,
            "implicitModifiers": [],
            "explicitModifiers": [],
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


class TestMovingAverage:
    def test_simple(self):
        assert _moving_average([10.0, 20.0, 30.0], 3) == pytest.approx(20.0)

    def test_window_smaller_than_data(self):
        assert _moving_average([10.0, 20.0, 30.0, 40.0], 2) == pytest.approx(15.0)

    def test_skips_zeros(self):
        assert _moving_average([0.0, 10.0, 20.0], 3) == pytest.approx(15.0)

    def test_all_zeros(self):
        assert _moving_average([0.0, 0.0, 0.0], 3) is None

    def test_empty(self):
        assert _moving_average([], 7) is None

    def test_handles_nullish_values(self):
        assert _moving_average([0.0, 0.0, 5.0], 3) == pytest.approx(5.0)


class TestVolatility:
    def test_constant_values(self):
        assert _volatility([10.0, 10.0, 10.0], 3) == pytest.approx(0.0)

    def test_varying_values(self):
        result = _volatility([10.0, 20.0, 30.0], 3)
        assert result is not None
        assert result > 0

    def test_insufficient_data(self):
        assert _volatility([10.0], 3) is None

    def test_with_zeros(self):
        assert _volatility([0.0, 0.0], 2) is None


class TestDetectSpike:
    def test_spike_detected(self):
        values = [300.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        assert _detect_spike(values) is True

    def test_no_spike(self):
        values = [105.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        assert _detect_spike(values) is False

    def test_too_few_points(self):
        assert _detect_spike([100.0, 200.0]) is False

    def test_zero_baseline(self):
        assert _detect_spike([100.0, 0.0, 0.0, 0.0]) is False


class TestDetectCrash:
    def test_crash_detected(self):
        values = [30.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        assert _detect_crash(values) is True

    def test_no_crash(self):
        values = [95.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        assert _detect_crash(values) is False

    def test_too_few_points(self):
        assert _detect_crash([10.0, 100.0]) is False


class TestTrendDirection:
    def test_rising(self):
        values = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0]
        assert _trend_direction(values) == "rising"

    def test_falling(self):
        values = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        assert _trend_direction(values) == "falling"

    def test_stable(self):
        values = [100.0, 101.0, 99.0, 100.0, 101.0, 99.0, 100.0]
        assert _trend_direction(values) == "stable"

    def test_too_few_points(self):
        assert _trend_direction([100.0, 200.0]) == "stable"


class TestAnalyzeHistory:
    def test_empty_data(self):
        result = analyze_history([])
        assert result.current_price == 0.0

    def test_366_entries(self):
        points = _make_366_points(100.0)
        result = analyze_history(points)
        assert result.current_price == 100.0
        assert result.average_7d is not None
        assert result.average_30d is not None
        assert result.min_price is not None
        assert result.max_price is not None
        assert result.league_start_price is not None

    def test_spike_in_data(self):
        values = [300.0] + [100.0] * 30
        points = _make_points(values)
        result = analyze_history(points)
        assert result.spike_detected is True
        assert result.crash_detected is False

    def test_crash_in_data(self):
        values = [30.0] + [100.0] * 30
        points = _make_points(values)
        result = analyze_history(points)
        assert result.crash_detected is True

    def test_change_percentages(self):
        points = _make_366_points(100.0)
        result = analyze_history(points)
        assert result.change_7d_pct is not None
        assert result.change_30d_pct is not None

    def test_volatility_present(self):
        points = _make_points([10.0, 20.0, 15.0, 25.0, 12.0, 18.0, 22.0] * 5)
        result = analyze_history(points)
        assert result.volatility_30d is not None
        assert result.volatility_30d > 0

    def test_handles_zero_values(self):
        points = _make_points([0.0, 0.0, 10.0, 0.0, 20.0])
        result = analyze_history(points)
        assert result.min_price == 10.0


class TestModelParsing:
    def test_currency_history_parses(self):
        resp = CurrencyHistoryResponse.model_validate(CURRENCY_HISTORY_RESPONSE)
        assert len(resp.receive_currency_graph_data) == 366
        assert len(resp.pay_currency_graph_data) == 366
        assert resp.receive_currency_graph_data[0].days_ago == 0

    def test_item_history_bare_array(self):
        points = [HistoryPoint.model_validate(p) for p in ITEM_HISTORY_RESPONSE]
        assert len(points) == 366
        assert points[0].value == 15000.0
        assert points[0].days_ago == 0

    def test_history_point_alias(self):
        p = HistoryPoint.model_validate({"count": 5, "value": 10.0, "daysAgo": 3})
        assert p.days_ago == 3

    def test_empty_currency_history(self):
        resp = CurrencyHistoryResponse.model_validate(
            {
                "payCurrencyGraphData": [],
                "receiveCurrencyGraphData": [],
            }
        )
        assert resp.pay_currency_graph_data == []


def _make_history_service(tmp_path, fixture_map=None):
    client = MagicMock(no_cache=False)

    def get_json(_path, **_kwargs):
        if fixture_map:
            for pattern, data in fixture_map.items():
                if pattern in _path:
                    return data
        msg = f"Unmocked: {_path}"
        raise ValueError(msg)

    client.get_json.side_effect = get_json

    economy_client = MagicMock(no_cache=False)
    economy_client.get_json.side_effect = get_json
    economy = EconomyService(economy_client, base_dir=tmp_path)

    return HistoryService(client, economy, base_dir=tmp_path)


class TestHistoryService:
    def test_currency_history(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "exchange/current/details": CURRENCY_DETAILS_RESPONSE,
            },
        )
        resp = svc.get_currency_history("Mirage", "exalted-orb", "Currency")
        assert len(resp.receive_currency_graph_data) == 366

    def test_item_history(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "item/history": ITEM_HISTORY_RESPONSE,
            },
        )
        points = svc.get_item_history("Mirage", 100, "UniqueAccessory")
        assert len(points) == 366

    def test_item_history_non_list(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "item/history": {"unexpected": "format"},
            },
        )
        points = svc.get_item_history("Mirage", 100, "UniqueAccessory")
        assert points == []

    def test_get_price_history_currency(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "currency/overview": CURRENCY_OVERVIEW,
                "exchange/current/details": CURRENCY_DETAILS_RESPONSE,
            },
        )
        result = svc.get_price_history("Mirage", "Exalted Orb", "Currency")
        assert result is not None
        assert result.item_name == "Exalted Orb"
        assert len(result.data_points) == 366
        assert result.analysis.current_price > 0

    def test_get_price_history_item(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "item/overview": ITEM_OVERVIEW,
                "item/history": ITEM_HISTORY_RESPONSE,
            },
        )
        result = svc.get_price_history("Mirage", "Headhunter", "UniqueAccessory")
        assert result is not None
        assert result.item_name == "Headhunter"
        assert len(result.data_points) == 366

    def test_currency_not_found(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "currency/overview": CURRENCY_OVERVIEW,
            },
        )
        result = svc.get_price_history("Mirage", "Fake Currency", "Currency")
        assert result is None

    def test_item_not_found(self, tmp_path):
        svc = _make_history_service(
            tmp_path,
            {
                "item/overview": ITEM_OVERVIEW,
            },
        )
        result = svc.get_price_history("Mirage", "Fake Item", "UniqueAccessory")
        assert result is None


class TestPriceHistoryCli:
    @patch("poe.commands.ninja.price.commands.NinjaClient")
    def test_price_history_found(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return INDEX_STATE
            if "currency/overview" in path:
                return CURRENCY_OVERVIEW
            if "exchange/current/details" in path:
                return CURRENCY_DETAILS_RESPONSE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "price", "history", "Exalted Orb", "Currency", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["item_name"] == "Exalted Orb"
        assert "analysis" in data

    @patch("poe.commands.ninja.price.commands.NinjaClient")
    def test_price_history_not_found(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return INDEX_STATE
            if "currency/overview" in path:
                return CURRENCY_OVERVIEW
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "price", "history", "Fake Orb", "Currency", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data

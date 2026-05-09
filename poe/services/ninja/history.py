from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from poe.models.ninja.history import (
    CurrencyDetailsResponse,
    CurrencyHistoryResponse,
    HistoryPoint,
    PriceHistory,
    TrendAnalysis,
)
from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.constants import (
    NINJA_ENDPOINTS,
    NINJA_POE1_CURRENCY_STASH_TYPES,
)

CHAOS_PAIR_ID = "chaos"

if TYPE_CHECKING:
    from poe.services.ninja.client import NinjaClient
    from poe.services.ninja.economy import EconomyService

SPIKE_THRESHOLD = 1.5
CRASH_THRESHOLD = 0.5
SUSTAINED_TREND_DAYS = 7
MIN_DATA_POINTS = 3
MIN_VARIANCE_POINTS = 2
TREND_DOMINANCE = 0.7
WINDOW_7D = 7
WINDOW_30D = 30


def _moving_average(values: list[float], window: int) -> float | None:
    recent = values[:window]
    valid = [v for v in recent if v > 0]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _volatility(values: list[float], window: int) -> float | None:
    recent = values[:window]
    valid = [v for v in recent if v > 0]
    if len(valid) < MIN_VARIANCE_POINTS:
        return None
    mean = sum(valid) / len(valid)
    variance = sum((v - mean) ** 2 for v in valid) / len(valid)
    return math.sqrt(variance)


def _pct_change(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return ((current - previous) / previous) * 100


def _detect_spike(values: list[float], threshold: float = SPIKE_THRESHOLD) -> bool:
    if len(values) < MIN_DATA_POINTS:
        return False
    recent = values[0]
    baseline = _moving_average(values[1 : WINDOW_7D + 1], WINDOW_7D)
    if baseline is None or baseline <= 0:
        return False
    return recent / baseline >= threshold


def _detect_crash(values: list[float], threshold: float = CRASH_THRESHOLD) -> bool:
    if len(values) < MIN_DATA_POINTS:
        return False
    recent = values[0]
    baseline = _moving_average(values[1 : WINDOW_7D + 1], WINDOW_7D)
    if baseline is None or baseline <= 0:
        return False
    return recent / baseline <= threshold


def _trend_direction(values: list[float]) -> str:
    if len(values) < SUSTAINED_TREND_DAYS:
        return "stable"

    recent = values[:SUSTAINED_TREND_DAYS]
    valid = [(i, v) for i, v in enumerate(recent) if v > 0]
    if len(valid) < MIN_DATA_POINTS:
        return "stable"

    rising = sum(1 for i in range(len(valid) - 1) if valid[i][1] > valid[i + 1][1])
    falling = sum(1 for i in range(len(valid) - 1) if valid[i][1] < valid[i + 1][1])

    ratio = len(valid) - 1
    if ratio == 0:
        return "stable"
    if rising / ratio >= TREND_DOMINANCE:
        return "rising"
    if falling / ratio >= TREND_DOMINANCE:
        return "falling"
    return "stable"


def analyze_history(points: list[HistoryPoint]) -> TrendAnalysis:
    sorted_points = sorted(points, key=lambda p: p.days_ago)
    values = [p.value for p in sorted_points]

    if not values:
        return TrendAnalysis()

    current = values[0]
    all_valid = [v for v in values if v > 0]

    avg_7 = _moving_average(values, WINDOW_7D)
    avg_30 = _moving_average(values, WINDOW_30D)

    old_7 = (
        _moving_average(values[WINDOW_7D : WINDOW_7D * 2], WINDOW_7D)
        if len(values) > WINDOW_7D
        else None
    )
    old_30 = (
        _moving_average(values[WINDOW_30D : WINDOW_30D * 2], WINDOW_30D)
        if len(values) > WINDOW_30D
        else None
    )

    vol_30 = _volatility(values, WINDOW_30D)

    return TrendAnalysis(
        current_price=current,
        average_7d=round(avg_7, 2) if avg_7 is not None else None,
        average_30d=round(avg_30, 2) if avg_30 is not None else None,
        change_7d_pct=(
            round(_pct_change(avg_7, old_7), 2) if avg_7 is not None and old_7 is not None else None
        ),
        change_30d_pct=(
            round(_pct_change(avg_30, old_30), 2)
            if avg_30 is not None and old_30 is not None
            else None
        ),
        volatility_30d=round(vol_30, 2) if vol_30 is not None else None,
        min_price=min(all_valid) if all_valid else None,
        max_price=max(all_valid) if all_valid else None,
        league_start_price=values[-1] if values else None,
        spike_detected=_detect_spike(values),
        crash_detected=_detect_crash(values),
        trend_direction=_trend_direction(values),
    )


class HistoryService:
    """Fetches and analyzes price history from poe.ninja."""

    def __init__(
        self,
        client: NinjaClient,
        economy: EconomyService,
        base_dir: Any = None,
    ) -> None:
        self._client = client
        self._economy = economy
        self._cache_dir = base_dir or ninja_cache.cache_dir()

    def _fetch_cached(self, cache_key: str, path: str, params: dict[str, str]) -> Any:
        if not self._client.no_cache and ninja_cache.is_fresh(
            self._cache_dir, cache_key, "history"
        ):
            cached = ninja_cache.read_cache(self._cache_dir, cache_key)
            if cached is not None:
                return cached
        data = self._client.get_json(path, params=params)
        ninja_cache.write_cache(self._cache_dir, cache_key, data)
        return data

    def get_currency_history(
        self,
        league: str,
        currency_slug: str,
        currency_type: str = "Currency",
    ) -> CurrencyHistoryResponse:
        cache_key = f"history_currency_{league}_{currency_type}_{currency_slug}"
        path = NINJA_ENDPOINTS["currency_history"]
        params = {
            "league": league,
            "type": currency_type,
            "id": currency_slug,
        }
        raw = self._fetch_cached(cache_key, path, params)
        details = CurrencyDetailsResponse.model_validate(raw)
        chaos_pair = next((p for p in details.pairs if p.id == CHAOS_PAIR_ID), None)
        if chaos_pair is None:
            return CurrencyHistoryResponse()
        now = datetime.now(UTC)
        receive_points: list[HistoryPoint] = []
        for entry in chaos_pair.history:
            try:
                ts = datetime.fromisoformat(entry.timestamp)
            except ValueError:
                continue
            receive_points.append(
                HistoryPoint(
                    count=int(entry.volume_primary_value),
                    value=entry.rate,
                    days_ago=(now - ts).days,
                )
            )
        return CurrencyHistoryResponse(receive_currency_graph_data=receive_points)

    def get_item_history(
        self,
        league: str,
        item_id: int,
        item_type: str,
    ) -> list[HistoryPoint]:
        cache_key = f"history_item_{league}_{item_type}_{item_id}"
        path = NINJA_ENDPOINTS["item_history"]
        params = {
            "league": league,
            "type": item_type,
            "id": str(item_id),
        }
        raw = self._fetch_cached(cache_key, path, params)
        if isinstance(raw, list):
            return [HistoryPoint.model_validate(p) for p in raw]
        return []

    def get_price_history(
        self,
        league: str,
        item_name: str,
        item_type: str,
        *,
        language: str = "en",
    ) -> PriceHistory | None:
        if item_type in NINJA_POE1_CURRENCY_STASH_TYPES:
            return self._currency_price_history(league, item_name, item_type, language=language)
        return self._item_price_history(league, item_name, item_type, language=language)

    def _currency_price_history(
        self,
        league: str,
        item_name: str,
        item_type: str,
        *,
        language: str = "en",
    ) -> PriceHistory | None:
        overview = self._economy.get_currency_overview(league, item_type, language=language)
        line = next(
            (ln for ln in overview.lines if ln.currency_type_name.lower() == item_name.lower()),
            None,
        )
        if not line or not line.details_id:
            return None

        resp = self.get_currency_history(league, line.details_id, item_type)
        points = resp.receive_currency_graph_data
        analysis = analyze_history(points)

        return PriceHistory(
            item_name=item_name,
            item_type=item_type,
            league=league,
            data_points=points,
            pay_data_points=resp.pay_currency_graph_data,
            analysis=analysis,
        )

    def _item_price_history(
        self,
        league: str,
        item_name: str,
        item_type: str,
        *,
        language: str = "en",
    ) -> PriceHistory | None:
        overview = self._economy.get_item_overview(league, item_type, language=language)
        line = next(
            (ln for ln in overview.lines if ln.name.lower() == item_name.lower()),
            None,
        )
        if not line:
            return None

        points = self.get_item_history(league, line.id, item_type)
        analysis = analyze_history(points)

        return PriceHistory(
            item_name=item_name,
            item_type=item_type,
            league=league,
            data_points=points,
            analysis=analysis,
        )

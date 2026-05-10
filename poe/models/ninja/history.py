from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoryPoint(BaseModel):
    """A single daily price data point."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    count: int = 0
    value: float = 0.0
    days_ago: int = Field(0, alias="daysAgo")

    @field_validator("value")
    @classmethod
    def _validate_value_finite(cls, v: float) -> float:
        if not isfinite(v):
            raise ValueError("value must be finite (not NaN or +/-inf)")
        return v


class CurrencyPairHistoryEntry(BaseModel):
    """A single history entry within a currency exchange pair."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    timestamp: str = ""
    rate: float = 0.0
    volume_primary_value: float = Field(0.0, alias="volumePrimaryValue")


class CurrencyPair(BaseModel):
    """An exchange pair from the currency details endpoint."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: str = ""
    rate: float = 0.0
    volume_primary_value: float = Field(0.0, alias="volumePrimaryValue")
    history: list[CurrencyPairHistoryEntry] = Field(default_factory=list)


class CurrencyDetailsItem(BaseModel):
    """The 'item' block in the currency details response."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: str = ""
    name: str = ""
    image: str = ""
    category: str = ""
    details_id: str = Field("", alias="detailsId")


class CurrencyDetailsResponse(BaseModel):
    """Raw response from /poe1/api/economy/exchange/current/details."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    item: CurrencyDetailsItem = Field(default_factory=CurrencyDetailsItem)
    pairs: list[CurrencyPair] = Field(default_factory=list)


class CurrencyHistoryResponse(BaseModel):
    """Translated currency history (pay + receive directions vs Chaos Orb).

    The poe.ninja API returns a nested `{item, pairs, core}` shape; we extract
    the chaos pair and translate it to this flat list-of-points form so
    downstream consumers (analyze_history, PriceHistory) don't need to know
    about pair structure.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    pay_currency_graph_data: list[HistoryPoint] = Field(
        default_factory=list, alias="payCurrencyGraphData"
    )
    receive_currency_graph_data: list[HistoryPoint] = Field(
        default_factory=list, alias="receiveCurrencyGraphData"
    )


class TrendAnalysis(BaseModel):
    """Analytics summary for a price history series."""

    model_config = ConfigDict(validate_assignment=True)

    current_price: float = 0.0
    average_7d: float | None = None
    average_30d: float | None = None
    change_7d_pct: float | None = None
    change_30d_pct: float | None = None
    volatility_30d: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    league_start_price: float | None = None
    spike_detected: bool = False
    crash_detected: bool = False
    trend_direction: str = "stable"


class PriceHistory(BaseModel):
    """Full price history with analytics for an item."""

    model_config = ConfigDict(validate_assignment=True)

    item_name: str
    item_type: str
    league: str
    data_points: list[HistoryPoint] = []
    pay_data_points: list[HistoryPoint] = []
    analysis: TrendAnalysis = TrendAnalysis()

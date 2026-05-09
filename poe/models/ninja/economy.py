from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SparkLine(BaseModel):
    """7-day price trend data."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    data: list[float | None] = []
    total_change: float = Field(0.0, alias="totalChange")


class TradeData(BaseModel):
    """Buy/sell trade sampling data from currency overview."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: int = 0
    league_id: int = Field(0, alias="league_id")
    pay_currency_id: int = Field(0, alias="pay_currency_id")
    get_currency_id: int = Field(0, alias="get_currency_id")
    sample_time_utc: str = Field("", alias="sample_time_utc")
    count: int = 0
    value: float = 0.0
    data_point_count: int = Field(0, alias="data_point_count")
    includes_secondary: bool = Field(default=False, alias="includes_secondary")
    listing_count: int = Field(0, alias="listing_count")


class CurrencyDetail(BaseModel):
    """Currency metadata including trade site ID."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: int = 0
    icon: str | None = None
    name: str = ""
    trade_id: str | None = Field(None, alias="tradeId")


class CurrencyLine(BaseModel):
    """A single currency entry from the stash currency overview."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    currency_type_name: str = Field("", alias="currencyTypeName")
    pay: TradeData | None = None
    receive: TradeData | None = None
    pay_spark_line: SparkLine | None = Field(None, alias="paySparkLine")
    receive_spark_line: SparkLine | None = Field(None, alias="receiveSparkLine")
    low_confidence_pay_spark_line: SparkLine | None = Field(None, alias="lowConfidencePaySparkLine")
    low_confidence_receive_spark_line: SparkLine | None = Field(
        None, alias="lowConfidenceReceiveSparkLine"
    )
    chaos_equivalent: float = Field(0.0, alias="chaosEquivalent")
    details_id: str = Field("", alias="detailsId")


class CurrencyOverviewResponse(BaseModel):
    """Response from the stash currency overview endpoint."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    lines: list[CurrencyLine] = []
    currency_details: list[CurrencyDetail] = Field([], alias="currencyDetails")


class Modifier(BaseModel):
    """Item modifier text."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    text: str = ""
    optional: bool = False


class TradeInfo(BaseModel):
    """Trade filter info for an item line."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    mod: str = ""
    min: float = 0.0
    max: float = 0.0
    option: str | None = None


class ItemLine(BaseModel):
    """A single item entry from the stash item overview."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: int = 0
    name: str = ""
    icon: str | None = None
    base_type: str | None = Field(None, alias="baseType")
    stack_size: int | None = Field(None, alias="stackSize")
    item_class: int | None = Field(None, alias="itemClass")
    variant: str | None = None
    level_required: int | None = Field(None, alias="levelRequired")
    links: int | None = None
    item_type: str | None = Field(None, alias="itemType")
    corrupted: bool | None = None
    gem_level: int | None = Field(None, alias="gemLevel")
    gem_quality: int | None = Field(None, alias="gemQuality")
    map_tier: int | None = Field(None, alias="mapTier")
    art_filename: str | None = Field(None, alias="artFilename")
    prophecy_text: str | None = Field(None, alias="prophecyText")
    spark_line: SparkLine | None = Field(None, alias="sparkLine")
    low_confidence_spark_line: SparkLine | None = Field(None, alias="lowConfidenceSparkLine")
    implicit_modifiers: list[Modifier] = Field([], alias="implicitModifiers")
    explicit_modifiers: list[Modifier] = Field([], alias="explicitModifiers")
    mutated_modifiers: list[Modifier] = Field([], alias="mutatedModifiers")
    flavour_text: str | None = Field(None, alias="flavourText")
    chaos_value: float | None = Field(None, alias="chaosValue")
    exalted_value: float | None = Field(None, alias="exaltedValue")
    divine_value: float | None = Field(None, alias="divineValue")
    count: int | None = None
    listing_count: int | None = Field(None, alias="listingCount")
    details_id: str | None = Field(None, alias="detailsId")
    trade_info: list[TradeInfo] | None = Field(None, alias="tradeInfo")
    trade_filter: dict | None = Field(None, alias="tradeFilter")


class ItemOverviewResponse(BaseModel):
    """Response from the stash item overview endpoint."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    lines: list[ItemLine] = []


class CoreItem(BaseModel):
    """Currency item in the exchange core rates."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: str = ""
    name: str = ""
    image: str = ""
    category: str = ""
    details_id: str = Field("", alias="detailsId")


class ExchangeCore(BaseModel):
    """Core rates and primary/secondary currency info."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    items: list[CoreItem] = []
    rates: dict[str, float] = {}
    primary: str = ""
    secondary: str = ""


class ExchangeLine(BaseModel):
    """A single item entry from the exchange overview."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: str = ""
    primary_value: float = Field(0.0, alias="primaryValue")
    volume_primary_value: float | None = Field(None, alias="volumePrimaryValue")
    max_volume_currency: str = Field("", alias="maxVolumeCurrency")
    max_volume_rate: float = Field(0.0, alias="maxVolumeRate")
    sparkline: SparkLine | None = None


class ExchangeItem(BaseModel):
    """Item metadata from the exchange overview."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    id: str = ""
    name: str = ""
    image: str = ""
    category: str = ""
    details_id: str = Field("", alias="detailsId")


class ExchangeOverviewResponse(BaseModel):
    """Response from the exchange overview endpoint."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    core: ExchangeCore = ExchangeCore()
    lines: list[ExchangeLine] = []
    items: list[ExchangeItem] = []


class PriceResult(BaseModel):
    """Normalized price result returned by EconomyService."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    chaos_value: float
    divine_value: float | None = None
    details_id: str = ""
    trade_id: str | None = None
    icon: str | None = None
    variant: str | None = None
    links: int | None = None
    corrupted: bool | None = None
    gem_level: int | None = None
    gem_quality: int | None = None
    map_tier: int | None = None
    listing_count: int | None = None
    sparkline: SparkLine | None = None
    low_confidence: bool = False
    category: str = ""
    fetched_at: str | None = None
    cache_age_seconds: float | None = None


class CraftingPrices(BaseModel):
    """Chaos-denominated prices for crafting materials."""

    model_config = ConfigDict(validate_assignment=True)

    currency: dict[str, float] = {}
    fossils: dict[str, float] = {}
    essences: dict[str, float] = {}
    resonators: dict[str, float] = {}
    beasts: dict[str, float] = {}
    fragments: dict[str, float] = {}
    scarabs: dict[str, float] = {}
    oils: dict[str, float] = {}

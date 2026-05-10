from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from poe.models.ninja.economy import (
    CraftingPrices,
    CurrencyOverviewResponse,
    ExchangeOverviewResponse,
    ItemOverviewResponse,
    PriceResult,
)
from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.constants import (
    CRAFTING_TYPE_MAP,
    CURRENCY_ALIASES,
    NINJA_DETAILS_BASE,
    NINJA_ENDPOINTS,
    NINJA_LOW_CONFIDENCE_THRESHOLD,
    NINJA_POE1_CURRENCY_STASH_TYPES,
    NINJA_POE1_STASH_TYPES,
    POE2_TYPE_CANONICAL,
    TYPE_CANONICAL,
)
from poe.services.ninja.errors import ApiSchemaError, NinjaError

if TYPE_CHECKING:
    from poe.services.ninja.client import NinjaClient

_logger = logging.getLogger("poe.ninja.economy")


def _normalize_type_key(item_type: str) -> str:
    """Strip whitespace, underscores, and hyphens; lowercase.

    So 'divination_card', 'divination card', 'Divination-Card',
    'DIVINATIONCARD' all match the same canonical key 'divinationcard'.
    """
    return "".join(c for c in item_type.lower() if c.isalnum())


def _route_type(item_type: str, *, game: str) -> tuple[str, str]:
    key = _normalize_type_key(item_type)
    if game == "poe2":
        # POE2_TYPE_CANONICAL keys are already lowercased; normalize them too
        # so user input like "exotic_currency" matches "exoticcurrency".
        poe2_normalized = {_normalize_type_key(k): v for k, v in POE2_TYPE_CANONICAL.items()}
        canonical_poe2 = poe2_normalized.get(key)
        if canonical_poe2 is None:
            valid = sorted(POE2_TYPE_CANONICAL.values())
            raise ApiSchemaError(
                f"Unknown item type '{item_type}' for {game}. Valid types: {valid}"
            )
        return "poe2_exchange", canonical_poe2
    poe1_normalized = {_normalize_type_key(k): v for k, v in TYPE_CANONICAL.items()}
    canonical = poe1_normalized.get(key)
    if canonical is None:
        valid = sorted(TYPE_CANONICAL.values())
        raise ApiSchemaError(f"Unknown item type '{item_type}' for {game}. Valid types: {valid}")
    if canonical in NINJA_POE1_CURRENCY_STASH_TYPES:
        return "poe1_stash_currency", canonical
    if canonical in NINJA_POE1_STASH_TYPES:
        return "poe1_stash_item", canonical
    return "poe1_exchange", canonical


def _endpoint_path(route: str) -> str:
    if route == "poe1_stash_currency":
        return NINJA_ENDPOINTS["poe1_currency_overview"]
    if route == "poe1_stash_item":
        return NINJA_ENDPOINTS["poe1_item_overview"]
    if route == "poe1_exchange":
        return NINJA_ENDPOINTS["poe1_exchange_overview"]
    return NINJA_ENDPOINTS["poe2_exchange_overview"]


def _exchange_chaos_value(
    primary_value: float, core_rates: dict[str, float], primary: str
) -> float:
    if primary == "chaos":
        return primary_value
    chaos_rate = core_rates.get("chaos", 0.0)
    if chaos_rate <= 0:
        return 0.0
    divine_to_chaos = 1.0 / chaos_rate
    return primary_value * divine_to_chaos


class EconomyService:
    """Fetches and normalizes economy data from poe.ninja."""

    def __init__(self, client: NinjaClient, base_dir: Any = None) -> None:
        self._client = client
        self._cache_dir = base_dir or ninja_cache.cache_dir()

    def _fetch_cached(self, cache_key: str, path: str, params: dict[str, str]) -> Any:
        if not self._client.no_cache and ninja_cache.is_fresh(
            self._cache_dir, cache_key, "economy"
        ):
            cached = ninja_cache.read_cache(self._cache_dir, cache_key)
            if cached is not None:
                return cached
        data = self._client.get_json(path, params=params)
        ninja_cache.write_cache(self._cache_dir, cache_key, data)
        return data

    def get_currency_overview(
        self, league: str, item_type: str, *, language: str = "en"
    ) -> CurrencyOverviewResponse:
        cache_key = f"currency_{league}_{item_type}_{language}"
        path = NINJA_ENDPOINTS["poe1_currency_overview"]
        params = {"league": league, "type": item_type, "language": language}
        raw = self._fetch_cached(cache_key, path, params)
        try:
            return CurrencyOverviewResponse.model_validate(raw)
        except ValidationError as e:
            _logger.warning(
                "currency overview schema mismatch (league=%r type=%r): %s — returning empty",
                league,
                item_type,
                e,
            )
            return CurrencyOverviewResponse()

    def get_item_overview(
        self, league: str, item_type: str, *, language: str = "en"
    ) -> ItemOverviewResponse:
        cache_key = f"item_{league}_{item_type}_{language}"
        path = NINJA_ENDPOINTS["poe1_item_overview"]
        params = {"league": league, "type": item_type, "language": language}
        raw = self._fetch_cached(cache_key, path, params)
        try:
            return ItemOverviewResponse.model_validate(raw)
        except ValidationError as e:
            _logger.warning(
                "item overview schema mismatch (league=%r type=%r): %s — returning empty",
                league,
                item_type,
                e,
            )
            return ItemOverviewResponse()

    def get_exchange_overview(
        self, league: str, item_type: str, *, game: str = "poe1"
    ) -> ExchangeOverviewResponse:
        cache_key = f"exchange_{game}_{league}_{item_type}"
        endpoint_key = "poe2_exchange_overview" if game == "poe2" else "poe1_exchange_overview"
        path = NINJA_ENDPOINTS[endpoint_key]
        params = {"league": league, "type": item_type}
        raw = self._fetch_cached(cache_key, path, params)
        try:
            return ExchangeOverviewResponse.model_validate(raw)
        except ValidationError as e:
            _logger.warning(
                "exchange overview schema mismatch "
                "(game=%r league=%r type=%r): %s — returning empty",
                game,
                league,
                item_type,
                e,
            )
            return ExchangeOverviewResponse()

    def get_prices(
        self,
        league: str,
        item_type: str,
        *,
        game: str = "poe1",
        language: str = "en",
    ) -> list[PriceResult]:
        route, canonical_type = _route_type(item_type, game=game)

        if route == "poe1_stash_currency":
            cache_key = f"currency_{league}_{canonical_type}_{language}"
            results = self._prices_from_currency(league, canonical_type, language=language)
        elif route == "poe1_stash_item":
            cache_key = f"item_{league}_{canonical_type}_{language}"
            results = self._prices_from_items(league, canonical_type, language=language)
        else:
            cache_key = f"exchange_{game}_{league}_{canonical_type}"
            results = self._prices_from_exchange(league, canonical_type, game=game)

        freshness = ninja_cache.get_freshness(self._cache_dir, cache_key, "economy")
        for r in results:
            r.fetched_at = freshness.get("fetched_at")
            r.cache_age_seconds = freshness.get("cache_age_seconds")
        return results

    def _prices_from_currency(
        self, league: str, item_type: str, *, language: str = "en"
    ) -> list[PriceResult]:
        resp = self.get_currency_overview(league, item_type, language=language)
        details_map = {d.name: d for d in resp.currency_details}
        results = []
        for line in resp.lines:
            detail = details_map.get(line.currency_type_name)
            try:
                results.append(
                    PriceResult(
                        name=line.currency_type_name,
                        chaos_value=line.chaos_equivalent,
                        details_id=line.details_id,
                        trade_id=detail.trade_id if detail else None,
                        icon=detail.icon if detail else None,
                        listing_count=line.receive.listing_count if line.receive else None,
                        sparkline=line.receive_spark_line,
                        low_confidence=line.receive is None,
                        category=item_type,
                    ),
                )
            except ValidationError as e:
                _logger.warning(
                    "skipping currency line name=%r chaos=%r: %s",
                    line.currency_type_name,
                    line.chaos_equivalent,
                    e,
                )
        return results

    def _prices_from_items(
        self, league: str, item_type: str, *, language: str = "en"
    ) -> list[PriceResult]:
        resp = self.get_item_overview(league, item_type, language=language)
        results = []
        for line in resp.lines:
            chaos = line.chaos_value or 0.0
            try:
                results.append(
                    PriceResult(
                        name=line.name,
                        chaos_value=chaos,
                        divine_value=line.divine_value,
                        details_id=line.details_id or "",
                        icon=line.icon,
                        variant=line.variant,
                        links=line.links,
                        corrupted=line.corrupted,
                        gem_level=line.gem_level,
                        gem_quality=line.gem_quality,
                        map_tier=line.map_tier,
                        listing_count=line.listing_count,
                        sparkline=line.spark_line,
                        low_confidence=line.count is not None
                        and line.count < NINJA_LOW_CONFIDENCE_THRESHOLD,
                        category=item_type,
                    ),
                )
            except ValidationError as e:
                _logger.warning("skipping item line name=%r chaos=%r: %s", line.name, chaos, e)
        return results

    def _prices_from_exchange(
        self, league: str, item_type: str, *, game: str = "poe1"
    ) -> list[PriceResult]:
        resp = self.get_exchange_overview(league, item_type, game=game)
        items_map = {item.id: item for item in resp.items}
        results = []
        for line in resp.lines:
            item = items_map.get(line.id)
            chaos = _exchange_chaos_value(line.primary_value, resp.core.rates, resp.core.primary)
            try:
                results.append(
                    PriceResult(
                        name=item.name if item else line.id,
                        chaos_value=chaos,
                        details_id=item.details_id if item else "",
                        icon=item.image if item else None,
                        sparkline=line.sparkline,
                        category=item.category if item else item_type,
                    ),
                )
            except ValidationError as e:
                _logger.warning("skipping exchange line id=%r chaos=%r: %s", line.id, chaos, e)
        return results

    def price_check(
        self,
        league: str,
        item_name: str,
        item_type: str,
        *,
        game: str = "poe1",
        language: str = "en",
    ) -> PriceResult | None:
        if item_name.lower() == "chaos orb" and item_type.lower() == "currency" and game == "poe1":
            return PriceResult(
                name="Chaos Orb",
                chaos_value=1.0,
                divine_value=0.0,
                details_id="chaos-orb",
                category="Currency",
            )
        prices = self.get_prices(league, item_type, game=game, language=language)
        name_lower = item_name.lower()
        return next(
            (p for p in prices if p.name.lower() == name_lower),
            None,
        )

    def price_list(
        self,
        league: str,
        item_type: str,
        *,
        game: str = "poe1",
        language: str = "en",
        variant: str | None = None,
        links: int | None = None,
        corrupted: bool | None = None,
        gem_level: int | None = None,
        gem_quality: int | None = None,
        map_tier: int | None = None,
    ) -> list[PriceResult]:
        prices = self.get_prices(league, item_type, game=game, language=language)

        if variant is not None:
            variant_lower = variant.lower()
            prices = [p for p in prices if p.variant and variant_lower in p.variant.lower()]
        if links is not None:
            prices = [p for p in prices if p.links == links]
        if corrupted is not None:
            prices = [p for p in prices if p.corrupted == corrupted]
        if gem_level is not None:
            prices = [p for p in prices if p.gem_level == gem_level]
        if gem_quality is not None:
            prices = [p for p in prices if p.gem_quality == gem_quality]
        if map_tier is not None:
            prices = [p for p in prices if p.map_tier == map_tier]

        return sorted(prices, key=lambda p: p.chaos_value, reverse=True)

    def currency_convert(
        self,
        league: str,
        amount: float,
        from_currency: str,
        to_currency: str,
        *,
        game: str = "poe1",
    ) -> float:
        if amount <= 0:
            raise NinjaError("Amount must be positive")
        prices = self.get_prices(league, "Currency", game=game)
        # Build the lookup with both canonical names and every alias that
        # resolves to a canonical name. This way a user passing "exalted",
        # "exalt", or "exalted orb" all hit the same price entry — without
        # the alias loop, only inputs whose alias-resolution exactly matches
        # a PriceResult.name would work.
        price_map: dict[str, float] = {}
        for p in prices:
            price_map[p.name.lower()] = p.chaos_value
        for alias, canonical in CURRENCY_ALIASES.items():
            chaos = price_map.get(canonical.lower())
            if chaos is not None:
                price_map.setdefault(alias.lower(), chaos)
        price_map["chaos orb"] = 1.0
        price_map["chaos"] = 1.0

        from_chaos = price_map.get(from_currency.lower())
        if from_chaos is None or from_chaos <= 0:
            raise NinjaError(f"Currency not found: {from_currency!r}")
        to_chaos = price_map.get(to_currency.lower())
        if to_chaos is None or to_chaos <= 0:
            raise NinjaError(f"Currency not found: {to_currency!r}")
        return amount * from_chaos / to_chaos

    def get_crafting_prices(self, league: str, *, language: str = "en") -> CraftingPrices:
        result: dict[str, dict[str, float]] = {}
        for category, type_routes in CRAFTING_TYPE_MAP.items():
            category_prices: dict[str, float] = {}
            for item_type, _route in type_routes:
                try:
                    prices = self.get_prices(league, item_type, game="poe1", language=language)
                except NinjaError as e:
                    _logger.warning(
                        "get_crafting_prices: category=%r type=%r failed: %s; "
                        "category will be partial or empty",
                        category,
                        item_type,
                        e,
                    )
                    continue
                for p in prices:
                    if p.chaos_value > 0:
                        category_prices[p.name] = p.chaos_value
            result[category] = category_prices
        return CraftingPrices.model_validate(result)

    def get_details_url(self, details_id: str, *, game: str = "poe1") -> str:
        return f"{NINJA_DETAILS_BASE}/{game}/economy/{details_id}"

    def get_trade_url(self, trade_id: str, league: str, *, game: str = "poe1") -> str:
        site = "www.pathofexile.com" if game == "poe1" else "www.pathofexile2.com"
        return f"https://{site}/trade/search/{league}?q={trade_id}"

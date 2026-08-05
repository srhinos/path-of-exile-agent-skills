from __future__ import annotations

from typing import TYPE_CHECKING, Any

from poe.models.ninja.builds import (
    DimensionEntry,
    IntegerRange,
    ResolvedDimension,
    SearchResults,
)
from poe.models.ninja.protobuf import Dictionary, NinjaSearchResult
from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.constants import HEATMAP_FLEX_THRESHOLD, HEATMAP_MANDATORY_THRESHOLD
from poe.services.ninja.errors import NinjaError

if TYPE_CHECKING:
    from poe.services.ninja.client import NinjaClient
    from poe.services.ninja.discovery import DiscoveryService
    from poe.services.ninja.economy import EconomyService


class AtlasService:
    """Atlas tree search, analysis, and passive heatmaps. PoE1 only."""

    def __init__(
        self,
        client: NinjaClient,
        discovery: DiscoveryService,
        base_dir: Any = None,
    ) -> None:
        self._client = client
        self._discovery = discovery
        self._cache_dir = base_dir or ninja_cache.cache_dir()

    def search(
        self,
        *,
        mechanics: str | None = None,
        beacons: str | None = None,
        travel: str | None = None,
        blockers: str | None = None,
        scarab_specializations: str | None = None,
        keystones: str | None = None,
    ) -> SearchResults | None:
        state = self._discovery.get_atlas_tree_index_state()
        if not state.snapshot_versions:
            return None

        version = state.snapshot_versions[0].version
        overview = state.snapshot_versions[0].snapshot_name

        path = f"/poe1/api/atlas-trees/{version}/search"
        params: dict[str, str] = {"overview": overview}
        if mechanics:
            params["mechanics"] = mechanics
        if beacons:
            params["beacons"] = beacons
        if travel:
            params["travel"] = travel
        if blockers:
            params["blockers"] = blockers
        if scarab_specializations:
            params["scarabspecializations"] = scarab_specializations
        if keystones:
            params["keystones"] = keystones

        raw = self._client.get_protobuf(path, params=params)
        result = NinjaSearchResult.from_protobuf(raw)
        if not result.result:
            return SearchResults(game="poe1")

        dictionaries = self._resolve_dictionaries(result)
        return _parse_atlas_results(result, dictionaries)

    def _resolve_dictionaries(self, result: NinjaSearchResult) -> dict[str, list[str]]:
        resolved: dict[str, list[str]] = {}
        if not result.result:
            return resolved

        for ref in result.result.dictionaries:
            cache_key = f"atlas_dict_{ref.hash}"
            cached_bytes = (
                ninja_cache.read_cache_bytes(self._cache_dir, cache_key, "dictionary")
                if ninja_cache.is_fresh(self._cache_dir, cache_key, "dictionary")
                else None
            )
            if cached_bytes:
                d = Dictionary.from_protobuf(cached_bytes)
            else:
                raw = self._client.get_protobuf(f"/poe1/api/atlas-trees/dictionary/{ref.hash}")
                ninja_cache.write_cache_bytes(self._cache_dir, cache_key, raw, "dictionary")
                d = Dictionary.from_protobuf(raw)
            resolved[ref.id] = d.values
        return resolved

    def get_popular_nodes(self, *, top_n: int = 20) -> list[DimensionEntry]:
        result = self.search()
        if not result or not result.dimensions:
            return []

        all_entries: list[DimensionEntry] = []
        for dim in result.dimensions:
            all_entries.extend(dim.entries)
        all_entries.sort(key=lambda e: e.count, reverse=True)
        return all_entries[:top_n]

    def estimate_profit(
        self,
        economy: EconomyService,
        league: str,
    ) -> list[dict[str, Any]]:
        result = self.search()
        if not result:
            return []

        scarab_dim = next(
            (d for d in result.dimensions if "scarab" in d.id.lower()),
            None,
        )
        if not scarab_dim:
            return []

        prices = economy.get_prices(league, "Scarab", game="poe1")
        price_map = {p.name.lower(): p.chaos_value for p in prices}
        if not price_map:
            msg = f"No scarab prices found for league {league!r}. Check the league name."
            raise NinjaError(msg)

        profits: list[dict[str, Any]] = []
        for entry in scarab_dim.entries:
            exact = price_map.get(entry.name.lower())
            if exact is not None:
                avg_price = exact
            else:
                prefix = entry.name.lower().removesuffix("s")
                matching = [v for k, v in price_map.items() if k.startswith(prefix)]
                avg_price = sum(matching) / len(matching) if matching else 0.0
            ev = entry.percentage / 100 * avg_price
            profits.append(
                {
                    "name": entry.name,
                    "spawn_chance_pct": entry.percentage,
                    "price_chaos": round(avg_price, 1),
                    "expected_value": round(ev, 2),
                }
            )
        profits.sort(key=lambda p: p["expected_value"], reverse=True)
        return profits

    def get_heatmap(
        self,
        builds_service: Any,
        *,
        class_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        result = builds_service.search(heatmap=True, class_filter=class_filter)
        if not result or not result.dimensions:
            return []

        node_dim = next(
            (d for d in result.dimensions if "passive" in d.id.lower() or "node" in d.id.lower()),
            None,
        )
        if not node_dim:
            return []

        return [
            {
                "name": e.name,
                "allocation_pct": e.percentage,
                "count": e.count,
                "zone": _classify_node(e.percentage),
            }
            for e in node_dim.entries
        ]


def _classify_node(pct: float) -> str:
    if pct >= HEATMAP_MANDATORY_THRESHOLD * 100:
        return "mandatory"
    if pct >= HEATMAP_FLEX_THRESHOLD * 100:
        return "flex"
    return "dead"


def _parse_atlas_results(
    result: NinjaSearchResult,
    dictionaries: dict[str, list[str]],
) -> SearchResults:
    sr = result.result
    if not sr:
        return SearchResults(game="poe1")

    dimensions = []
    for dim in sr.dimensions:
        vocab = dictionaries.get(dim.dictionary_id, [])
        entries = []
        for c in dim.counts:
            name = vocab[c.key] if c.key < len(vocab) else f"unknown-{c.key}"
            pct = (c.count / sr.total * 100) if sr.total > 0 else 0.0
            entries.append(DimensionEntry(name=name, count=c.count, percentage=round(pct, 2)))
        entries.sort(key=lambda e: e.count, reverse=True)
        dimensions.append(ResolvedDimension(id=dim.id, entries=entries))

    integer_ranges = [
        IntegerRange(id=d.id, min_value=d.min_value, max_value=d.max_value)
        for d in sr.integer_dimensions
    ]

    return SearchResults(
        total=sr.total,
        dimensions=dimensions,
        integer_ranges=integer_ranges,
        game="poe1",
    )

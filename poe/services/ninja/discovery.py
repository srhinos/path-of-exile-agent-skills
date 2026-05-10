from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from poe.constants import NINJA_LEAGUE_LIST_KEYS, PERCENTAGE_MAX
from poe.models.ninja.discovery import (
    AtlasTreeIndexState,
    BuildIndexState,
    LeagueInfo,
    Poe1IndexState,
    Poe1Snapshot,
    Poe2IndexState,
    Poe2Snapshot,
)
from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.constants import NINJA_ENDPOINTS

if TYPE_CHECKING:
    from poe.services.ninja.client import NinjaClient

_logger = logging.getLogger("poe.ninja.discovery")


def _camel_to_snake(name: str) -> str:
    result: list[str] = []
    for i, c in enumerate(name):
        if c.isupper() and i > 0:
            result.append("_")
        result.append(c.lower())
    return "".join(result)


def _convert_keys(data: Any) -> Any:
    if isinstance(data, dict):
        return {_camel_to_snake(k): _convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_keys(item) for item in data]
    return data


def _sanitize_leagues(data: Any) -> Any:
    """Drop league entries with empty name or url, logging warnings."""
    if not isinstance(data, dict):
        return data
    for key in NINJA_LEAGUE_LIST_KEYS:
        leagues = data.get(key)
        if not isinstance(leagues, list):
            continue
        kept: list[Any] = []
        for entry in leagues:
            if not isinstance(entry, dict):
                kept.append(entry)
                continue
            name = entry.get("name") or entry.get("league_name") or ""
            url = entry.get("url") or entry.get("league_url") or ""
            if not name or not url:
                _logger.warning(
                    "%s entry missing name/url, dropping: name=%r url=%r",
                    key,
                    name,
                    url,
                )
                continue
            kept.append(entry)
        data[key] = kept
    return data


def _sanitize_build_index(data: Any) -> Any:
    """Clamp percentage and drop empty-class BuildStat entries, logging warnings."""
    if not isinstance(data, dict):
        return data
    league_builds = data.get("league_builds")
    if not isinstance(league_builds, list):
        return data
    for lb in league_builds:
        if not isinstance(lb, dict):
            continue
        stats = lb.get("statistics")
        if not isinstance(stats, list):
            continue
        kept: list[Any] = []
        for stat in stats:
            if not isinstance(stat, dict):
                kept.append(stat)
                continue
            class_name = stat.get("class") or stat.get("class_name") or ""
            if not class_name:
                _logger.warning(
                    "build stat missing class, dropping: skill=%r",
                    stat.get("skill"),
                )
                continue
            pct = stat.get("percentage")
            if isinstance(pct, (int, float)) and not isinstance(pct, bool):
                # NaN slips both `< 0` and `> MAX` (NaN comparisons are always
                # False), so isfinite() must come first or NaN reaches the
                # strict model validator and crashes the whole response.
                if not math.isfinite(pct):
                    _logger.warning(
                        "build stat percentage=%r non-finite, defaulting to 0.0 (class=%r)",
                        pct,
                        class_name,
                    )
                    stat["percentage"] = 0.0
                elif pct < 0:
                    _logger.warning(
                        "build stat percentage=%r below 0, clamping (class=%r)",
                        pct,
                        class_name,
                    )
                    stat["percentage"] = 0.0
                elif pct > PERCENTAGE_MAX:
                    _logger.warning(
                        "build stat percentage=%r above %d, clamping (class=%r)",
                        pct,
                        PERCENTAGE_MAX,
                        class_name,
                    )
                    stat["percentage"] = float(PERCENTAGE_MAX)
            kept.append(stat)
        lb["statistics"] = kept
    return data


class DiscoveryService:
    """Fetches and caches poe.ninja index-state endpoints."""

    def __init__(
        self,
        client: NinjaClient,
        base_dir: Any = None,
    ) -> None:
        self._client = client
        self._cache_dir = base_dir or ninja_cache.cache_dir()

    def _fetch_cached_json(self, cache_key: str, path: str) -> Any:
        if not self._client.no_cache and ninja_cache.is_fresh(self._cache_dir, cache_key, "index"):
            cached = ninja_cache.read_cache(self._cache_dir, cache_key, "index")
            if cached is not None:
                return cached

        data = self._client.get_json(path)
        ninja_cache.write_cache(self._cache_dir, cache_key, data, "index")
        return data

    def get_poe1_index_state(self, *, force: bool = False) -> Poe1IndexState:
        cache_key = "poe1_index_state"
        if force:
            ninja_cache.invalidate_all(self._cache_dir)
        raw = self._fetch_cached_json(cache_key, NINJA_ENDPOINTS["poe1_index_state"])
        try:
            return Poe1IndexState.model_validate(_sanitize_leagues(_convert_keys(raw)))
        except ValidationError as e:
            _logger.warning("poe1 index-state schema mismatch: %s — returning empty", e)
            return Poe1IndexState()

    def get_poe2_index_state(self, *, force: bool = False) -> Poe2IndexState:
        cache_key = "poe2_index_state"
        if force:
            ninja_cache.invalidate_all(self._cache_dir)
        raw = self._fetch_cached_json(cache_key, NINJA_ENDPOINTS["poe2_index_state"])
        try:
            return Poe2IndexState.model_validate(_sanitize_leagues(_convert_keys(raw)))
        except ValidationError as e:
            _logger.warning("poe2 index-state schema mismatch: %s — returning empty", e)
            return Poe2IndexState()

    def get_build_index_state(self, *, game: str = "poe1") -> BuildIndexState:
        key = f"{game}_build_index_state"
        raw = self._fetch_cached_json(key, NINJA_ENDPOINTS[key])
        sanitized = _sanitize_build_index(_sanitize_leagues(_convert_keys(raw)))
        try:
            return BuildIndexState.model_validate(sanitized)
        except ValidationError as e:
            _logger.warning(
                "build index-state schema mismatch (game=%r): %s — returning empty", game, e
            )
            return BuildIndexState()

    def get_atlas_tree_index_state(self) -> AtlasTreeIndexState:
        cache_key = "poe1_atlas_tree_index_state"
        raw = self._fetch_cached_json(cache_key, NINJA_ENDPOINTS["poe1_atlas_tree_index_state"])
        try:
            return AtlasTreeIndexState.model_validate(_sanitize_leagues(_convert_keys(raw)))
        except ValidationError as e:
            _logger.warning("atlas-tree index-state schema mismatch: %s — returning empty", e)
            return AtlasTreeIndexState()

    def get_current_league(self, *, game: str = "poe1") -> LeagueInfo | None:
        state = self.get_poe2_index_state() if game == "poe2" else self.get_poe1_index_state()

        for league in state.economy_leagues:
            if league.name.lower() not in ("standard", "hardcore"):
                return league
        return state.economy_leagues[0] if state.economy_leagues else None

    def get_current_snapshot(
        self, *, game: str = "poe1", snapshot_type: str = "exp"
    ) -> Poe1Snapshot | Poe2Snapshot | None:
        if game == "poe2":
            state = self.get_poe2_index_state()
            return state.snapshot_versions[0] if state.snapshot_versions else None

        state = self.get_poe1_index_state()
        for snap in state.snapshot_versions:
            if snap.type == snapshot_type:
                return snap
        return state.snapshot_versions[0] if state.snapshot_versions else None

    def validate_league(self, league_name: str, *, game: str = "poe1") -> bool:
        state = self.get_poe2_index_state() if game == "poe2" else self.get_poe1_index_state()

        all_leagues = state.economy_leagues + state.old_economy_leagues
        return any(
            lg.name.lower() == league_name.lower() or lg.url.lower() == league_name.lower()
            for lg in all_leagues
        )

    def detect_game(self, league_name: str) -> str:
        poe1 = self.get_poe1_index_state()
        for lg in poe1.economy_leagues + poe1.old_economy_leagues:
            if lg.name.lower() == league_name.lower():
                return "poe1"

        poe2 = self.get_poe2_index_state()
        for lg in poe2.economy_leagues + poe2.old_economy_leagues:
            if lg.name.lower() == league_name.lower():
                return "poe2"

        return "poe1"

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from poe.models.ninja.builds import (
    CharacterResponse,
    DimensionEntry,
    IntegerRange,
    MetaSummary,
    ResolvedDimension,
    SearchCharacter,
    SearchResults,
    TooltipResponse,
)
from poe.models.ninja.protobuf import Dictionary, NinjaSearchResult
from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.errors import NinjaError
from poe.services.ninja.protobuf import ProtobufDecodeError
from poe.services.ninja.validators import normalize_game

if TYPE_CHECKING:
    from poe.services.ninja.client import NinjaClient
    from poe.services.ninja.discovery import DiscoveryService

_logger = logging.getLogger("poe.ninja.builds")


class BuildsService:
    """Fetches character details, meta data, and tooltips from poe.ninja."""

    def __init__(
        self,
        client: NinjaClient,
        discovery: DiscoveryService,
        base_dir: Any = None,
    ) -> None:
        self._client = client
        self._discovery = discovery
        self._cache_dir = base_dir or ninja_cache.cache_dir()

    def _fetch_cached(self, cache_key: str, path: str, params: dict[str, str]) -> Any:
        if not self._client.no_cache and ninja_cache.is_fresh(self._cache_dir, cache_key, "builds"):
            cached = ninja_cache.read_cache(self._cache_dir, cache_key, "builds")
            if cached is not None:
                return cached
        data = self._client.get_json(path, params=params)
        ninja_cache.write_cache(self._cache_dir, cache_key, data, "builds")
        return data

    def get_character(
        self,
        account: str,
        character: str,
        *,
        game: str = "poe1",
        snapshot_type: str = "exp",
    ) -> CharacterResponse | None:
        game = normalize_game(game)
        snap = self._discovery.get_current_snapshot(game=game, snapshot_type=snapshot_type)
        if not snap:
            return None

        prefix = "poe2" if game == "poe2" else "poe1"
        path = f"/{prefix}/api/builds/{snap.version}/character"
        params: dict[str, str] = {
            "account": account,
            "name": character,
            "overview": snap.snapshot_name,
        }
        if game == "poe1":
            params["type"] = snapshot_type

        cache_key = f"char_{game}_{account}_{character}"
        try:
            raw = self._fetch_cached(cache_key, path, params)
        except NinjaError:
            return None
        try:
            return CharacterResponse.model_validate(raw)
        except ValidationError as e:
            _logger.warning(
                "character schema mismatch (account=%r character=%r): %s",
                account,
                character,
                e,
            )
            return None

    def get_tooltip(
        self,
        slug: str,
        *,
        game: str = "poe1",
        tooltip_type: str = "exp",
        snapshot_type: str = "exp",
    ) -> TooltipResponse | None:
        game = normalize_game(game)
        snap = self._discovery.get_current_snapshot(game=game, snapshot_type=snapshot_type)
        if not snap:
            return None

        prefix = "poe2" if game == "poe2" else "poe1"
        path = f"/{prefix}/api/builds/{snap.version}/tooltip"
        params = {
            "overview": snap.snapshot_name,
            "tooltip": slug,
            "type": tooltip_type,
        }

        cache_key = f"tooltip_{game}_{slug}_{tooltip_type}"
        raw = self._fetch_cached(cache_key, path, params)
        try:
            return TooltipResponse.model_validate(raw)
        except ValidationError as e:
            _logger.warning("tooltip schema mismatch (slug=%r): %s", slug, e)
            return None

    def get_generic_tooltip(
        self,
        name: str,
        tooltip_type: str,
        tree_name: str = "PassiveTree-3.28",
    ) -> TooltipResponse | None:
        path = "/poe1/api/builds/tooltip/any"
        params = {"type": tooltip_type, "name": name, "treeName": tree_name}

        cache_key = f"tooltip_any_{tooltip_type}_{name}"
        try:
            raw = self._fetch_cached(cache_key, path, params)
        except NinjaError:
            return None
        try:
            return TooltipResponse.model_validate(raw)
        except ValidationError as e:
            _logger.warning("generic tooltip schema mismatch (name=%r): %s", name, e)
            return None

    def get_meta_summary(self, *, game: str = "poe1") -> MetaSummary:
        game = normalize_game(game)
        state = self._discovery.get_build_index_state(game=game)

        if not state.league_builds:
            return MetaSummary(game=game)

        current = state.league_builds[0]
        top_builds = [
            {
                "class": s.class_name,
                "skill": s.skill,
                "percentage": s.percentage,
                "trend": s.trend,
            }
            for s in current.statistics
        ]

        return MetaSummary(
            game=game,
            league=current.league_name,
            total_builds=current.total,
            top_builds=top_builds,
            rising=[b for b in top_builds if b["trend"] > 0],
            declining=[b for b in top_builds if b["trend"] < 0],
        )

    def search(
        self,
        *,
        game: str = "poe1",
        snapshot_type: str = "exp",
        time_machine: str | None = None,
        heatmap: bool = False,
        atlas_heatmap: bool = False,
        class_filter: str | None = None,
        skill: str | None = None,
        item: str | None = None,
        keystone: str | None = None,
        mastery: str | None = None,
        anointment: str | None = None,
        weapon_mode: str | None = None,
        bandit: str | None = None,
        pantheon: str | None = None,
        linked_gems: dict[str, str] | None = None,
    ) -> SearchResults | None:
        game = normalize_game(game)
        snap = self._discovery.get_current_snapshot(game=game, snapshot_type=snapshot_type)
        if not snap:
            return None

        prefix = "poe2" if game == "poe2" else "poe1"
        path = f"/{prefix}/api/builds/{snap.version}/search"
        params = _build_search_params(
            overview=snap.snapshot_name,
            game=game,
            snapshot_type=snapshot_type,
            time_machine=time_machine,
            heatmap=heatmap,
            atlas_heatmap=atlas_heatmap,
            class_filter=class_filter,
            skill=skill,
            item=item,
            keystone=keystone,
            mastery=mastery,
            anointment=anointment,
            weapon_mode=weapon_mode,
            bandit=bandit,
            pantheon=pantheon,
            linked_gems=linked_gems,
        )

        raw = self._client.get_protobuf(path, params=params)
        result = NinjaSearchResult.from_protobuf(raw)
        if not result.result:
            return SearchResults(game=game)

        dictionaries = self._resolve_dictionaries(result, game=game)
        return _parse_search_results(result, dictionaries, game=game)

    def _resolve_dictionaries(
        self, result: NinjaSearchResult, *, game: str = "poe1"
    ) -> dict[str, list[str]]:
        resolved: dict[str, list[str]] = {}
        if not result.result:
            return resolved

        prefix = "poe2" if game == "poe2" else "poe1"
        for ref in result.result.dictionaries:
            cache_key = f"dict_{ref.hash}"
            cached_bytes = (
                ninja_cache.read_cache_bytes(self._cache_dir, cache_key, "dictionary")
                if ninja_cache.is_fresh(self._cache_dir, cache_key, "dictionary")
                else None
            )
            d = self._decode_dictionary(prefix, ref.hash, cache_key, cached_bytes)
            resolved[ref.id] = d.values
        return resolved

    def _decode_dictionary(
        self,
        prefix: str,
        ref_hash: str,
        cache_key: str,
        cached_bytes: bytes | None,
    ) -> Dictionary:
        # A truncated/corrupted dictionary .bin (interrupted write, disk
        # corruption) raises ProtobufDecodeError. Without this catch the
        # exception bubbles past callers and every subsequent search call
        # for 30 days fails on the same stale cache file. On decode error,
        # delete the cache file and refetch.
        if cached_bytes:
            try:
                return Dictionary.from_protobuf(cached_bytes)
            except ProtobufDecodeError as e:
                _logger.warning(
                    "discarding corrupted dictionary cache %s: %s", cache_key, e
                )
                ninja_cache.invalidate_one(self._cache_dir, cache_key, "dictionary")
        raw = self._client.get_protobuf(f"/{prefix}/api/builds/dictionary/{ref_hash}")
        try:
            d = Dictionary.from_protobuf(raw)
        except ProtobufDecodeError as e:
            raise NinjaError(
                f"poe.ninja returned corrupt dictionary protobuf for {ref_hash}: {e}"
            ) from e
        ninja_cache.write_cache_bytes(self._cache_dir, cache_key, raw, "dictionary")
        return d


def _build_search_params(
    *,
    overview: str,
    game: str,
    snapshot_type: str,
    time_machine: str | None,
    heatmap: bool,
    atlas_heatmap: bool,
    class_filter: str | None,
    skill: str | None,
    item: str | None,
    keystone: str | None,
    mastery: str | None,
    anointment: str | None,
    weapon_mode: str | None,
    bandit: str | None,
    pantheon: str | None,
    linked_gems: dict[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"overview": overview}

    if game == "poe1":
        params["type"] = snapshot_type

    params.update(
        {
            k: v
            for k, v in {
                "timemachine": time_machine,
                "class": class_filter,
                "skills": skill,
                "items": item,
                "keypassives": keystone,
            }.items()
            if v
        }
    )

    if heatmap:
        params["heatmap"] = "true"
    if atlas_heatmap and game == "poe1":
        params["atlasheatmap"] = "true"

    if game == "poe1":
        params.update(
            {
                k: v
                for k, v in {
                    "masteries": mastery,
                    "anointed": anointment,
                    "weaponmode": weapon_mode,
                    "bandit": bandit,
                    "pantheon": pantheon,
                }.items()
                if v
            }
        )

    if game == "poe2" and linked_gems:
        for skill_name, gem_name in linked_gems.items():
            params[f"linkedgems-{skill_name}"] = gem_name

    return params


def _parse_search_results(
    result: NinjaSearchResult,
    dictionaries: dict[str, list[str]],
    *,
    game: str = "poe1",
) -> SearchResults:
    sr = result.result
    if not sr:
        return SearchResults(game=game)

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

    vl_map = {vl.id: vl.values for vl in sr.value_lists}
    characters = _extract_characters(vl_map, dictionaries)

    return SearchResults(
        total=sr.total,
        characters=characters,
        dimensions=dimensions,
        integer_ranges=integer_ranges,
        game=game,
    )


def _resolve_ids(ids: list[int], vocab: list[str]) -> list[str]:
    return [vocab[idx] if idx < len(vocab) else f"unknown-{idx}" for idx in ids]


def _extract_characters(
    vl_map: dict[str, list],
    dictionaries: dict[str, list[str]],
) -> list[SearchCharacter]:
    names = vl_map.get("name", [])
    accounts = vl_map.get("account", [])
    levels = vl_map.get("level", [])
    lives = vl_map.get("life", [])
    es_vals = vl_map.get("energyshield", [])
    dps_vals = vl_map.get("dps", [])
    ehp_vals = vl_map.get("ehp", [])
    class_vals = vl_map.get("class", [])
    skill_vals = vl_map.get("skills", [])
    keystone_vals = vl_map.get("keypassives", [])

    gem_vocab = dictionaries.get("gem", [])
    keystone_vocab = dictionaries.get("keypassive", [])

    count = len(names)
    parallel = {
        "account": accounts,
        "level": levels,
        "life": lives,
        "energyshield": es_vals,
        "dps": dps_vals,
        "ehp": ehp_vals,
        "class": class_vals,
        "skills": skill_vals,
        "keypassives": keystone_vals,
    }
    truncated = sorted(k for k, v in parallel.items() if len(v) < count)
    if truncated:
        _logger.warning(
            "poe.ninja search response: parallel value-lists shorter than 'name' (%d): %s; "
            "characters with missing fields will be dropped",
            count,
            truncated,
        )

    characters = []
    for i in range(count):
        name = names[i].str_val if i < len(names) else ""
        account = accounts[i].str_val if i < len(accounts) else ""
        if not name or not account:
            continue
        # Skip rows where any expected parallel list ran short — partial data
        # would mix real and synthesized-zero values and be silently wrong.
        if any(i >= len(v) for v in parallel.values()):
            continue
        raw_skills = skill_vals[i].numbers
        raw_keystones = keystone_vals[i].numbers
        characters.append(
            SearchCharacter(
                name=name,
                account=account,
                level=levels[i].number,
                life=lives[i].number,
                energy_shield=es_vals[i].number,
                dps=dps_vals[i].str_val,
                ehp=ehp_vals[i].str_val,
                class_id=class_vals[i].number,
                skills=_resolve_ids(raw_skills, gem_vocab),
                keystones=_resolve_ids(raw_keystones, keystone_vocab),
            )
        )
    return characters

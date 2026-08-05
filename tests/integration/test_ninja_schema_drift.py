from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from poe.exceptions import PoeError

if TYPE_CHECKING:
    from pydantic import BaseModel
from poe.models.ninja.builds import (
    CharacterResponse,
    DefensiveStats,
    SearchResults,
)
from poe.models.ninja.discovery import (
    AtlasTreeIndexState,
    BuildIndexState,
    Poe1IndexState,
    Poe2IndexState,
)
from poe.models.ninja.economy import (
    CurrencyOverviewResponse,
    ExchangeOverviewResponse,
    ItemOverviewResponse,
)
from poe.services.ninja.builds import BuildsService
from poe.services.ninja.client import NinjaClient, RateLimiter
from poe.services.ninja.constants import NINJA_ENDPOINTS
from poe.services.ninja.discovery import DiscoveryService
from poe.services.ninja.economy import EconomyService
from poe.services.ninja.history import HistoryService

pytestmark = pytest.mark.integration

RATE_LIMITER = RateLimiter(max_requests=5, window=10.0)


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _convert_keys(data: Any) -> Any:
    if isinstance(data, dict):
        return {_camel_to_snake(k): _convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_keys(item) for item in data]
    return data


def _get_model_accepted_keys(model_cls: type[BaseModel]) -> set[str]:
    keys: set[str] = set()
    for name, field in model_cls.model_fields.items():
        keys.add(name)
        if field.alias:
            keys.add(field.alias)
    return keys


def _check_no_unmodeled_fields(
    raw: dict,
    model_cls: type[BaseModel],
    context: str = "",
    *,
    convert_camel: bool = False,
):
    check_keys = set(_convert_keys(raw).keys()) if convert_camel else set(raw.keys())
    accepted = _get_model_accepted_keys(model_cls)
    unmodeled = check_keys - accepted
    assert not unmodeled, (
        f"API returned fields not in {model_cls.__name__} model"
        f"{f' ({context})' if context else ''}: "
        f"{sorted(unmodeled)}. Add these to the model."
    )


@pytest.fixture(scope="module")
def ninja_client():
    try:
        client = NinjaClient(rate_limiter=RATE_LIMITER)
        svc = DiscoveryService(client)
        svc.get_poe1_index_state()
    except (OSError, PoeError):
        pytest.skip("poe.ninja unreachable")
    else:
        yield client
        client.close()


@pytest.fixture(scope="module")
def discovery(ninja_client):
    return DiscoveryService(ninja_client)


@pytest.fixture(scope="module")
def economy(ninja_client):
    return EconomyService(ninja_client)


@pytest.fixture(scope="module")
def current_league(discovery):
    league = discovery.get_current_league()
    if not league:
        pytest.skip("No current league")
    return league.name


@pytest.fixture(scope="module")
def first_character(ninja_client, discovery):
    snap = discovery.get_current_snapshot(game="poe1", snapshot_type="exp")
    if not snap:
        pytest.skip("No snapshot")

    from poe.models.ninja.protobuf import NinjaSearchResult

    raw_pb = ninja_client.get_protobuf(
        f"/poe1/api/builds/{snap.version}/search",
        params={"overview": snap.snapshot_name, "type": "exp"},
    )
    result = NinjaSearchResult.from_protobuf(raw_pb)
    vl_map = {vl.id: vl.values for vl in result.result.value_lists}
    return vl_map["account"][0].str_val, vl_map["name"][0].str_val, snap


class TestDiscoverySchema:
    def test_poe1_index_state_no_dropped_fields(self, ninja_client):
        raw = ninja_client.get_json("/poe1/api/data/index-state")
        _check_no_unmodeled_fields(raw, Poe1IndexState, "poe1 index-state", convert_camel=True)

    def test_poe2_index_state_no_dropped_fields(self, ninja_client):
        raw = ninja_client.get_json("/poe2/api/data/index-state")
        _check_no_unmodeled_fields(raw, Poe2IndexState, "poe2 index-state", convert_camel=True)

    def test_build_index_state_no_dropped_fields(self, ninja_client):
        raw = ninja_client.get_json("/poe1/api/data/build-index-state")
        _check_no_unmodeled_fields(raw, BuildIndexState, "build index-state", convert_camel=True)

    def test_atlas_index_state_no_dropped_fields(self, ninja_client):
        raw = ninja_client.get_json("/poe1/api/data/atlas-tree-index-state")
        _check_no_unmodeled_fields(
            raw, AtlasTreeIndexState, "atlas index-state", convert_camel=True
        )


class TestCharacterSchema:
    def test_character_response_no_dropped_fields(self, ninja_client, first_character):
        account, name, snap = first_character
        raw = ninja_client.get_json(
            f"/poe1/api/builds/{snap.version}/character",
            params={
                "account": account,
                "name": name,
                "overview": snap.snapshot_name,
                "type": "exp",
            },
        )
        _check_no_unmodeled_fields(raw, CharacterResponse, "character response")

    def test_defensive_stats_no_dropped_fields(self, ninja_client, first_character):
        account, name, snap = first_character
        raw = ninja_client.get_json(
            f"/poe1/api/builds/{snap.version}/character",
            params={
                "account": account,
                "name": name,
                "overview": snap.snapshot_name,
                "type": "exp",
            },
        )
        ds_raw = raw.get("defensiveStats", {})
        _check_no_unmodeled_fields(ds_raw, DefensiveStats, "defensiveStats")

    def test_character_items_have_item_data(self, ninja_client, discovery, first_character):
        account, name, _ = first_character
        svc = BuildsService(ninja_client, discovery)
        char = svc.get_character(account, name, game="poe1", snapshot_type="exp")
        assert char is not None

        if char.items:
            assert char.items[0].item_data, "item_data should be populated"
            assert "name" in char.items[0].item_data or "typeLine" in char.items[0].item_data

        if char.flasks:
            assert char.flasks[0].item_data, "flask item_data should be populated"

        if char.jewels:
            assert char.jewels[0].item_data, "jewel item_data should be populated"

    def test_character_skills_have_dps(self, ninja_client, discovery, first_character):
        account, name, _ = first_character
        svc = BuildsService(ninja_client, discovery)
        char = svc.get_character(account, name, game="poe1", snapshot_type="exp")
        assert char is not None
        assert len(char.skills) > 0

        skills_with_dps = [s for s in char.skills if s.dps]
        assert len(skills_with_dps) > 0, "At least one skill should have DPS data"


class TestSearchSchema:
    def test_search_returns_characters(self, ninja_client, discovery):
        svc = BuildsService(ninja_client, discovery)
        results = svc.search(game="poe1", snapshot_type="exp")
        assert results is not None
        assert isinstance(results, SearchResults)
        assert results.total > 0
        assert len(results.characters) > 0, "Search should return character listings"

    def test_search_characters_have_data(self, ninja_client, discovery):
        svc = BuildsService(ninja_client, discovery)
        results = svc.search(game="poe1", snapshot_type="exp")
        assert results is not None

        char = results.characters[0]
        assert char.name != ""
        assert char.account != ""
        assert char.level > 0

    def test_search_value_lists_populated(self, ninja_client, discovery):
        snap = discovery.get_current_snapshot(game="poe1", snapshot_type="exp")
        if not snap:
            pytest.skip("No snapshot")

        from poe.models.ninja.protobuf import NinjaSearchResult

        raw = ninja_client.get_protobuf(
            f"/poe1/api/builds/{snap.version}/search",
            params={"overview": snap.snapshot_name, "type": "exp"},
        )
        result = NinjaSearchResult.from_protobuf(raw)
        sr = result.result
        assert sr is not None

        vl_ids = {vl.id for vl in sr.value_lists}
        assert "name" in vl_ids, "Search should return character names"
        assert "account" in vl_ids, "Search should return account names"
        assert "level" in vl_ids, "Search should return levels"

        name_vl = next(vl for vl in sr.value_lists if vl.id == "name")
        assert len(name_vl.values) > 0, "Name value list should have entries"


class TestEconomySchema:
    def test_currency_overview_no_dropped_fields(self, ninja_client, current_league):
        raw = ninja_client.get_json(
            NINJA_ENDPOINTS["poe1_currency_overview"],
            params={"league": current_league, "type": "Currency", "language": "en"},
        )
        _check_no_unmodeled_fields(raw, CurrencyOverviewResponse, "currency overview")

    def test_item_overview_no_dropped_fields(self, ninja_client, current_league):
        raw = ninja_client.get_json(
            NINJA_ENDPOINTS["poe1_item_overview"],
            params={"league": current_league, "type": "UniqueArmour", "language": "en"},
        )
        _check_no_unmodeled_fields(raw, ItemOverviewResponse, "item overview")

    def test_exchange_overview_no_dropped_fields(self, ninja_client, current_league):
        raw = ninja_client.get_json(
            NINJA_ENDPOINTS["poe1_exchange_overview"],
            params={"league": current_league, "type": "DivinationCard", "language": "en"},
        )
        _check_no_unmodeled_fields(raw, ExchangeOverviewResponse, "exchange overview")


class TestHistorySchema:
    def test_currency_history_returns_data(self, ninja_client, economy, current_league):
        svc = HistoryService(ninja_client, economy)
        result = svc.get_price_history(current_league, "Divine Orb", "Currency")
        assert result is not None
        assert len(result.data_points) > 0
        for pt in result.data_points:
            assert pt.value >= 0
            assert pt.days_ago >= 0

    def test_item_history_returns_data(self, ninja_client, economy, current_league):
        svc = HistoryService(ninja_client, economy)
        result = svc.get_price_history(current_league, "Headhunter", "UniqueAccessory")
        assert result is not None
        assert len(result.data_points) > 0

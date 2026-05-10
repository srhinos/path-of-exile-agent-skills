from __future__ import annotations

import cyclopts

from poe.output import render
from poe.services.ninja.atlas import AtlasService
from poe.services.ninja.client import NinjaClient
from poe.services.ninja.discovery import DiscoveryService
from poe.services.ninja.economy import EconomyService
from poe.services.ninja.errors import NinjaError

atlas_app = cyclopts.App(name="atlas", help="Atlas tree search and analysis. PoE1 only.")


def _resolve_league(discovery: DiscoveryService, league: str | None) -> str:
    if league:
        cleaned = league.strip()
        if not cleaned:
            raise NinjaError("--league is empty after stripping whitespace")
        return cleaned
    current = discovery.get_current_league()
    if not current:
        # NinjaError is a PoeError subclass — surfaces as clean JSON error.
        raise NinjaError("No current league found")
    return current.name


@atlas_app.command(name="search")
def atlas_search(
    mechanics: str | None = None,
    beacons: str | None = None,
    keystones: str | None = None,
    travel: str | None = None,
    blockers: str | None = None,
    scarab_specializations: str | None = None,
    *,
    no_cache: bool = False,
    json: bool = False,
) -> None:
    """Search atlas tree nodes with filters.

    Parameters
    ----------
    mechanics
        Mechanic filter.
    beacons
        Beacon filter.
    keystones
        Keystone filter.
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    with NinjaClient(no_cache=no_cache) as client:
        discovery = DiscoveryService(client)
        svc = AtlasService(client, discovery)
        result = svc.search(
            mechanics=mechanics,
            beacons=beacons,
            keystones=keystones,
            travel=travel,
            blockers=blockers,
            scarab_specializations=scarab_specializations,
        )
        if result is None:
            render({"error": "No atlas data"}, json_mode=json)
            return
        render(result, json_mode=json)


@atlas_app.command(name="recommend")
def atlas_recommend(*, top_n: int = 20, no_cache: bool = False, json: bool = False) -> None:
    """Get popular atlas nodes.

    Parameters
    ----------
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    with NinjaClient(no_cache=no_cache) as client:
        discovery = DiscoveryService(client)
        svc = AtlasService(client, discovery)
        nodes = svc.get_popular_nodes(top_n=top_n)
        render(nodes, json_mode=json)


@atlas_app.command(name="profit")
def atlas_profit(league: str | None = None, *, no_cache: bool = False, json: bool = False) -> None:
    """Estimate atlas profit by mechanic.

    Parameters
    ----------
    league
        League name.
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    with NinjaClient(no_cache=no_cache) as client:
        discovery = DiscoveryService(client)
        resolved_league = _resolve_league(discovery, league)
        economy = EconomyService(client)
        svc = AtlasService(client, discovery)
        profits = svc.estimate_profit(economy, resolved_league)
        render(profits, json_mode=json)

from __future__ import annotations

import cyclopts

from poe.output import render
from poe.services.ninja.builds import BuildsService
from poe.services.ninja.client import NinjaClient
from poe.services.ninja.discovery import DiscoveryService

meta_app = cyclopts.App(name="meta", help="Meta overview and trends.")


@meta_app.command(name="summary")
def meta_summary(game: str = "poe1", *, no_cache: bool = False, json: bool = False) -> None:
    """Get meta build summary from poe.ninja.

    Parameters
    ----------
    game
        poe1 or poe2.
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    with NinjaClient(no_cache=no_cache) as client:
        discovery = DiscoveryService(client)
        svc = BuildsService(client, discovery)
        result = svc.get_meta_summary(game=game)
        render(result, json_mode=json)


@meta_app.command(name="trend")
def meta_trend(game: str = "poe1", *, no_cache: bool = False, json: bool = False) -> None:
    """Get build popularity trends across leagues.

    Parameters
    ----------
    game
        poe1 or poe2.
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    with NinjaClient(no_cache=no_cache) as client:
        discovery = DiscoveryService(client)
        state = discovery.get_build_index_state(game=game)

        trends = [
            {
                "league": lb.league_name,
                "total": lb.total,
                "status": lb.status,
                "top": [
                    {
                        "class": s.class_name,
                        "skill": s.skill,
                        "percentage": s.percentage,
                        "trend": s.trend,
                    }
                    for s in lb.statistics
                ],
            }
            for lb in state.league_builds
        ]
        render(trends, json_mode=json)

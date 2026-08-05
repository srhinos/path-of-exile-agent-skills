from __future__ import annotations

from typing import Annotated

import cyclopts

from poe.commands.ninja.atlas import atlas_app
from poe.commands.ninja.builds import builds_app
from poe.commands.ninja.meta import meta_app
from poe.commands.ninja.price import price_app
from poe.exceptions import PoeError
from poe.models.ninja.discovery import CacheStatusEntry, CacheStatusReport
from poe.output import render
from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.builds import BuildsService
from poe.services.ninja.client import NinjaClient
from poe.services.ninja.discovery import DiscoveryService
from poe.services.ninja.validators import normalize_game

ninja_app = cyclopts.App(name="ninja", help="poe.ninja economy, builds, and meta data.")

ninja_app.command(price_app)
ninja_app.command(builds_app)
ninja_app.command(atlas_app)
ninja_app.command(meta_app)


@ninja_app.command(name="league-info")
def league_info(
    game: str = "poe1", *, force: bool = False, no_cache: bool = False, json: bool = False
) -> None:
    """Show league index state from poe.ninja.

    Parameters
    ----------
    game
        Game version: poe1 or poe2.
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    game = normalize_game(game)
    with NinjaClient(no_cache=no_cache) as client:
        svc = DiscoveryService(client)
        state = (
            svc.get_poe2_index_state(force=force)
            if game == "poe2"
            else svc.get_poe1_index_state(force=force)
        )
        render(state, json_mode=json)


@ninja_app.command(name="cache-clear")
def cache_clear(*, json: bool = False) -> None:
    """Clear all cached poe.ninja data.

    Parameters
    ----------
    json
        Output raw JSON.
    """
    base = ninja_cache.cache_dir()
    ninja_cache.invalidate_all(base)
    render({"status": "ok", "cleared": str(base)}, json_mode=json)


@ninja_app.command(name="cache-status")
def cache_status(*, json: bool = False) -> None:
    """Show ninja data cache status.

    Parameters
    ----------
    json
        Output raw JSON.
    """
    base = ninja_cache.cache_dir()
    known_keys = [
        ("poe1_index_state", "index"),
        ("poe2_index_state", "index"),
        ("poe1_build_index_state", "index"),
        ("poe2_build_index_state", "index"),
        ("poe1_atlas_tree_index_state", "index"),
    ]

    entries: list[CacheStatusEntry] = []
    for key, category in known_keys:
        cf = ninja_cache.cache_file(base, key, category)
        freshness = ninja_cache.get_freshness(base, key, category)
        entries.append(
            CacheStatusEntry(
                name=key,
                is_cached=cf.exists(),
                is_fresh=not freshness["is_stale"],
                age_seconds=freshness["cache_age_seconds"],
                fetched_at=freshness["fetched_at"],
            ),
        )

    report = CacheStatusReport(cache_dir=str(base), entries=entries)
    render(report, json_mode=json)


@ninja_app.command(name="tooltip")
def tooltip(
    name: str,
    tooltip_type: Annotated[str, cyclopts.Parameter(name="--type")] = "anointed",
    *,
    no_cache: bool = False,
    json: bool = False,
) -> None:
    """Look up a tooltip by name and type.

    Parameters
    ----------
    name
        Item or passive name.
    tooltip_type
        Type: anointed, bandit, pantheon, etc.
    no_cache
        Bypass cache and fetch fresh data.
    json
        Output raw JSON.
    """
    with NinjaClient(no_cache=no_cache) as client:
        discovery = DiscoveryService(client)
        svc = BuildsService(client, discovery)
        result = svc.get_generic_tooltip(name, tooltip_type)
        if result is None:
            raise PoeError(f"No tooltip for '{name}'")
        render(result, json_mode=json)

from __future__ import annotations

import cyclopts

from poe.output import render as _output
from poe.services.build.engine_service import EngineService

engine_app = cyclopts.App(name="engine", help="PoB engine operations (requires lupa).")


def _svc() -> EngineService:
    return EngineService()


@engine_app.command(name="load")
def engine_load(name: str, *, json: bool = False) -> None:
    """Load a build into the PoB engine and print calculated stats.

    Parameters
    ----------
    name
        Build name or unique prefix.
    json
        Output raw JSON.
    """
    _output(_svc().load(name), json_mode=json)


@engine_app.command(name="stats")
def engine_stats(name: str | None = None, *, category: str = "all", json: bool = False) -> None:
    """Get calculated stats from loaded build.

    Parameters
    ----------
    name
        Build name. If provided, loads the build first.
    category
        Stat category.
    json
        Output raw JSON.
    """
    _output(_svc().stats(name=name, category=category), json_mode=json)


@engine_app.command(name="info")
def engine_info(*, json: bool = False) -> None:
    """Get PoB installation and engine compatibility info.

    Parameters
    ----------
    json
        Output raw JSON.
    """
    _output(_svc().info(), json_mode=json)

from __future__ import annotations

from poe.models.build.engine import EngineStats
from poe.services.build.engine.runtime import lua_table_to_dict


def extract_stats(lua_table, *, build_name: str = "") -> EngineStats:
    """Convert a Lua stats table to an EngineStats pydantic model.

    bool is a subclass of int in Python; without the not-bool guard, Lua's
    `output.HasFlask = true` silently becomes a stats[...]=1.0 numeric entry.
    """
    raw = lua_table_to_dict(lua_table)
    stats = {
        k: float(v)
        for k, v in raw.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    return EngineStats(stats=stats, build_name=build_name)

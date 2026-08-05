from __future__ import annotations

from poe.exceptions import (
    BuildNotFoundError,
    BuildValidationError,
    EngineNotAvailableError,
    PoeError,
)
from poe.services.build.constants import ENGINE_DEF_TERMS, ENGINE_OFF_TERMS
from poe.services.build.engine.runtime import LuaError, get_engine, get_pob_info


class EngineService:
    """Owns PoB engine business logic."""

    def info(self) -> dict:
        return get_pob_info()

    def load(self, name: str) -> dict:
        try:
            eng = get_engine()
            build_info = eng.load_build(name)
            if "error" in build_info:
                raise EngineNotAvailableError(build_info["error"])
            stats = eng.get_stats()
        except (BuildNotFoundError, BuildValidationError):
            raise
        # lupa.LuaError inherits from Exception (NOT RuntimeError) — the
        # original catch tuple let raw Lua tracebacks past app.run()'s
        # PoeError envelope. Include LuaError explicitly.
        except (LuaError, RuntimeError, ImportError, FileNotFoundError, OSError) as e:
            raise EngineNotAvailableError(str(e)) from e
        else:
            return {"build_info": build_info, "stats": stats}

    def stats(self, *, name: str | None = None, category: str = "all") -> dict:
        try:
            eng = get_engine()
            if name:
                eng.load_build(name)
            elif not eng.build_loaded:
                raise EngineNotAvailableError(
                    "No build loaded. Run 'poe build engine stats <name>' or "
                    "'poe build engine load <name>' first."
                )
            all_stats = eng.get_stats()
            if category == "all" or not isinstance(all_stats, dict):
                return all_stats
            cat = category.casefold()
            if cat in ("off", "offence", "offense"):
                return {k: v for k, v in all_stats.items() if any(t in k for t in ENGINE_OFF_TERMS)}
            if cat in ("def", "defence", "defense"):
                return {k: v for k, v in all_stats.items() if any(t in k for t in ENGINE_DEF_TERMS)}
            return {k: v for k, v in all_stats.items() if cat in k.casefold()}
        except PoeError:
            raise
        except (LuaError, RuntimeError, ImportError, FileNotFoundError, OSError) as e:
            raise EngineNotAvailableError(str(e)) from e

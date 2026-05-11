from __future__ import annotations

import contextlib
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import ParseError as XMLParseError

from defusedxml import ElementTree as SafeET

from poe.exceptions import EngineNotAvailableError
from poe.paths import get_pob_path, resolve_build_file
from poe.services.build.constants import LUA_TABLE_MAX_DEPTH, LUA_TABLE_MAX_KEYS
from poe.services.build.engine.stubs import register_stubs

_logger = logging.getLogger("poe.engine")

# os.chdir is process-global, not thread-local. Concurrent PoBEngine
# methods running on the same process (pytest-xdist, a future MCP server,
# any async caller) would see each other's cwd. Serialize all chdir
# regions through a module-level lock so the contract becomes
# "PoBEngine is not safe to use re-entrantly but is safe across threads".
_chdir_lock = threading.Lock()


@contextlib.contextmanager
def _pob_cwd(pob_path: str):
    """Context manager: chdir into PoB folder under the chdir lock."""
    with _chdir_lock:
        orig_cwd = Path.cwd()
        try:
            os.chdir(pob_path)
            yield
        finally:
            os.chdir(orig_cwd)


if TYPE_CHECKING:
    from lupa import LuaRuntime

# lupa.LuaError is the type raised by lua.eval / lua.execute on Lua-side
# errors (syntax, runtime, type confusion). It inherits directly from
# Exception, NOT RuntimeError — so `except RuntimeError` clauses silently
# pass it through as a raw Python traceback. Import the concrete class so
# service-layer catches can translate it to EngineNotAvailableError.
try:
    from lupa import LuaError
except ImportError:

    class LuaError(Exception):  # type: ignore[no-redef]
        """Fallback when lupa is not installed."""


try:
    import lupa.luajit21 as _lua_mod
except ImportError:
    try:
        import lupa.luajit20 as _lua_mod
    except ImportError:
        _lua_mod = None


def _get_lua_module():
    """Return the lupa LuaJIT module, or raise if unavailable."""
    if _lua_mod is None:
        raise ImportError(
            "pob requires LuaJIT, which is bundled with lupa on most platforms. "
            "Install lupa >= 2.0 (`uv add lupa`). "
            "If LuaJIT is still missing, your platform may not support it."
        )
    return _lua_mod


class PoBEngine:
    """Manages an embedded PoB Lua runtime via lupa + LuaJIT."""

    def __init__(self, pob_path: str | Path | None = None):
        self.pob_path = str(pob_path or get_pob_path())
        self.lua: LuaRuntime | None = None
        self._initialized = False
        self._build_loaded = False
        self._last_build_name: str = ""

    def _require_lua(self) -> LuaRuntime:
        if self.lua is None:
            raise EngineNotAvailableError("Engine not initialized — call init() first")
        return self.lua

    def init(self) -> None:
        lua_mod = _get_lua_module()
        self.lua = lua_mod.LuaRuntime(unpack_returned_tuples=True)

        register_stubs(self.lua, self.pob_path)

        pob_path_lua = self.pob_path.replace("\\", "/")
        self.lua.globals()["_pobPathStr"] = pob_path_lua
        self.lua.execute("""
            local pobPath = _pobPathStr
            package.path = pobPath .. "/?.lua;" ..
                           pobPath .. "/?/init.lua;" ..
                           pobPath .. "/lua/?.lua;" ..
                           pobPath .. "/lua/?/init.lua;" ..
                           pobPath .. "/Modules/?.lua;" ..
                           pobPath .. "/Classes/?.lua;" ..
                           package.path
        """)

        with _pob_cwd(self.pob_path):
            launch_path = Path(self.pob_path) / "Launch.lua"
            launch_code = launch_path.read_text(encoding="utf-8")

            # Strip the #@ SimpleGraphic directive that requires a GUI
            lines = launch_code.split("\n")
            if lines and lines[0].startswith("#@"):
                lines[0] = "-- " + lines[0]
            launch_code = "\n".join(lines)

            self.lua.execute(launch_code)
            self.lua.execute("runCallback('OnInit')")
            self.lua.execute("runCallback('OnFrame')")

            # Poll mainObject.promptMsg after init callbacks. Without this,
            # any error PoB stored during data-file load (missing data,
            # bad mod table) would not surface until the next operation,
            # making _initialized=True a lie about engine readiness.
            err = self._check_init_error_locked()
            if err:
                raise EngineNotAvailableError(f"PoB init failed: {err}")
            self._initialized = True

    def _check_init_error_locked(self) -> str | None:
        """Read promptMsg with the caller already inside `_pob_cwd`."""
        try:
            msg = self._require_lua().eval("mainObject and mainObject.promptMsg or nil")
        except (LuaError, AttributeError):
            return None
        else:
            return str(msg) if msg else None

    def _check_init_error(self) -> str | None:
        # lupa.LuaRuntime is not thread-safe; serialize all Lua interaction
        # under the same chdir lock the other methods use, otherwise this
        # eval can race with concurrent execute/eval from another thread
        # (pytest-xdist, future MCP server).
        with _pob_cwd(self.pob_path):
            return self._check_init_error_locked()

    def load_build(self, build_name: str) -> dict:
        if not self._initialized:
            self.init()

        err = self._check_init_error()
        if err:
            return {"error": f"PoB init failed: {err}"}

        build_path = resolve_build_file(build_name)
        self._last_build_name = build_name
        xml_content = build_path.read_text(encoding="utf-8")

        with _pob_cwd(self.pob_path):
            lua = self._require_lua()
            lua.globals()["_loadBuildName"] = build_path.stem
            lua.globals()["_loadBuildXml"] = xml_content

            lua.execute("""
                local main = mainObject.main
                if main then
                    main:SetMode("BUILD", false, _loadBuildName, _loadBuildXml)
                    for i = 1, 10 do
                        runCallback('OnFrame')
                    end
                end
            """)

            self._build_loaded = True
        return self.get_build_info()

    def get_build_info(self) -> dict:
        if not self._initialized:
            return {"error": "Engine not initialized"}

        # PoB sets mainObject.promptMsg whenever it hits a runtime error
        # (missing data file, mod parse failure). Without this check, get_*
        # ran on a corrupted Lua state and returned silently empty / wrong
        # numbers — silent corruption.
        err = self._check_init_error()
        if err:
            return {"error": f"PoB runtime error: {err}"}

        with _pob_cwd(self.pob_path):
            info = self._require_lua().eval("""
                (function()
                    local main = mainObject and mainObject.main
                    local build = main and main.modes and main.modes["BUILD"]
                    if not build then
                        return {error = "No build loaded"}
                    end
                    return {
                        className = build.spec and build.spec.curClassName or "Unknown",
                        ascendClassName = build.spec and build.spec.curAscendClassName or "None",
                        level = build.characterLevel or 1,
                        buildName = build.buildName or "",
                    }
                end)()
            """)
        result = lua_table_to_dict(info)
        if result.get("className") in ("Scion", "Unknown", "") and self._last_build_name:
            result = self._fallback_class_from_xml(result)
        return result

    def _fallback_class_from_xml(self, result: dict) -> dict:
        try:
            build_path = resolve_build_file(self._last_build_name)
            tree = SafeET.parse(str(build_path))
            build_el = tree.find("Build")
            if build_el is not None:
                result["className"] = build_el.get("className", result.get("className", ""))
                result["ascendClassName"] = build_el.get(
                    "ascendClassName", result.get("ascendClassName", "")
                )
        except (FileNotFoundError, XMLParseError, OSError):
            pass
        return result

    def get_stats(self, fields: list[str] | None = None) -> dict:
        if not self._initialized:
            return {"error": "Engine not initialized"}

        err = self._check_init_error()
        if err:
            return {"error": f"PoB runtime error: {err}"}

        with _pob_cwd(self.pob_path):
            result = self._require_lua().eval("""
                (function()
                    local main = mainObject and mainObject.main
                    local build = main and main.modes and main.modes["BUILD"]
                    if not build or not build.calcsTab then
                        return {error = "No build loaded or calculated"}
                    end
                    local output = build.calcsTab.mainOutput
                    if not output then
                        return {error = "No calculation output available"}
                    end
                    local stats = {}
                    for k, v in pairs(output) do
                        -- Exclude booleans: bool is subclass of int in Python,
                        -- so `output.HasFlask = true` would silently become a
                        -- numeric 1.0 stat downstream. Stats are numeric/textual.
                        if type(v) == "number" or type(v) == "string" then
                            stats[k] = v
                        end
                    end
                    return stats
                end)()
            """)
        stats = lua_table_to_dict(result)

        if fields:
            stats = {k: v for k, v in stats.items() if k in fields}

        return stats

    def recalculate(self) -> None:
        if not self._initialized:
            return

        err = self._check_init_error()
        if err:
            # Don't silently recalculate against a broken state.
            _logger.warning("recalculate skipped: PoB runtime error: %s", err)
            return

        with _pob_cwd(self.pob_path):
            self._require_lua().execute("""
                local main = mainObject and mainObject.main
                local build = main and main.modes and main.modes["BUILD"]
                if build then
                    build.buildFlag = true
                    runCallback('OnFrame')
                end
            """)

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def build_loaded(self) -> bool:
        return self._build_loaded


def lua_table_to_dict(lua_table) -> dict:
    """Convert a lupa Lua table to a Python dict.

    Bounded by LUA_TABLE_MAX_DEPTH and LUA_TABLE_MAX_KEYS. Self-referential
    tables are detected via id() and short-circuited with a "_cycle" marker.
    On iteration failure, returns {"_raw": str(...)} as a degraded fallback
    so a broken bridge doesn't masquerade as empty stats.
    """
    if lua_table is None:
        return {}
    return _lua_table_to_dict_impl(lua_table, depth=0, seen=set())


def _lua_table_to_dict_impl(lua_table, *, depth: int, seen: set[int]) -> dict:
    if depth >= LUA_TABLE_MAX_DEPTH:
        _logger.warning("lua_table_to_dict truncated at depth %d", LUA_TABLE_MAX_DEPTH)
        return {"_truncated_depth": True}

    table_id = id(lua_table)
    if table_id in seen:
        _logger.warning("lua_table_to_dict detected cycle at depth %d", depth)
        return {"_cycle": True}
    seen.add(table_id)
    try:
        try:
            result: dict = {}
            for k, v in lua_table.items():
                if len(result) >= LUA_TABLE_MAX_KEYS:
                    _logger.warning(
                        "lua_table_to_dict truncated at %d keys (depth %d)",
                        LUA_TABLE_MAX_KEYS,
                        depth,
                    )
                    result["_truncated_keys"] = True
                    break
                key = str(k)
                if hasattr(v, "items"):
                    result[key] = _lua_table_to_dict_impl(v, depth=depth + 1, seen=seen)
                elif hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
                    result[key] = list(v)
                else:
                    result[key] = v
        except (AttributeError, TypeError) as e:
            _logger.warning(
                "lua_table_to_dict failed to iterate %r: %s", type(lua_table).__name__, e
            )
            return {"_raw": str(lua_table)}
        else:
            return result
    finally:
        seen.discard(table_id)


def check_lua_version() -> dict:
    """Check the Lua version available via lupa."""
    try:
        lua_mod = _get_lua_module()
        lua = lua_mod.LuaRuntime()
        lua_ver = lua.eval("_VERSION")
        has_jit = lua.eval("jit ~= nil")
        jit_ver = None
        if has_jit:
            jit_ver = lua.eval("jit.version")
    except ImportError:
        return {"error": "lupa not installed"}
    else:
        return {
            "lua_version": lua_ver,
            "has_luajit": has_jit,
            "luajit_version": jit_ver,
            "module": lua_mod.__name__,
        }


def get_pob_info() -> dict:
    """Get info about the PoB installation."""
    try:
        pob_path = get_pob_path()
    except FileNotFoundError as e:
        return {"error": str(e)}

    launch = Path(pob_path) / "Launch.lua"
    manifest = Path(pob_path) / "manifest.xml"

    version = "unknown"
    if manifest.exists():
        try:
            tree = SafeET.parse(str(manifest))
            root = tree.getroot()
        except (XMLParseError, OSError):
            root = None
        if root is not None:
            for child in root:
                if child.tag == "Version":
                    version = child.get("number", "unknown")

    return {
        "pob_path": str(pob_path),
        "launch_exists": launch.exists(),
        "version": version,
        "lua": check_lua_version(),
    }


def get_engine() -> PoBEngine:
    """Create a new engine instance."""
    return PoBEngine()

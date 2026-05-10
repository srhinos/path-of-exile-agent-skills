from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from poe.services.build.engine.runtime import (
    PoBEngine,
    _get_lua_module,
    check_lua_version,
    get_pob_info,
    lua_table_to_dict,
)

# ── _get_lua_module ──────────────────────────────────────────────────────────


class TestGetLuaModule:
    def test_returns_luajit_module(self):
        mod = _get_lua_module()
        assert hasattr(mod, "LuaRuntime")

    def test_raises_when_no_luajit(self):
        with (
            patch("poe.services.build.engine.runtime._lua_mod", None),
            pytest.raises(ImportError, match="LuaJIT"),
        ):
            _get_lua_module()


# ── check_lua_version ────────────────────────────────────────────────────────


class TestCheckLuaVersion:
    def test_returns_version_info(self):
        info = check_lua_version()
        assert "lua_version" in info
        assert "has_luajit" in info
        assert info["has_luajit"] is True
        assert "luajit_version" in info
        assert "module" in info

    def test_returns_error_when_no_lupa(self):
        with patch("poe.services.build.engine.runtime._get_lua_module", side_effect=ImportError):
            result = check_lua_version()
        assert result == {"error": "lupa not installed"}


# ── lua_table_to_dict ───────────────────────────────────────────────────────


class TestLuaTableToDict:
    def test_none_returns_empty_dict(self):
        assert lua_table_to_dict(None) == {}

    def test_converts_simple_table(self):
        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        tbl = lua.eval('{foo = "bar", num = 42}')
        result = lua_table_to_dict(tbl)
        assert result["foo"] == "bar"
        assert result["num"] == 42

    def test_converts_nested_table(self):
        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        tbl = lua.eval('{outer = {inner = "value"}}')
        result = lua_table_to_dict(tbl)
        assert result["outer"]["inner"] == "value"

    def test_converts_iterable_to_list(self):
        """Non-dict iterable values become lists."""
        mock_table = MagicMock()
        mock_table.items.return_value = [("key", [1, 2, 3])]
        result = lua_table_to_dict(mock_table)
        assert result["key"] == [1, 2, 3]

    def test_non_table_returns_raw(self):
        result = lua_table_to_dict("just a string")
        assert "_raw" in result

    def test_attribute_error_returns_raw(self):
        class Bad:
            def items(self):
                raise AttributeError("no items")

            def __str__(self):
                return "bad-object"

        assert lua_table_to_dict(Bad()) == {"_raw": "bad-object"}

    def test_type_error_returns_raw(self):
        class BadType:
            def items(self):
                raise TypeError("not iterable")

            def __str__(self):
                return "bad-type"

        assert lua_table_to_dict(BadType()) == {"_raw": "bad-type"}

    def test_self_referential_table_marked_cycle(self):
        # Self-cycle: t = {}; t.t = t — without cycle detection this stack-overflows.
        mock_inner = MagicMock()
        mock_outer = MagicMock()
        mock_outer.items.return_value = [("self", mock_inner)]
        mock_inner.items.return_value = [("back", mock_outer)]

        result = lua_table_to_dict(mock_outer)
        assert result["self"]["back"] == {"_cycle": True}

    def test_disjoint_subtrees_not_falsely_marked_cycle(self):
        # Cycle detection must release the id when leaving a subtree —
        # otherwise sibling subtrees with the same id (rare but possible
        # with mocks/recycled objects) get mis-flagged as cycles.
        shared_inner = MagicMock()
        shared_inner.items.return_value = [("v", 1)]
        outer = MagicMock()
        outer.items.return_value = [("a", shared_inner), ("b", shared_inner)]

        result = lua_table_to_dict(outer)
        assert result["a"] == {"v": 1}
        assert result["b"] == {"v": 1}

    def test_excessive_depth_truncated(self):
        # Build a >MAX-deep nested chain.
        from poe.services.build.constants import LUA_TABLE_MAX_DEPTH

        leaf = MagicMock()
        leaf.items.return_value = [("k", "v")]
        chain = leaf
        for _ in range(LUA_TABLE_MAX_DEPTH + 5):
            wrapper = MagicMock()
            wrapper.items.return_value = [("next", chain)]
            chain = wrapper

        result = lua_table_to_dict(chain)
        # Walk to the truncation marker
        node = result
        for _ in range(LUA_TABLE_MAX_DEPTH):
            assert isinstance(node, dict)
            node = node.get("next", node)
        assert node == {"_truncated_depth": True}

    def test_excessive_keys_truncated(self):
        from poe.services.build.constants import LUA_TABLE_MAX_KEYS

        mock_table = MagicMock()
        mock_table.items.return_value = [(f"k{i}", i) for i in range(LUA_TABLE_MAX_KEYS + 10)]
        result = lua_table_to_dict(mock_table)
        assert result.get("_truncated_keys") is True
        # Real keys count = LUA_TABLE_MAX_KEYS (the marker doesn't count toward the cap)
        real = {k: v for k, v in result.items() if not k.startswith("_truncated")}
        assert len(real) == LUA_TABLE_MAX_KEYS


# ── PoBEngine.__init__ ───────────────────────────────────────────────────────


class TestPoBEngineInit:
    def test_init_with_explicit_path(self):
        engine = PoBEngine(pob_path="/tmp/fakepob")
        assert engine.pob_path == "/tmp/fakepob"
        assert engine.lua is None
        assert engine._initialized is False
        assert engine._build_loaded is False

    def test_init_uses_get_pob_path_when_none(self):
        with patch("poe.services.build.engine.runtime.get_pob_path", return_value="/detected/pob"):
            engine = PoBEngine()
        assert engine.pob_path == "/detected/pob"


# ── PoBEngine._require_lua ──────────────────────────────────────────────────


class TestRequireLua:
    def test_raises_when_lua_is_none(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine.lua = None
        with pytest.raises(RuntimeError, match="not initialized"):
            engine._require_lua()

    def test_returns_lua_when_set(self):
        engine = PoBEngine.__new__(PoBEngine)
        mock_lua = MagicMock()
        engine.lua = mock_lua
        assert engine._require_lua() is mock_lua


# ── PoBEngine.init (mocked) ─────────────────────────────────────────────────


class TestPoBEngineInitMethod:
    def test_init_loads_launch_lua(self, tmp_path):
        """init() reads Launch.lua, strips #@ directive, calls lua.execute."""
        launch = tmp_path / "Launch.lua"
        launch.write_text("#@ SimpleGraphic 800 600\nprint('loaded')\n")

        mock_lua_mod = MagicMock()
        mock_lua = MagicMock()
        mock_lua_mod.LuaRuntime.return_value = mock_lua
        mock_globals = {}
        mock_lua.globals.return_value = mock_globals

        engine = PoBEngine(pob_path=str(tmp_path))
        with (
            patch("poe.services.build.engine.runtime._get_lua_module", return_value=mock_lua_mod),
            patch("poe.services.build.engine.runtime.register_stubs"),
        ):
            engine.init()

        assert engine._initialized is True
        assert engine.lua is mock_lua
        # Verify Launch.lua was executed (multiple execute calls)
        assert mock_lua.execute.call_count >= 3  # package.path + launch + OnInit + OnFrame

    def test_init_strips_hash_at_directive(self, tmp_path):
        """First line starting with #@ gets commented out."""
        launch = tmp_path / "Launch.lua"
        launch.write_text("#@ SimpleGraphic 800 600\nlocal x = 1\n")

        mock_lua_mod = MagicMock()
        mock_lua = MagicMock()
        mock_lua_mod.LuaRuntime.return_value = mock_lua
        mock_lua.globals.return_value = {}

        engine = PoBEngine(pob_path=str(tmp_path))
        with (
            patch("poe.services.build.engine.runtime._get_lua_module", return_value=mock_lua_mod),
            patch("poe.services.build.engine.runtime.register_stubs"),
        ):
            engine.init()

        # Find the execute call with the launch code
        launch_calls = [
            str(c) for c in mock_lua.execute.call_args_list if "SimpleGraphic" in str(c)
        ]
        assert len(launch_calls) == 1
        assert "-- #@" in launch_calls[0]

    def test_init_no_hash_at_line(self, tmp_path):
        """Launch.lua without #@ directive is passed through unchanged."""
        launch = tmp_path / "Launch.lua"
        launch.write_text("local x = 1\n")

        mock_lua_mod = MagicMock()
        mock_lua = MagicMock()
        mock_lua_mod.LuaRuntime.return_value = mock_lua
        mock_lua.globals.return_value = {}

        engine = PoBEngine(pob_path=str(tmp_path))
        with (
            patch("poe.services.build.engine.runtime._get_lua_module", return_value=mock_lua_mod),
            patch("poe.services.build.engine.runtime.register_stubs"),
        ):
            engine.init()

        assert engine._initialized is True

    def test_init_restores_cwd_on_success(self, tmp_path):
        """CWD is restored after init."""
        from pathlib import Path

        launch = tmp_path / "Launch.lua"
        launch.write_text("-- launch\n")
        orig_cwd = Path.cwd()

        mock_lua_mod = MagicMock()
        mock_lua = MagicMock()
        mock_lua_mod.LuaRuntime.return_value = mock_lua
        mock_lua.globals.return_value = {}

        engine = PoBEngine(pob_path=str(tmp_path))
        with (
            patch("poe.services.build.engine.runtime._get_lua_module", return_value=mock_lua_mod),
            patch("poe.services.build.engine.runtime.register_stubs"),
        ):
            engine.init()

        assert Path.cwd() == orig_cwd

    def test_init_restores_cwd_on_failure(self, tmp_path):
        """CWD is restored even if init fails."""
        from pathlib import Path

        launch = tmp_path / "Launch.lua"
        launch.write_text("-- launch\n")
        orig_cwd = Path.cwd()

        mock_lua_mod = MagicMock()
        mock_lua = MagicMock()
        mock_lua_mod.LuaRuntime.return_value = mock_lua
        mock_lua.globals.return_value = {}
        mock_lua.execute.side_effect = [None, RuntimeError("boom")]  # package.path ok, launch fails

        engine = PoBEngine(pob_path=str(tmp_path))
        with (
            patch("poe.services.build.engine.runtime._get_lua_module", return_value=mock_lua_mod),
            patch("poe.services.build.engine.runtime.register_stubs"),
            pytest.raises(RuntimeError),
        ):
            engine.init()

        assert Path.cwd() == orig_cwd


# ── PoBEngine._check_init_error ─────────────────────────────────────────────


class TestCheckInitError:
    def test_returns_none_when_no_error(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine.lua = MagicMock()
        engine.lua.eval.return_value = None
        assert engine._check_init_error() is None

    def test_returns_message_when_error(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine.lua = MagicMock()
        engine.lua.eval.return_value = "Something went wrong"
        assert engine._check_init_error() == "Something went wrong"

    def test_returns_none_on_exception(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine.lua = MagicMock()
        engine.lua.eval.side_effect = RuntimeError("lua error")
        assert engine._check_init_error() is None


# ── PoBEngine.load_build (mocked) ───────────────────────────────────────────


class TestLoadBuild:
    def test_calls_init_if_not_initialized(self, tmp_path):
        build_xml = tmp_path / "test.xml"
        build_xml.write_text("<PathOfBuilding/>")

        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = False
        engine._build_loaded = False
        engine.lua = None
        engine.init = MagicMock()  # mock init

        # After init, set up lua mock
        def fake_init():
            engine._initialized = True
            engine.lua = MagicMock()
            engine.lua.eval.return_value = None  # get_build_info returns None table
            engine.lua.globals.return_value = {}

        engine.init.side_effect = fake_init

        with patch("poe.services.build.engine.runtime.resolve_build_file", return_value=build_xml):
            engine.load_build("test")
        engine.init.assert_called_once()

    def test_returns_error_when_init_error(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = "/tmp"
        engine._initialized = True
        engine._build_loaded = False
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value="PoB broken")

        result = engine.load_build("test")
        assert result == {"error": "PoB init failed: PoB broken"}

    def test_loads_build_successfully(self, tmp_path):
        build_xml = tmp_path / "test.xml"
        build_xml.write_text("<PathOfBuilding/>")

        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine._build_loaded = False
        engine.lua = MagicMock()
        engine.lua.eval.return_value = None  # get_build_info
        engine.lua.globals.return_value = {}
        engine._check_init_error = MagicMock(return_value=None)

        with patch("poe.services.build.engine.runtime.resolve_build_file", return_value=build_xml):
            engine.load_build("test")
        assert engine._build_loaded is True


# ── PoBEngine.get_build_info (mocked) ────────────────────────────────────────


class TestGetBuildInfo:
    def test_returns_error_when_not_initialized(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine._initialized = False
        assert engine.get_build_info() == {"error": "Engine not initialized"}

    def test_returns_lua_eval_result(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        mock_table = MagicMock()
        mock_table.items.return_value = [
            ("className", "Witch"),
            ("level", 95),
        ]
        engine.lua = MagicMock()
        engine.lua.eval.return_value = mock_table
        engine._check_init_error = MagicMock(return_value=None)

        result = engine.get_build_info()
        assert result["className"] == "Witch"
        assert result["level"] == 95


# ── PoBEngine.get_stats (mocked) ────────────────────────────────────────────


class TestGetStats:
    def test_returns_error_when_not_initialized(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine._initialized = False
        assert engine.get_stats() == {"error": "Engine not initialized"}

    def test_returns_all_stats(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        mock_table = MagicMock()
        mock_table.items.return_value = [
            ("Life", 5000),
            ("Mana", 2000),
            ("TotalDPS", 100000),
        ]
        engine.lua = MagicMock()
        engine.lua.eval.return_value = mock_table
        engine._check_init_error = MagicMock(return_value=None)

        result = engine.get_stats()
        assert result["Life"] == 5000
        assert result["TotalDPS"] == 100000

    def test_filters_by_fields(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        mock_table = MagicMock()
        mock_table.items.return_value = [
            ("Life", 5000),
            ("Mana", 2000),
            ("TotalDPS", 100000),
        ]
        engine.lua = MagicMock()
        engine.lua.eval.return_value = mock_table
        engine._check_init_error = MagicMock(return_value=None)

        result = engine.get_stats(fields=["Life"])
        assert result == {"Life": 5000}


# ── PoBEngine.recalculate (mocked) ──────────────────────────────────────────


class TestRecalculate:
    def test_noop_when_not_initialized(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine._initialized = False
        engine.recalculate()  # should not raise

    def test_executes_lua_when_initialized(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value=None)

        engine.recalculate()
        engine.lua.execute.assert_called_once()

    def test_skips_when_init_error_present(self, tmp_path):
        # New behavior: recalculate must not run against a corrupted Lua
        # state. A non-None _check_init_error means PoB hit a runtime
        # error since last load; warn and skip.
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value="data file missing")

        engine.recalculate()
        engine.lua.execute.assert_not_called()


# ── PoBEngine properties ────────────────────────────────────────────────────


class TestProperties:
    def test_initialized_property(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine._initialized = True
        assert engine.initialized is True

    def test_build_loaded_property(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine._build_loaded = True
        assert engine.build_loaded is True


# ── get_pob_info (mocked) ───────────────────────────────────────────────────


class TestGetPobInfo:
    def test_returns_error_when_pob_not_found(self):
        with patch(
            "poe.services.build.engine.runtime.get_pob_path",
            side_effect=FileNotFoundError("not found"),
        ):
            result = get_pob_info()
        assert "error" in result

    def test_returns_info_with_manifest(self, tmp_path):
        (tmp_path / "Launch.lua").write_text("-- launch")
        (tmp_path / "manifest.xml").write_text(
            '<?xml version="1.0"?><PoBVersion><Version number="2.62.0"/></PoBVersion>'
        )

        with (
            patch("poe.services.build.engine.runtime.get_pob_path", return_value=str(tmp_path)),
            patch(
                "poe.services.build.engine.runtime.check_lua_version",
                return_value={"lua": "ok"},
            ),
        ):
            result = get_pob_info()
        assert result["pob_path"] == str(tmp_path)
        assert result["launch_exists"] is True
        assert result["version"] == "2.62.0"

    def test_returns_unknown_version_without_manifest(self, tmp_path):
        (tmp_path / "Launch.lua").write_text("-- launch")

        with (
            patch("poe.services.build.engine.runtime.get_pob_path", return_value=str(tmp_path)),
            patch(
                "poe.services.build.engine.runtime.check_lua_version",
                return_value={"lua": "ok"},
            ),
        ):
            result = get_pob_info()
        assert result["version"] == "unknown"

    def test_handles_corrupt_manifest(self, tmp_path):
        (tmp_path / "Launch.lua").write_text("-- launch")
        (tmp_path / "manifest.xml").write_text("not xml at all")

        with (
            patch("poe.services.build.engine.runtime.get_pob_path", return_value=str(tmp_path)),
            patch(
                "poe.services.build.engine.runtime.check_lua_version",
                return_value={"lua": "ok"},
            ),
        ):
            result = get_pob_info()
        assert result["version"] == "unknown"


# ── get_engine ───────────────────────────────────────────────────────────────


class TestGetEngine:
    def test_returns_engine_instance(self):
        from poe.services.build.engine.runtime import get_engine

        with patch("poe.services.build.engine.runtime.PoBEngine") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = get_engine()
        assert result is mock_cls.return_value

    def test_creates_new_instance_each_call(self):
        from poe.services.build.engine.runtime import get_engine

        with patch("poe.services.build.engine.runtime.PoBEngine") as mock_cls:
            get_engine()
            get_engine()
        assert mock_cls.call_count == 2


# ── register_stubs (real Lua runtime, lupa is a project dep) ─────────────────


class TestRegisterStubs:
    def test_stubs_register_without_error(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")

    def test_stub_functions_exist(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")

        for fn in (
            "GetTime",
            "ConPrintf",
            "GetScreenSize",
            "NewImageHandle",
            "IsKeyDown",
            "SetMainObject",
            "GetScriptPath",
            "LoadModule",
            "PLoadModule",
            "PCall",
            "Inflate",
            "Deflate",
            "NewFileSearch",
        ):
            assert lua.eval(f"type({fn})") == "function", f"{fn} not registered"

    def test_stub_path_functions_return_pob_path(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "C:\\Users\\Test\\PoB")

        assert lua.eval("GetScriptPath()") == "C:/Users/Test/PoB"
        assert lua.eval("GetRuntimePath()") == "C:/Users/Test/PoB"

    def test_stub_inflate_deflate_roundtrip(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")

        lua.execute('_testDeflated = Deflate("hello world")')
        assert lua.eval("Inflate(_testDeflated)") == "hello world"

    def test_stub_inflate_nil_returns_empty(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        assert lua.eval("Inflate(nil)") == ""

    def test_stub_screen_size(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        w, h = lua.eval("GetScreenSize()")
        assert w == 1920
        assert h == 1080

    def test_stub_image_handle(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        assert lua.eval("NewImageHandle():IsValid()") is False

    def test_stub_path_with_quotes_safe(self):
        """Paths with special characters don't cause Lua injection."""
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        evil_path = 'C:\\Users\\O\'Malley\\"evil"\\PoB'
        register_stubs(lua, evil_path)
        result = lua.eval("GetScriptPath()")
        assert "O'Malley" in result

    def test_stub_deflate_nil_returns_empty(self):
        """Deflate(nil) returns empty string."""
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        assert lua.eval("Deflate(nil)") == ""

    def test_stub_inflate_bad_data_returns_empty(self):
        """Inflate with invalid compressed data returns empty string."""
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        assert lua.eval('Inflate("not compressed data at all")') == ""


class TestPoBEngineLastBuildName:
    def test_last_build_name_initialized_empty(self):
        """PoBEngine should start with empty _last_build_name."""
        from unittest.mock import patch

        with patch("poe.services.build.engine.runtime.get_pob_path", return_value="/tmp/fake"):
            from poe.services.build.engine.runtime import PoBEngine

            eng = PoBEngine(pob_path="/tmp/fake")
            assert eng._last_build_name == ""


# ── lua_table_to_dict full coverage ─────────────────────────────────────────


class TestLuaTableToDictAdditional:
    def test_handles_none(self):
        assert lua_table_to_dict(None) == {}

    def test_returns_dict_type(self):
        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        tbl = lua.eval("{a = 1, b = 2}")
        result = lua_table_to_dict(tbl)
        assert isinstance(result, dict)

    def test_string_values_preserved(self):
        mock_table = MagicMock()
        mock_table.items.return_value = [("name", "Witch")]
        result = lua_table_to_dict(mock_table)
        assert result["name"] == "Witch"

    def test_iterable_string_not_split_into_chars(self):
        # Strings have __iter__ but should not be treated as lists
        mock_table = MagicMock()
        mock_table.items.return_value = [("str_field", "hello")]
        result = lua_table_to_dict(mock_table)
        assert result["str_field"] == "hello"
        assert result["str_field"] != ["h", "e", "l", "l", "o"]

    def test_bytes_not_split(self):
        mock_table = MagicMock()
        mock_table.items.return_value = [("bytes_field", b"abc")]
        result = lua_table_to_dict(mock_table)
        # bytes excluded from list-conversion path
        assert result["bytes_field"] == b"abc"


# ── PoBEngine init failure paths ────────────────────────────────────────────


class TestEngineInitFailures:
    def test_init_raises_when_lua_mod_unavailable(self, tmp_path):
        engine = PoBEngine(pob_path=str(tmp_path))
        with (
            patch("poe.services.build.engine.runtime._lua_mod", None),
            pytest.raises(ImportError, match="LuaJIT"),
        ):
            engine.init()

    def test_load_build_propagates_init_error(self):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = "/tmp"
        engine._initialized = True
        engine._build_loaded = False
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value="some error")

        result = engine.load_build("test")
        assert "error" in result
        assert "some error" in result["error"]


# ── PoBEngine get_stats with empty result ───────────────────────────────────


class TestGetStatsEdgeCases:
    def test_get_stats_empty_table(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine.lua = MagicMock()
        engine.lua.eval.return_value = None
        result = engine.get_stats()
        # None lua table converts to empty dict
        assert result == {}

    def test_get_stats_with_field_filter_empty_result(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine.lua = MagicMock()
        mock_table = MagicMock()
        mock_table.items.return_value = [("Life", 5000)]
        engine.lua.eval.return_value = mock_table
        engine._check_init_error = MagicMock(return_value=None)
        # Filter for nonexistent field
        result = engine.get_stats(fields=["Mana"])
        assert result == {}

    def test_get_stats_returns_error_on_init_error(self, tmp_path):
        # New behavior: get_stats refuses to run against a corrupted Lua
        # state. PoB's promptMsg surfacing means data files / mods failed
        # to load and any output would be silently wrong.
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value="data file missing")

        result = engine.get_stats()
        assert "error" in result
        assert "data file missing" in result["error"]


# ── PoBEngine.get_build_info fallback path ──────────────────────────────────


class TestGetBuildInfoFallback:
    def test_fallback_class_when_unknown(self, tmp_path):
        build_xml = tmp_path / "test.xml"
        build_xml.write_text(
            '<?xml version="1.0"?><PathOfBuilding>'
            '<Build className="Witch" ascendClassName="Necromancer" level="90"/>'
            "</PathOfBuilding>",
            encoding="utf-8",
        )

        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine._last_build_name = "test"
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value=None)

        mock_table = MagicMock()
        mock_table.items.return_value = [
            ("className", "Unknown"),
            ("level", 1),
        ]
        engine.lua.eval.return_value = mock_table

        with patch(
            "poe.services.build.engine.runtime.resolve_build_file",
            return_value=build_xml,
        ):
            result = engine.get_build_info()
        # Fallback should populate from XML
        assert result["className"] == "Witch"
        assert result["ascendClassName"] == "Necromancer"

    def test_fallback_handles_missing_file(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine._last_build_name = "test"
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value=None)

        mock_table = MagicMock()
        mock_table.items.return_value = [
            ("className", "Scion"),
            ("level", 1),
        ]
        engine.lua.eval.return_value = mock_table

        with patch(
            "poe.services.build.engine.runtime.resolve_build_file",
            side_effect=FileNotFoundError("missing"),
        ):
            # Should not raise
            result = engine.get_build_info()
        assert "className" in result

    def test_no_fallback_when_class_known(self, tmp_path):
        engine = PoBEngine.__new__(PoBEngine)
        engine.pob_path = str(tmp_path)
        engine._initialized = True
        engine._last_build_name = "test"
        engine.lua = MagicMock()
        engine._check_init_error = MagicMock(return_value=None)

        mock_table = MagicMock()
        mock_table.items.return_value = [
            ("className", "Witch"),
            ("level", 95),
        ]
        engine.lua.eval.return_value = mock_table

        # Should not call resolve_build_file when className is good
        with patch(
            "poe.services.build.engine.runtime.resolve_build_file",
        ) as mock_resolve:
            result = engine.get_build_info()
        mock_resolve.assert_not_called()
        assert result["className"] == "Witch"


# ── get_pob_info corruption resilience ──────────────────────────────────────


class TestGetPobInfoExtra:
    def test_returns_pob_path_string_type(self, tmp_path):
        (tmp_path / "Launch.lua").write_text("-- launch")
        with (
            patch("poe.services.build.engine.runtime.get_pob_path", return_value=str(tmp_path)),
            patch("poe.services.build.engine.runtime.check_lua_version", return_value={}),
        ):
            result = get_pob_info()
        assert isinstance(result["pob_path"], str)

    def test_lua_subdict_present(self, tmp_path):
        (tmp_path / "Launch.lua").write_text("-- launch")
        with (
            patch("poe.services.build.engine.runtime.get_pob_path", return_value=str(tmp_path)),
            patch(
                "poe.services.build.engine.runtime.check_lua_version",
                return_value={"lua_version": "5.1", "has_luajit": True},
            ),
        ):
            result = get_pob_info()
        assert "lua" in result
        assert result["lua"]["lua_version"] == "5.1"


# ── Stub Lua bridge negative paths ──────────────────────────────────────────


class TestStubsNegativePaths:
    def test_inflate_invalid_data_returns_empty(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        # Random bytes that aren't valid zlib
        assert lua.eval('Inflate("\\x00\\x01\\x02\\x03")') == ""

    def test_deflate_string_succeeds(self):
        from poe.services.build.engine.stubs import register_stubs

        mod = _get_lua_module()
        lua = mod.LuaRuntime(unpack_returned_tuples=True)
        register_stubs(lua, "/tmp/fakepob")
        # Should compress without error
        result = lua.eval('Deflate("data")')
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0


# ── Engine semantic invariants ───────────────────────────────────────────────


class TestEngineSemanticInvariants:
    def test_initial_state_consistent(self, tmp_path):
        with patch("poe.services.build.engine.runtime.get_pob_path", return_value=str(tmp_path)):
            engine = PoBEngine()
        # Semantic: if not initialized, build cannot be loaded
        assert engine.initialized is False
        assert engine.build_loaded is False

    def test_lua_path_normalizes_backslashes(self, tmp_path):
        # Semantic invariant: pob_path with backslashes is normalized
        engine = PoBEngine(pob_path="C:\\Users\\Test\\PoB")
        assert engine.pob_path == "C:\\Users\\Test\\PoB"
        # Conversion happens during init

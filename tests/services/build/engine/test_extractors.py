from __future__ import annotations

from poe.services.build.engine.extractors import extract_stats
from poe.services.build.engine.runtime import (
    PoBEngine,
    check_lua_version,
    get_engine,
    get_pob_info,
    lua_table_to_dict,
)
from poe.services.build.engine.stubs import register_stubs


class TestBridge:
    def test_lua_table_to_dict_none(self):
        assert lua_table_to_dict(None) == {}

    def test_lua_table_to_dict_with_dict(self):
        mock_table = {"key": "value", "num": 42}
        result = lua_table_to_dict(mock_table)
        assert result["key"] == "value"
        assert result["num"] == 42


class TestExtractors:
    def test_extract_stats_from_dict(self):
        mock_table = {"Life": 5000, "Mana": 1000, "name": "ignored"}
        result = extract_stats(mock_table, build_name="test")
        assert result.build_name == "test"
        assert result.stats["Life"] == 5000.0
        assert result.stats["Mana"] == 1000.0
        assert "name" not in result.stats

    def test_extract_stats_empty(self):
        result = extract_stats(None)
        assert result.stats == {}
        assert result.build_name == ""


class TestRuntimeReExports:
    def test_pob_engine_importable(self):
        assert PoBEngine is not None

    def test_check_lua_version_importable(self):
        assert callable(check_lua_version)

    def test_get_engine_importable(self):
        assert callable(get_engine)

    def test_get_pob_info_importable(self):
        assert callable(get_pob_info)


class TestStubsReExport:
    def test_register_stubs_importable(self):
        assert callable(register_stubs)


# ── Pydantic invariant tests ────────────────────────────────────────────────


class TestExtractStatsInvariants:
    def test_filters_non_numeric_values(self):
        mock_table = {
            "Life": 5000,
            "Mana": 1000.5,
            "string_field": "not_a_number",
            "bool_field": True,
            "none_field": None,
        }
        result = extract_stats(mock_table)
        # Bool is technically int subclass — verify behavior
        for v in result.stats.values():
            assert isinstance(v, float)
        assert "string_field" not in result.stats
        assert "none_field" not in result.stats

    def test_all_stats_are_finite_floats(self):
        mock_table = {"Life": 5000, "Mana": 1000.5, "DPS": 100000}
        result = extract_stats(mock_table)
        import math

        for v in result.stats.values():
            assert isinstance(v, float)
            assert math.isfinite(v)

    def test_int_values_become_float(self):
        # Semantic invariant: stats dict[str, float] — int inputs must be coerced
        mock_table = {"Life": 5000}
        result = extract_stats(mock_table)
        assert isinstance(result.stats["Life"], float)
        assert result.stats["Life"] == 5000.0

    def test_negative_numbers_preserved(self):
        mock_table = {"NegativeStat": -50, "ZeroStat": 0}
        result = extract_stats(mock_table)
        assert result.stats["NegativeStat"] == -50.0
        assert result.stats["ZeroStat"] == 0.0

    def test_empty_stats_invariant(self):
        result = extract_stats({})
        assert result.stats == {}
        assert result.build_name == ""

    def test_build_name_preserved(self):
        result = extract_stats({"Life": 5000}, build_name="My Build")
        assert result.build_name == "My Build"

    def test_returns_engine_stats_model(self):
        from poe.models.build.engine import EngineStats

        result = extract_stats({"Life": 5000})
        assert isinstance(result, EngineStats)

    def test_stats_keys_are_strings(self):
        mock_table = {"Life": 5000, "TotalDPS": 100000}
        result = extract_stats(mock_table)
        for k in result.stats:
            assert isinstance(k, str)


class TestExtractStatsBoolFiltering:
    def test_bool_filtered_or_coerced(self):
        # In Python, bool is a subclass of int. The implementation uses
        # isinstance(v, (int, float)) which includes bool. Check the actual
        # behavior is consistent with the dict[str, float] contract.
        mock_table = {"BoolField": True, "Life": 5000}
        result = extract_stats(mock_table)
        # If bool passes the int check, it becomes 1.0/0.0; the semantic
        # invariant is that all values must be float-compatible
        for v in result.stats.values():
            assert isinstance(v, float)


class TestLuaTableToDictNegativePaths:
    def test_attribute_error_returns_raw(self):
        # Object that fails the items() iteration with AttributeError
        class Bad:
            def items(self):
                raise AttributeError("no items")

            def __str__(self):
                return "bad-object"

        result = lua_table_to_dict(Bad())
        assert result == {"_raw": "bad-object"}

    def test_type_error_returns_raw(self):
        class BadType:
            def items(self):
                raise TypeError("not iterable")

            def __str__(self):
                return "bad-type"

        result = lua_table_to_dict(BadType())
        assert result == {"_raw": "bad-type"}

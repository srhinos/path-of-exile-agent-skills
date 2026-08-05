from __future__ import annotations

from unittest.mock import patch

import pytest

from poe.exceptions import EngineNotAvailableError
from poe.services.build.engine_service import EngineService


class TestEngineService:
    def test_info(self):
        svc = EngineService()
        result = svc.info()
        assert isinstance(result, dict)


class TestEngineServiceCoverage:
    def test_load_runtime_error(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=RuntimeError("no lua"),
        ):
            with pytest.raises(EngineNotAvailableError, match="no lua"):
                svc.load("test")

    def test_load_error_in_info(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "load_build": lambda self, name: {"error": "init failed"},
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            with pytest.raises(EngineNotAvailableError, match="init failed"):
                svc.load("test")

    def test_load_success(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "load_build": lambda self, name: {"className": "Witch"},
                "get_stats": lambda self: {"Life": 5000},
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.load("test")
            assert result["stats"]["Life"] == 5000

    def test_stats_no_build(self):
        svc = EngineService()
        mock_eng = type("MockEngine", (), {"build_loaded": False})()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            with pytest.raises(EngineNotAvailableError, match="No build"):
                svc.stats()

    def test_stats_success(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {"Life": 5000},
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats()
            assert result["Life"] == 5000

    def test_stats_import_error(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=ImportError("no lupa"),
        ):
            with pytest.raises(EngineNotAvailableError, match="no lupa"):
                svc.stats()

    def test_stats_category_off(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "AverageDamage": 5000,
                    "Life": 4000,
                    "Mana": 2000,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="off")
        assert "TotalDPS" in result
        assert "AverageDamage" in result
        assert "Life" not in result
        assert "Mana" not in result

    def test_stats_category_offence_alias(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "Life": 4000,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="offence")
        assert "TotalDPS" in result
        assert "Life" not in result

    def test_stats_category_offense_alias(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "Life": 4000,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="offense")
        assert "TotalDPS" in result
        assert "Life" not in result

    def test_stats_category_def(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "Life": 4000,
                    "Mana": 2000,
                    "EnergyShield": 1000,
                    "Armour": 500,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="def")
        assert "Life" in result
        assert "Mana" in result
        assert "EnergyShield" in result
        assert "Armour" in result
        assert "TotalDPS" not in result

    def test_stats_category_defence_alias(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "Life": 4000,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="defence")
        assert "Life" in result
        assert "TotalDPS" not in result

    def test_stats_category_defense_alias(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "Life": 4000,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="defense")
        assert "Life" in result
        assert "TotalDPS" not in result

    def test_stats_category_custom_filter(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "CritChance": 50,
                    "Life": 4000,
                },
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="Crit")
        assert "CritChance" in result
        assert "TotalDPS" not in result
        assert "Life" not in result

    def test_stats_category_all_returns_everything(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {"Life": 4000, "TotalDPS": 100000},
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="all")
        assert "Life" in result
        assert "TotalDPS" in result

    def test_stats_non_dict_returns_as_is(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: "raw stats string",
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="off")
        assert result == "raw stats string"

    def test_stats_with_name_loads_build(self):
        svc = EngineService()
        loaded = []
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "load_build": lambda self, name: loaded.append(name),
                "get_stats": lambda self: {"Life": 4000},
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(name="my_build")
        assert loaded == ["my_build"]
        assert result["Life"] == 4000

    def test_stats_runtime_error_wraps(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=RuntimeError("engine crash"),
        ):
            with pytest.raises(EngineNotAvailableError, match="engine crash"):
                svc.stats()

    def test_stats_file_not_found_wraps(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=FileNotFoundError("missing"),
        ):
            with pytest.raises(EngineNotAvailableError, match="missing"):
                svc.stats()

    def test_stats_os_error_wraps(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=OSError("os error"),
        ):
            with pytest.raises(EngineNotAvailableError, match="os error"):
                svc.stats()


# ── Negative tests for every raise path ─────────────────────────────────────


class TestEngineServiceRaises:
    def test_load_wraps_runtime_error(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(EngineNotAvailableError, match="boom"):
                svc.load("test")

    def test_load_wraps_import_error(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=ImportError("no lupa"),
        ):
            with pytest.raises(EngineNotAvailableError, match="no lupa"):
                svc.load("test")

    def test_load_wraps_file_not_found(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=FileNotFoundError("not there"),
        ):
            with pytest.raises(EngineNotAvailableError, match="not there"):
                svc.load("test")

    def test_load_wraps_os_error(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=OSError("os error"),
        ):
            with pytest.raises(EngineNotAvailableError, match="os error"):
                svc.load("test")

    def test_load_inherits_from_poe_error(self):
        from poe.exceptions import PoeError

        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_engine",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(PoeError):
                svc.load("test")


# ── Category alias full coverage ────────────────────────────────────────────


class TestStatsCategoryFullCoverage:
    @pytest.fixture
    def mock_eng(self):
        return type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self: {
                    "TotalDPS": 100000,
                    "AverageHit": 5000,
                    "CombinedDPS": 99999,
                    "Life": 4000,
                    "Mana": 2000,
                    "EnergyShield": 1500,
                    "Armour": 800,
                    "Evasion": 600,
                    "FireResist": 75,
                    "ColdResist": 75,
                    "LightningResist": 75,
                    "ChaosResist": -30,
                    "BlockChance": 25,
                    "DodgeChance": 30,
                    "SuppressChance": 100,
                    "EHP": 12000,
                    "DamageReduction": 50,
                    "LifeRegen": 100,
                    "Ward": 0,
                },
            },
        )()

    @pytest.mark.parametrize("category", ["off", "offence", "offense"])
    def test_offence_aliases_filter_to_dps_terms(self, mock_eng, category):
        svc = EngineService()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category=category)
        # Invariant: result should not contain Life/Mana/etc.
        assert "Life" not in result
        assert "Mana" not in result
        assert "TotalDPS" in result

    @pytest.mark.parametrize("category", ["def", "defence", "defense"])
    def test_defence_aliases_filter_to_def_terms(self, mock_eng, category):
        svc = EngineService()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category=category)
        # Invariant: result should not contain DPS
        assert "TotalDPS" not in result
        assert "Life" in result
        assert "Mana" in result

    @pytest.mark.parametrize("category", ["OFF", "Off", "OFFENCE", "Offence"])
    def test_offence_category_case_insensitive(self, mock_eng, category):
        svc = EngineService()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category=category)
        assert "TotalDPS" in result

    @pytest.mark.parametrize("category", ["DEF", "Def", "DEFENCE", "Defence"])
    def test_defence_category_case_insensitive(self, mock_eng, category):
        svc = EngineService()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category=category)
        assert "Life" in result


# ── Stats invariants ────────────────────────────────────────────────────────


class TestStatsInvariants:
    def test_filtered_stats_subset_of_all(self):
        svc = EngineService()
        all_stats = {
            "Life": 5000,
            "TotalDPS": 100000,
            "Mana": 1000,
        }
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self, all_stats=all_stats: dict(all_stats),
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            off_result = svc.stats(category="off")
            def_result = svc.stats(category="def")
        # Invariant: filtered category must be a subset of all stats
        assert set(off_result.keys()).issubset(all_stats.keys())
        assert set(def_result.keys()).issubset(all_stats.keys())

    def test_off_and_def_no_overlap_for_disjoint_terms(self):
        svc = EngineService()
        # Use clearly off-only and def-only stats
        all_stats = {"TotalDPS": 100000, "Life": 5000, "Mana": 2000, "Armour": 100}
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self, all_stats=all_stats: dict(all_stats),
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            off_result = svc.stats(category="off")
            def_result = svc.stats(category="def")
        # Invariant: TotalDPS in off, not in def
        assert "TotalDPS" in off_result
        assert "TotalDPS" not in def_result
        # Invariant: Life in def, not in off
        assert "Life" in def_result
        assert "Life" not in off_result

    def test_all_category_returns_full_set(self):
        svc = EngineService()
        all_stats = {"Life": 5000, "TotalDPS": 100000, "Custom": 42}
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self, all_stats=all_stats: dict(all_stats),
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="all")
        # Invariant: all stats present
        assert set(result.keys()) == set(all_stats.keys())


# ── Engine info return invariants ───────────────────────────────────────────


class TestEngineInfo:
    def test_info_returns_dict(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_pob_info",
            return_value={"pob_path": "/tmp", "version": "2.62.0"},
        ):
            result = svc.info()
        assert isinstance(result, dict)
        assert "pob_path" in result

    def test_info_passes_through_get_pob_info(self):
        svc = EngineService()
        with patch(
            "poe.services.build.engine_service.get_pob_info",
            return_value={"error": "missing"},
        ):
            result = svc.info()
        assert result == {"error": "missing"}


# ── Custom-substring category filter ────────────────────────────────────────


class TestCustomCategoryFilter:
    @pytest.mark.parametrize(
        ("category", "expected_keys"),
        [
            ("Life", {"Life", "LifeRegen"}),
            ("DPS", {"TotalDPS"}),
        ],
    )
    def test_custom_substring_filter(self, category, expected_keys):
        svc = EngineService()
        all_stats = {"Life": 5000, "LifeRegen": 100, "TotalDPS": 100000, "Mana": 2000}
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self, all_stats=all_stats: dict(all_stats),
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category=category)
        assert set(result.keys()) == expected_keys

    def test_empty_substring_match(self):
        svc = EngineService()
        all_stats = {"Life": 5000, "TotalDPS": 100000}
        mock_eng = type(
            "MockEngine",
            (),
            {
                "build_loaded": True,
                "get_stats": lambda self, all_stats=all_stats: dict(all_stats),
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.stats(category="zzzz_no_match_zzzz")
        assert result == {}


# ── Load result shape invariant ─────────────────────────────────────────────


class TestLoadShape:
    def test_load_returns_build_info_and_stats(self):
        svc = EngineService()
        mock_eng = type(
            "MockEngine",
            (),
            {
                "load_build": lambda self, name: {"className": "Ranger", "level": 90},
                "get_stats": lambda self: {"Life": 4000, "TotalDPS": 50000},
            },
        )()
        with patch("poe.services.build.engine_service.get_engine", return_value=mock_eng):
            result = svc.load("test")
        # Semantic invariant: result must have both keys
        assert "build_info" in result
        assert "stats" in result
        assert result["build_info"]["className"] == "Ranger"
        assert result["stats"]["Life"] == 4000

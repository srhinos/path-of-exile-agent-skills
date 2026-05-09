from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app
from poe.services.build.engine_service import EngineService
from tests.conftest import invoke_cli

_PATCH_SVC = "poe.commands.build.engine.commands._svc"


class TestEngineStatsWithName:
    @patch("poe.services.build.engine_service.get_engine")
    def test_stats_loads_build_when_name_provided(self, mock_get_engine):
        mock_eng = MagicMock()
        mock_eng.get_stats.return_value = {"Life": 5000, "TotalDPS": 100000}
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        result = svc.stats(name="TestBuild", category="all")

        mock_eng.load_build.assert_called_once_with("TestBuild")
        assert result["Life"] == 5000

    @patch("poe.services.build.engine_service.get_engine")
    def test_stats_without_name_requires_loaded_build(self, mock_get_engine):
        mock_eng = MagicMock()
        mock_eng.build_loaded = True
        mock_eng.get_stats.return_value = {"Life": 5000}
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        result = svc.stats(category="all")
        assert result["Life"] == 5000


class TestEngineLoadCli:
    def test_engine_load_cli(self):
        mock_svc = MagicMock()
        mock_svc.load.return_value = {"build_info": {"name": "test"}, "stats": {"Life": 5000}}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "load", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["stats"]["Life"] == 5000


class TestEngineStatsCli:
    def test_engine_stats_cli(self):
        mock_svc = MagicMock()
        mock_svc.stats.return_value = {"Life": 5000, "TotalDPS": 100000}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "stats", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["Life"] == 5000


class TestEngineInfoCli:
    def test_engine_info_cli(self):
        mock_svc = MagicMock()
        mock_svc.info.return_value = {"pob_path": "/some/path", "available": True}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "info", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["available"] is True


class TestEngineSvcFactory:
    @patch("poe.commands.build.engine.commands.EngineService")
    def test_svc_returns_engine_service(self, mock_cls):
        from poe.commands.build.engine.commands import _svc

        mock_cls.return_value = MagicMock()
        result = _svc()
        mock_cls.assert_called_once()
        assert result is mock_cls.return_value


# ── engine load: error propagation ───────────────────────────────────────────


class TestEngineLoadErrors:
    def test_engine_load_propagates_engine_not_available(self):
        from poe.exceptions import EngineNotAvailableError

        mock_svc = MagicMock()
        mock_svc.load.side_effect = EngineNotAvailableError("PoB unavailable")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "load", "test"])
        assert result.exit_code == 1
        assert isinstance(result.exception, EngineNotAvailableError)

    def test_engine_stats_propagates_engine_not_available(self):
        from poe.exceptions import EngineNotAvailableError

        mock_svc = MagicMock()
        mock_svc.stats.side_effect = EngineNotAvailableError("No build loaded")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "stats"])
        assert result.exit_code == 1
        assert isinstance(result.exception, EngineNotAvailableError)


# ── engine load CLI: invariants ─────────────────────────────────────────────


class TestEngineLoadInvariants:
    def test_load_json_contains_build_info_and_stats(self):
        mock_svc = MagicMock()
        mock_svc.load.return_value = {
            "build_info": {"name": "test", "class_name": "Witch"},
            "stats": {"Life": 5000, "TotalDPS": 100000},
        }
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "load", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "build_info" in data
        assert "stats" in data
        assert data["build_info"]["name"] == "test"
        assert isinstance(data["stats"]["Life"], int)


# ── engine stats CLI: human output by default ───────────────────────────────


class TestEngineStatsHumanOutput:
    def test_engine_stats_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.stats.return_value = {"Life": 5000, "TotalDPS": 100000}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "stats", "test"])
        assert result.exit_code == 0
        assert "Life" in result.output
        assert "5000" in result.output


class TestEngineLoadHumanOutput:
    def test_engine_load_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.load.return_value = {
            "build_info": {"name": "test"},
            "stats": {"Life": 5000},
        }
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "load", "test"])
        assert result.exit_code == 0
        assert "Life" in result.output


class TestEngineInfoHumanOutput:
    def test_engine_info_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.info.return_value = {"pob_path": "/tmp/pob", "available": True}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "engine", "info"])
        assert result.exit_code == 0
        assert "pob_path" in result.output


# ── engine stats: parametrize over category aliases ─────────────────────────


class TestEngineStatsCategoryParams:
    @pytest.mark.parametrize(
        "category",
        ["all", "off", "offence", "offense", "def", "defence", "defense"],
    )
    def test_engine_stats_accepts_category_aliases(self, category):
        mock_svc = MagicMock()
        mock_svc.stats.return_value = {"Life": 5000}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                app, ["build", "engine", "stats", "test", "--category", category, "--json"]
            )
        assert result.exit_code == 0
        mock_svc.stats.assert_called_once_with(name="test", category=category)


# ── engine service-level invariants ─────────────────────────────────────────


class TestEngineServiceErrors:
    @patch("poe.services.build.engine_service.get_engine")
    def test_load_propagates_runtime_error(self, mock_get_engine):
        from poe.exceptions import EngineNotAvailableError

        mock_eng = MagicMock()
        mock_eng.load_build.side_effect = RuntimeError("boom")
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        with pytest.raises(EngineNotAvailableError):
            svc.load("test")

    @patch("poe.services.build.engine_service.get_engine")
    def test_load_with_engine_error_dict(self, mock_get_engine):
        from poe.exceptions import EngineNotAvailableError

        mock_eng = MagicMock()
        mock_eng.load_build.return_value = {"error": "Something bad"}
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        with pytest.raises(EngineNotAvailableError, match="Something bad"):
            svc.load("test")

    @patch("poe.services.build.engine_service.get_engine")
    def test_stats_without_name_no_loaded_build_raises(self, mock_get_engine):
        from poe.exceptions import EngineNotAvailableError

        mock_eng = MagicMock()
        mock_eng.build_loaded = False
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        with pytest.raises(EngineNotAvailableError):
            svc.stats()

    @patch("poe.services.build.engine_service.get_engine")
    def test_stats_off_category_filters(self, mock_get_engine):
        mock_eng = MagicMock()
        mock_eng.build_loaded = True
        mock_eng.get_stats.return_value = {
            "TotalDPS": 100,
            "Life": 5000,
            "AverageHit": 50,
            "Mana": 200,
        }
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        result = svc.stats(category="off")
        assert "TotalDPS" in result
        assert "AverageHit" in result
        assert "Life" not in result
        assert "Mana" not in result

    @patch("poe.services.build.engine_service.get_engine")
    def test_stats_def_category_filters(self, mock_get_engine):
        mock_eng = MagicMock()
        mock_eng.build_loaded = True
        mock_eng.get_stats.return_value = {
            "TotalDPS": 100,
            "Life": 5000,
            "EnergyShield": 1000,
            "AverageHit": 50,
        }
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        result = svc.stats(category="def")
        assert "Life" in result
        assert "EnergyShield" in result
        assert "TotalDPS" not in result
        assert "AverageHit" not in result

    @patch("poe.services.build.engine_service.get_engine")
    def test_stats_freeform_category_substring_match(self, mock_get_engine):
        mock_eng = MagicMock()
        mock_eng.build_loaded = True
        mock_eng.get_stats.return_value = {
            "FireResist": 75,
            "ColdResist": 75,
            "Life": 5000,
        }
        mock_get_engine.return_value = mock_eng

        svc = EngineService()
        result = svc.stats(category="resist")
        assert "FireResist" in result
        assert "ColdResist" in result
        assert "Life" not in result

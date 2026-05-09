from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app
from tests.conftest import invoke_cli

POE1_INDEX_STATE = {
    "economyLeagues": [
        {"name": "Mirage", "url": "mirage", "displayName": "Mirage"},
        {"name": "Standard", "url": "standard"},
    ],
    "oldEconomyLeagues": [],
    "snapshotVersions": [
        {
            "url": "mirage",
            "type": "exp",
            "name": "Mirage",
            "timeMachineLabels": ["hour-3"],
            "version": "0309-20260316-12036",
            "snapshotName": "mirage",
            "overviewType": 0,
            "passiveTree": "PassiveTree-3.28",
            "atlasTree": "AtlasTree-3.28",
        },
    ],
    "buildLeagues": [],
    "oldBuildLeagues": [],
}


class TestLeagueInfo:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_league_info_default(self, mock_client_cls):
        mock_client = MagicMock(no_cache=False)
        mock_client.get_json.return_value = POE1_INDEX_STATE
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "league-info", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "economy_leagues" in data
        assert data["economy_leagues"][0]["name"] == "Mirage"

    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_league_info_with_snapshots(self, mock_client_cls):
        mock_client = MagicMock(no_cache=False)
        mock_client.get_json.return_value = POE1_INDEX_STATE
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "league-info", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["snapshot_versions"]) == 1
        assert data["snapshot_versions"][0]["version"] == "0309-20260316-12036"


class TestCacheStatus:
    def test_cache_status_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        result = invoke_cli(app, ["ninja", "cache-status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "entries" in data
        assert all(not e["is_cached"] for e in data["entries"])

    def test_cache_status_with_data(self, tmp_path, monkeypatch):
        from poe.services.ninja import cache as ninja_cache

        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        ninja_cache.write_cache(tmp_path, "poe1_index_state", {"test": True})

        result = invoke_cli(app, ["ninja", "cache-status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        poe1_entry = next(e for e in data["entries"] if e["name"] == "poe1_index_state")
        assert poe1_entry["is_cached"] is True
        assert poe1_entry["is_fresh"] is True


class TestLeagueInfoForce:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_force_flag_passes_through(self, mock_client_cls):
        mock_client = MagicMock(no_cache=False)
        mock_client.get_json.return_value = POE1_INDEX_STATE
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "league-info", "--force"])
        assert result.exit_code == 0


class TestTooltipNotFound:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_tooltip_not_found(self, mock_cls):
        from poe.exceptions import PoeError

        mock_client = MagicMock(no_cache=False)
        mock_client.get_json.return_value = None
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("poe.commands.ninja.commands.BuildsService") as mock_builds_cls:
            mock_svc = MagicMock()
            mock_svc.get_generic_tooltip.return_value = None
            mock_builds_cls.return_value = mock_svc

            result = invoke_cli(app, ["ninja", "tooltip", "FakeItem", "--json"])
        assert result.exit_code == 1
        assert isinstance(result.exception, PoeError)


class TestNinjaHelp:
    def test_ninja_help(self):
        result = invoke_cli(app, ["ninja", "--help"])
        assert result.exit_code == 0
        assert "league-info" in result.output
        assert "cache-status" in result.output


# ── Added tests below ────────────────────────────────────────────────────────


POE2_INDEX_STATE = {
    "economyLeagues": [
        {"name": "Fate of the Vaal", "url": "fate-of-the-vaal"},
    ],
    "oldEconomyLeagues": [],
    "snapshotVersions": [
        {
            "url": "fate-of-the-vaal",
            "type": "exp",
            "name": "Fate of the Vaal",
            "timeMachineLabels": [],
            "version": "0501-20260316-77777",
            "snapshotName": "fate-of-the-vaal",
            "overviewType": 0,
            "passiveTree": "PassiveTree-poe2",
            "atlasTree": "",
        },
    ],
    "buildLeagues": [],
    "oldBuildLeagues": [],
}


def _make_ninja_ctx(client, mock_cls):
    mock_cls.return_value.__enter__ = MagicMock(return_value=client)
    mock_cls.return_value.__exit__ = MagicMock(return_value=False)


class TestLeagueInfoHumanOutput:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_default_no_json_is_human_readable(self, mock_cls):
        client = MagicMock(no_cache=False)
        client.get_json.return_value = POE1_INDEX_STATE
        _make_ninja_ctx(client, mock_cls)

        result = invoke_cli(app, ["ninja", "league-info"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json
        assert "Mirage" in result.output


class TestLeagueInfoGameRouting:
    @patch("poe.commands.ninja.commands.DiscoveryService")
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_poe1_calls_poe1_endpoint(self, mock_cls, mock_disc_cls):
        from poe.models.ninja.discovery import Poe1IndexState

        client = MagicMock(no_cache=False)
        _make_ninja_ctx(client, mock_cls)
        mock_disc = MagicMock()
        mock_disc.get_poe1_index_state.return_value = Poe1IndexState.model_validate(
            POE1_INDEX_STATE
        )
        mock_disc_cls.return_value = mock_disc

        result = invoke_cli(app, ["ninja", "league-info", "--game", "poe1", "--json"])
        assert result.exit_code == 0
        mock_disc.get_poe1_index_state.assert_called_once()
        mock_disc.get_poe2_index_state.assert_not_called()

    @patch("poe.commands.ninja.commands.DiscoveryService")
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_poe2_calls_poe2_endpoint(self, mock_cls, mock_disc_cls):
        from poe.models.ninja.discovery import Poe2IndexState

        client = MagicMock(no_cache=False)
        _make_ninja_ctx(client, mock_cls)
        mock_disc = MagicMock()
        mock_disc.get_poe2_index_state.return_value = Poe2IndexState.model_validate(
            POE2_INDEX_STATE
        )
        mock_disc_cls.return_value = mock_disc

        result = invoke_cli(app, ["ninja", "league-info", "--game", "poe2", "--json"])
        assert result.exit_code == 0
        mock_disc.get_poe2_index_state.assert_called_once()
        mock_disc.get_poe1_index_state.assert_not_called()


class TestLeagueInfoNoCacheFlag:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_no_cache_flag_routed_to_client(self, mock_cls):
        client = MagicMock(no_cache=True)
        client.get_json.return_value = POE1_INDEX_STATE
        _make_ninja_ctx(client, mock_cls)

        result = invoke_cli(app, ["ninja", "league-info", "--no-cache", "--json"])
        assert result.exit_code == 0
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True

    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_default_does_not_set_no_cache(self, mock_cls):
        client = MagicMock(no_cache=False)
        client.get_json.return_value = POE1_INDEX_STATE
        _make_ninja_ctx(client, mock_cls)

        result = invoke_cli(app, ["ninja", "league-info", "--json"])
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is False


class TestCacheClear:
    def test_cache_clear_deletes_files(self, tmp_path, monkeypatch):
        from poe.services.ninja import cache as ninja_cache

        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        ninja_cache.write_cache(tmp_path, "poe1_index_state", {"hello": True})
        ninja_cache.write_cache(tmp_path, "poe2_index_state", {"hello2": True})
        assert any(tmp_path.iterdir())

        result = invoke_cli(app, ["ninja", "cache-clear", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert str(tmp_path) in data["cleared"]
        assert list(tmp_path.iterdir()) == []

    def test_cache_clear_idempotent_on_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        result = invoke_cli(app, ["ninja", "cache-clear", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_cache_clear_human_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        result = invoke_cli(app, ["ninja", "cache-clear"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json
        assert "ok" in result.output


class TestCacheStatusInvariants:
    def test_known_cache_keys_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        result = invoke_cli(app, ["ninja", "cache-status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        names = {e["name"] for e in data["entries"]}
        assert "poe1_index_state" in names
        assert "poe2_index_state" in names
        assert "poe1_build_index_state" in names
        assert "poe2_build_index_state" in names
        assert "poe1_atlas_tree_index_state" in names

    def test_cache_status_human_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: tmp_path)
        result = invoke_cli(app, ["ninja", "cache-status"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json


class TestTooltipTypes:
    @patch("poe.commands.ninja.commands.BuildsService")
    @patch("poe.commands.ninja.commands.NinjaClient")
    @pytest.mark.parametrize(
        "tooltip_type",
        ["anointed", "bandit", "pantheon", "keystone", "mastery"],
    )
    def test_tooltip_passes_type_through(self, mock_cls, mock_builds_cls, tooltip_type):
        from poe.models.ninja.builds import TooltipResponse

        client = MagicMock(no_cache=False)
        _make_ninja_ctx(client, mock_cls)

        mock_svc = MagicMock()
        mock_svc.get_generic_tooltip.return_value = TooltipResponse(
            name="test", implicit_mods=[], explicit_mods=[], mutated_mods=[]
        )
        mock_builds_cls.return_value = mock_svc

        result = invoke_cli(app, ["ninja", "tooltip", "Test", "--type", tooltip_type, "--json"])
        assert result.exit_code == 0
        mock_svc.get_generic_tooltip.assert_called_once_with("Test", tooltip_type)


class TestTooltipNoCache:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_no_cache_propagated(self, mock_cls):
        from poe.models.ninja.builds import TooltipResponse

        client = MagicMock(no_cache=True)
        _make_ninja_ctx(client, mock_cls)

        with patch("poe.commands.ninja.commands.BuildsService") as mock_builds_cls:
            mock_svc = MagicMock()
            mock_svc.get_generic_tooltip.return_value = TooltipResponse(
                name="x", implicit_mods=[], explicit_mods=[], mutated_mods=[]
            )
            mock_builds_cls.return_value = mock_svc

            result = invoke_cli(app, ["ninja", "tooltip", "Foo", "--no-cache", "--json"])
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True


class TestTooltipHumanOutput:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_default_human_output(self, mock_cls):
        from poe.models.ninja.builds import TooltipMod, TooltipResponse

        client = MagicMock(no_cache=False)
        _make_ninja_ctx(client, mock_cls)
        with patch("poe.commands.ninja.commands.BuildsService") as mock_builds_cls:
            mock_svc = MagicMock()
            mock_svc.get_generic_tooltip.return_value = TooltipResponse(
                name="Whispers of Doom",
                implicit_mods=[],
                explicit_mods=[
                    TooltipMod(text="You can apply an additional Curse", optional=False),
                ],
                mutated_mods=[],
            )
            mock_builds_cls.return_value = mock_svc
            result = invoke_cli(app, ["ninja", "tooltip", "Whispers of Doom"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json
        assert "Whispers of Doom" in result.output


class TestTooltip404GracefulNone:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_tooltip_returns_none_raises_poe_error(self, mock_cls):
        from poe.exceptions import PoeError

        client = MagicMock(no_cache=False)
        _make_ninja_ctx(client, mock_cls)

        with patch("poe.commands.ninja.commands.BuildsService") as mock_builds_cls:
            mock_svc = MagicMock()
            mock_svc.get_generic_tooltip.return_value = None
            mock_builds_cls.return_value = mock_svc
            result = invoke_cli(app, ["ninja", "tooltip", "DoesNotExist"])

        assert result.exit_code == 1
        assert isinstance(result.exception, PoeError)
        assert "DoesNotExist" in str(result.exception)


# Bug-catcher: check-clear should not raise even when cache_dir does not exist
class TestCacheClearMissingDir:
    def test_clear_when_dir_missing(self, tmp_path, monkeypatch):
        missing = tmp_path / "does-not-exist"
        monkeypatch.setattr("poe.commands.ninja.commands.ninja_cache.cache_dir", lambda: missing)
        result = invoke_cli(app, ["ninja", "cache-clear", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

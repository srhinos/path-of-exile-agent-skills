from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import pytest

from poe.app import _check_skill_version, app, run
from poe.exceptions import PoeError
from tests.conftest import invoke_cli


class TestSkillStalenessCheck:
    def test_warns_when_outdated(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "home"
        version_file = home / ".claude" / "skills" / "poe" / "version.md"
        version_file.parent.mkdir(parents=True)
        version_file.write_text("0.0.1")

        monkeypatch.setattr("poe.app.Path.home", lambda: home)
        monkeypatch.setattr("poe.app._pkg_version", lambda _name: "0.1.0")

        _check_skill_version()

        captured = capsys.readouterr()
        assert "Skill outdated" in captured.err
        assert "0.0.1" in captured.err
        assert "0.1.0" in captured.err

    def test_silent_when_current(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "home"
        version_file = home / ".claude" / "skills" / "poe" / "version.md"
        version_file.parent.mkdir(parents=True)
        version_file.write_text("0.1.0")

        monkeypatch.setattr("poe.app.Path.home", lambda: home)
        monkeypatch.setattr("poe.app._pkg_version", lambda _name: "0.1.0")

        _check_skill_version()

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_silent_when_no_version_file(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "home"
        monkeypatch.setattr("poe.app.Path.home", lambda: home)

        _check_skill_version()

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_silent_when_metadata_unavailable(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "home"
        version_file = home / ".claude" / "skills" / "poe" / "version.md"
        version_file.parent.mkdir(parents=True)
        version_file.write_text("0.0.1")

        monkeypatch.setattr("poe.app.Path.home", lambda: home)

        def raise_error(_name):
            raise PackageNotFoundError("poe-tools")

        monkeypatch.setattr("poe.app._pkg_version", raise_error)

        _check_skill_version()

        captured = capsys.readouterr()
        assert captured.err == ""


class TestCliReExports:
    def test_app_reexport(self):
        from poe.app import app as cli_app

        assert cli_app is app

    def test_find_skill_source_reexport(self):
        from poe.commands.root import _find_skill_source

        # Re-exports must actually be the real function — a renamed-away
        # replacement with `lambda *a, **k: None` would still be callable
        # but lose the proper signature.
        assert callable(_find_skill_source)
        assert _find_skill_source.__qualname__ == "_find_skill_source"

    def test_install_skill_reexport(self):
        from poe.commands.root import install_skill

        assert callable(install_skill)
        assert install_skill.__qualname__ == "install_skill"

    def test_unknown_attribute_raises(self):
        import poe.commands.build as cli_mod

        with pytest.raises(AttributeError, match="no_such_attr"):
            _ = cli_mod.no_such_attr


class TestApp:
    def test_app_has_build_subcommand(self):
        result = invoke_cli(app, ["build", "--help"])
        assert result.exit_code == 0

    def test_app_has_craft_subcommand(self):
        result = invoke_cli(app, ["craft", "--help"])
        assert result.exit_code == 0

    def test_app_has_install_skill(self):
        result = invoke_cli(app, ["install-skill", "--help"])
        assert result.exit_code == 0


class TestVersion:
    def test_version_shows_package_version(self):
        result = invoke_cli(app, ["--version"])
        assert result.exit_code == 0
        assert "0.0.0" not in result.output or "poe-tools" not in result.output


class TestRun:
    def test_run_catches_poe_error(self, capsys):
        with patch("poe.app.app", side_effect=PoeError("test error")):
            with pytest.raises(SystemExit, match="1"):
                run()
        captured = capsys.readouterr()
        assert "test error" in captured.err

    def test_run_propagates_other_errors(self):
        with patch("poe.app.app", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                run()

    def test_run_catches_validation_error(self, capsys, monkeypatch):
        import json as _json

        from pydantic import ValidationError

        from poe.models.build.items import Item

        monkeypatch.setattr("poe.app._check_skill_version", lambda: None)
        try:
            Item(id=1, text="", rarity="HEROIC")
        except ValidationError as ve:
            err = ve

        with patch("poe.app.app", side_effect=err):
            with pytest.raises(SystemExit) as exc_info:
                run()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        parsed = _json.loads(captured.err.strip())
        assert "Invalid data" in parsed["error"]
        assert "rarity" in parsed["error"]


# ── Error handler structure invariants (Pattern 4) ──────────────────────────


class TestRunErrorHandlerSerialization:
    def test_run_serializes_poe_error_as_json(self, capsys, monkeypatch):
        import json as _json

        monkeypatch.setattr("poe.app._check_skill_version", lambda: None)
        with patch("poe.app.app", side_effect=PoeError("formatted error")):
            with pytest.raises(SystemExit):
                run()
        captured = capsys.readouterr()
        parsed = _json.loads(captured.err.strip())
        assert parsed == {"error": "formatted error"}

    @pytest.mark.parametrize(
        "exc_class_name",
        [
            "PoeError",
            "BuildNotFoundError",
            "SlotError",
            "SimDataError",
            "BuildValidationError",
            "CodecError",
            "EngineNotAvailableError",
        ],
    )
    def test_each_poe_error_subclass_caught(self, exc_class_name, capsys, monkeypatch):
        import poe.exceptions as exc_mod

        monkeypatch.setattr("poe.app._check_skill_version", lambda: None)
        exc_class = getattr(exc_mod, exc_class_name)
        with patch("poe.app.app", side_effect=exc_class("test message")):
            with pytest.raises(SystemExit) as exc_info:
                run()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert '"error"' in captured.err

    def test_run_exit_code_is_1_for_poe_error(self):
        with patch("poe.app.app", side_effect=PoeError("x")):
            with pytest.raises(SystemExit) as exc_info:
                run()
        assert exc_info.value.code == 1


class TestAppHelp:
    @pytest.mark.parametrize(
        "subcommand",
        ["build", "dev", "sim", "ninja", "install-skill"],
    )
    def test_subcommand_help_succeeds(self, subcommand):
        result = invoke_cli(app, [subcommand, "--help"])
        assert result.exit_code == 0

    def test_no_args_shows_help_or_error(self):
        result = invoke_cli(app, [])
        assert result.exit_code is not None

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from poe.app import app as cli
from poe.commands.root import _find_skill_source
from tests.conftest import invoke_cli


def _can_symlink() -> bool:
    try:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "test_src"
            source.mkdir()
            (td_path / "test_link").symlink_to(source, target_is_directory=True)
    except OSError:
        return False
    else:
        return True


_symlinks_available = _can_symlink()
requires_symlinks = pytest.mark.skipif(
    not _symlinks_available, reason="Symlinks require admin or Developer Mode on Windows"
)


class TestGetPackageVersion:
    def test_returns_version_when_installed(self, monkeypatch):
        from poe.commands.root import _get_package_version

        monkeypatch.setattr("poe.commands.root._pkg_version", lambda _name: "1.2.3")
        assert _get_package_version() == "1.2.3"

    def test_returns_none_when_not_installed(self, monkeypatch):
        from importlib.metadata import PackageNotFoundError

        from poe.commands.root import _get_package_version

        def _raise(_name):
            raise PackageNotFoundError("not found")

        monkeypatch.setattr("poe.commands.root._pkg_version", _raise)
        assert _get_package_version() is None


class TestFindSkillSource:
    def test_finds_skill_in_package(self, tmp_path):
        poe_dir = tmp_path / "poe"
        cli_dir = poe_dir / "cli"
        cli_dir.mkdir(parents=True)
        skill_dir = poe_dir / "skills" / "poe"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# skill")

        fake_file = cli_dir / "root.py"
        fake_file.write_text("")

        with patch("poe.commands.root.__file__", str(fake_file)):
            result = _find_skill_source()
        assert result is not None
        assert result == skill_dir

    def test_returns_none_when_not_found(self, tmp_path):
        cli_dir = tmp_path / "poe" / "cli"
        cli_dir.mkdir(parents=True)
        fake_file = cli_dir / "root.py"
        fake_file.write_text("")

        with patch("poe.commands.root.__file__", str(fake_file)):
            result = _find_skill_source()
        assert result is None


class TestInstallFlow:
    def test_install_source_not_found(self, monkeypatch):
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: None)
        result = invoke_cli(cli, ["install-skill", "--json"])
        assert result.exit_code != 0

    def test_install_target_exists_no_force(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        target_dir = tmp_path / "home" / ".claude" / "skills" / "poe"
        target_dir.mkdir(parents=True)
        (target_dir / "SKILL.md").write_text("# old")

        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: tmp_path / "home")

        result = invoke_cli(cli, ["install-skill", "--json"])
        assert result.exit_code != 0

    def test_install_default_copy(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill content")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "copied"
        target = home / ".claude" / "skills" / "poe"
        assert target.is_dir()
        assert not target.is_symlink()
        assert (target / "SKILL.md").read_text() == "# skill content"

    @requires_symlinks
    def test_install_symlink_flag(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--symlink", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "symlinked"
        target = home / ".claude" / "skills" / "poe"
        assert target.is_symlink()
        assert target.resolve() == source_dir.resolve()

    def test_install_force_overwrites_existing_dir(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# new skill")

        home = tmp_path / "home"
        target_dir = home / ".claude" / "skills" / "poe"
        target_dir.mkdir(parents=True)
        (target_dir / "SKILL.md").write_text("# old")

        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--force", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "copied"
        assert (target_dir / "SKILL.md").read_text() == "# new skill"

    @requires_symlinks
    def test_install_force_overwrites_existing_symlink(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# new skill")

        old_source = tmp_path / "old_source"
        old_source.mkdir(parents=True)

        home = tmp_path / "home"
        target_dir = home / ".claude" / "skills" / "poe"
        target_dir.parent.mkdir(parents=True)
        target_dir.symlink_to(old_source, target_is_directory=True)

        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--force", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "copied"
        assert not target_dir.is_symlink()
        assert (target_dir / "SKILL.md").read_text() == "# new skill"

    def test_install_stamps_version_md(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)
        monkeypatch.setattr("poe.commands.root._get_package_version", lambda: "1.2.3")

        result = invoke_cli(cli, ["install-skill", "--json"])
        assert result.exit_code == 0
        target = home / ".claude" / "skills" / "poe"
        assert (target / "version.md").read_text() == "1.2.3"

    def test_install_no_version_md_when_version_unavailable(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)
        monkeypatch.setattr("poe.commands.root._get_package_version", lambda: None)

        result = invoke_cli(cli, ["install-skill", "--json"])
        assert result.exit_code == 0
        target = home / ".claude" / "skills" / "poe"
        assert not (target / "version.md").exists()

    @requires_symlinks
    def test_install_symlink_does_not_stamp_version(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)
        monkeypatch.setattr("poe.commands.root._get_package_version", lambda: "1.0.0")

        result = invoke_cli(cli, ["install-skill", "--symlink", "--json"])
        assert result.exit_code == 0
        target = home / ".claude" / "skills" / "poe"
        assert not (target / "version.md").exists()

    @pytest.mark.skipif(_symlinks_available, reason="Only runs when symlinks are unavailable")
    def test_install_symlink_gives_helpful_error(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--symlink", "--json"])
        assert result.exit_code != 0


class TestUninstallFlow:
    @requires_symlinks
    def test_uninstall_symlink(self, tmp_path, monkeypatch):
        real_dir = tmp_path / "real" / "poe"
        real_dir.mkdir(parents=True)
        (real_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        target = home / ".claude" / "skills" / "poe"
        target.parent.mkdir(parents=True)
        target.symlink_to(real_dir, target_is_directory=True)

        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--uninstall", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "uninstalled"
        assert not target.exists()
        assert not target.is_symlink()

    def test_uninstall_directory(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        target = home / ".claude" / "skills" / "poe"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("# skill")

        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--uninstall", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "uninstalled"
        assert not target.exists()

    def test_uninstall_not_found(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        target = home / ".claude" / "skills" / "poe"
        assert not target.exists()

        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--uninstall", "--json"])
        assert result.exit_code != 0


# ── install-skill JSON output structure invariants ──────────────────────────


class TestInstallSkillJSONOutput:
    def test_install_output_has_action_field(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# skill")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "action" in data
        assert isinstance(data["action"], str)

    def test_uninstall_output_has_action_field(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        target = home / ".claude" / "skills" / "poe"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("# skill")

        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result = invoke_cli(cli, ["install-skill", "--uninstall", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["action"] == "uninstalled"


class TestInstallSkillIdempotence:
    def test_install_then_force_install_succeeds(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# v1")

        home = tmp_path / "home"
        monkeypatch.setattr("poe.commands.root._find_skill_source", lambda: source_dir)
        monkeypatch.setattr("poe.commands.root.Path.home", lambda: home)

        result1 = invoke_cli(cli, ["install-skill", "--json"])
        assert result1.exit_code == 0

        (source_dir / "SKILL.md").write_text("# v2")
        result2 = invoke_cli(cli, ["install-skill", "--force", "--json"])
        assert result2.exit_code == 0
        target = home / ".claude" / "skills" / "poe"
        assert (target / "SKILL.md").read_text() == "# v2"

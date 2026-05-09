"""Unit tests for poe.safety — clone-on-write and Claude folder detection."""

from __future__ import annotations

import pytest

from poe.exceptions import BuildNotFoundError, BuildValidationError
from poe.paths import resolve_build_file
from poe.safety import (
    get_claude_builds_path,
    is_inside_claude_folder,
    resolve_for_write,
    resolve_or_file_for_write,
)
from tests.conftest import MINIMAL_BUILD_XML

# ── Path traversal guards (resolve_for_write) ───────────────────────────────


class TestPathTraversalWrite:
    def test_reject_backslash(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            resolve_for_write("..\\windows\\system32")

    def test_reject_dotdot(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            resolve_for_write("../../escape")

    def test_relative_check(self, tmp_builds_dir, monkeypatch):
        """resolve_for_write has is_relative_to check on constructed path."""
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        # A name with slash is caught by validate_build_name before
        # reaching the is_relative_to check, so we verify slash is rejected
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            resolve_for_write("foo/bar")

    def test_is_relative_to_guard(self, tmp_builds_dir, monkeypatch):
        """is_relative_to guard rejects paths escaping Claude/."""
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        # Bypass validate_build_name to directly test the is_relative_to check
        monkeypatch.setattr("poe.paths.validate_build_name", lambda _name: None)
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            resolve_for_write("../../escape")


# ── Claude/ safety layer ────────────────────────────────────────────────────


class TestClaudeBuildsPaths:
    def test_get_claude_builds_path_creates_dir(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = get_claude_builds_path()
        assert claude_dir == tmp_builds_dir / "Claude"
        assert claude_dir.is_dir()

    def test_is_inside_claude_folder_true(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        claude_dir.mkdir(exist_ok=True)
        test_file = claude_dir / "build.xml"
        test_file.write_text("x")
        assert is_inside_claude_folder(test_file) is True

    def test_is_inside_claude_folder_false(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        outside = tmp_builds_dir / "BuildA.xml"
        assert is_inside_claude_folder(outside) is False

    def test_resolve_for_write_clones_outside_build(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        path, cloned_from = resolve_for_write("BuildA")
        assert path.parent.name == "Claude"
        assert path.name == "BuildA.xml"
        assert cloned_from == str(tmp_builds_dir / "BuildA.xml")
        # Original untouched
        assert (tmp_builds_dir / "BuildA.xml").exists()
        # Clone exists
        assert path.exists()

    def test_resolve_for_write_uses_existing_claude_copy(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        claude_dir.mkdir(exist_ok=True)
        existing = claude_dir / "BuildA.xml"
        existing.write_text(MINIMAL_BUILD_XML, encoding="utf-8")

        path, cloned_from = resolve_for_write("BuildA")
        assert path == existing
        assert cloned_from is None

    def test_resolve_for_write_already_in_claude(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        claude_dir.mkdir(exist_ok=True)
        build = claude_dir / "OnlyHere.xml"
        build.write_text(MINIMAL_BUILD_XML, encoding="utf-8")

        path, cloned_from = resolve_for_write("OnlyHere")
        assert path == build
        assert cloned_from is None

    def test_resolve_for_write_not_found(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        with pytest.raises((FileNotFoundError, BuildNotFoundError)):
            resolve_for_write("NonExistent")

    def test_resolve_prefers_claude_copy(self, tmp_builds_dir, monkeypatch):
        """resolve_build_file prefers Claude/ copy over original."""
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        claude_dir.mkdir(exist_ok=True)
        # Create Claude/ copy
        (claude_dir / "BuildA.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")

        result = resolve_build_file("BuildA")
        assert result.parent.name == "Claude"


# ── resolve_or_file_for_write ────────────────────────────────────────────────


class TestResolveOrFileForWrite:
    def test_with_file(self, tmp_path):
        p = tmp_path / "test.xml"
        p.write_text("<xml/>")
        path, cloned = resolve_or_file_for_write("ignored", str(p))
        assert path == p
        assert cloned is None

    def test_with_name(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        path, _cloned = resolve_or_file_for_write("BuildA", None)
        assert "Claude" in str(path)


# ── Clone-on-write directory state invariants ────────────────────────────────


class TestCloneOnWriteDirectoryStates:
    def test_creates_claude_dir_when_missing(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        assert not claude_dir.exists()

        path, cloned = resolve_for_write("BuildA")

        assert claude_dir.is_dir()
        assert path.parent == claude_dir
        assert cloned == str(tmp_builds_dir / "BuildA.xml")

    def test_clone_preserves_original_contents(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        original = tmp_builds_dir / "BuildA.xml"
        original_text = original.read_text(encoding="utf-8")

        path, _cloned = resolve_for_write("BuildA")

        assert path.read_text(encoding="utf-8") == original_text
        assert original.read_text(encoding="utf-8") == original_text

    def test_clone_does_not_mutate_original_after_write(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        original = tmp_builds_dir / "BuildA.xml"
        before = original.read_text(encoding="utf-8")
        path, _cloned = resolve_for_write("BuildA")
        path.write_text("MODIFIED CONTENT", encoding="utf-8")
        assert original.read_text(encoding="utf-8") == before

    def test_repeated_resolve_for_write_uses_existing_clone(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        path1, cloned1 = resolve_for_write("BuildA")
        path1.write_text("MUTATED", encoding="utf-8")
        path2, cloned2 = resolve_for_write("BuildA")
        assert path1 == path2
        assert cloned1 is not None
        assert cloned2 is None
        assert path2.read_text(encoding="utf-8") == "MUTATED"

    def test_resolve_for_write_extension_appended(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        path, _ = resolve_for_write("BuildA")
        assert path.name == "BuildA.xml"

    def test_resolve_for_write_extension_not_doubled(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        path, _ = resolve_for_write("BuildA.xml")
        assert path.name == "BuildA.xml"
        assert not path.name.endswith(".xml.xml")

    def test_get_claude_builds_path_idempotent(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        first = get_claude_builds_path()
        second = get_claude_builds_path()
        assert first == second
        assert first.is_dir()

    def test_resolve_or_file_for_write_explicit_file_no_safety(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        explicit = tmp_builds_dir / "BuildA.xml"
        path, cloned = resolve_or_file_for_write("ignored", str(explicit))
        assert path == explicit
        assert cloned is None
        assert "Claude" not in str(path)


# ── is_inside_claude_folder edge cases ───────────────────────────────────────


class TestIsInsideClaudeFolder:
    def test_path_outside_builds_dir_returns_false(self, tmp_builds_dir, monkeypatch, tmp_path):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        outside = tmp_path / "elsewhere.xml"
        outside.write_text("x")
        assert is_inside_claude_folder(outside) is False

    def test_nested_inside_claude(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        nested = claude_dir / "subdir"
        nested.mkdir(parents=True)
        nested_file = nested / "x.xml"
        nested_file.write_text("x")
        assert is_inside_claude_folder(nested_file) is True

    def test_claude_dir_itself(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        claude_dir = tmp_builds_dir / "Claude"
        claude_dir.mkdir(exist_ok=True)
        assert is_inside_claude_folder(claude_dir) is True

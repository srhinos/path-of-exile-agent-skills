"""Unit tests for pob.paths — path detection and build file resolution."""

from __future__ import annotations

import pytest

from poe.exceptions import BuildNotFoundError, BuildValidationError
from poe.paths import (
    get_builds_path,
    get_pob_path,
    list_build_files,
    resolve_build_file,
    resolve_or_file,
    validate_build_name,
)

# ── get_pob_path ─────────────────────────────────────────────────────────────


class TestGetPobPath:
    def test_env_override(self, tmp_path, monkeypatch):
        pob_dir = tmp_path / "PoB"
        pob_dir.mkdir()
        # Launch.lua presence is the marker of a valid PoB directory.
        (pob_dir / "Launch.lua").write_text("-- placeholder")
        monkeypatch.setenv("POB_PATH", str(pob_dir))
        assert get_pob_path() == pob_dir

    def test_env_dir_without_launch_lua_raises(self, tmp_path, monkeypatch):
        pob_dir = tmp_path / "wrong-dir"
        pob_dir.mkdir()
        monkeypatch.setenv("POB_PATH", str(pob_dir))
        monkeypatch.delenv("APPDATA", raising=False)
        with pytest.raises(BuildNotFoundError, match=r"Launch\.lua"):
            get_pob_path()

    def test_appdata_fallback(self, tmp_path, monkeypatch):
        pob_dir = tmp_path / "Path of Building Community"
        pob_dir.mkdir()
        (pob_dir / "Launch.lua").write_text("-- placeholder")
        monkeypatch.delenv("POB_PATH", raising=False)
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert get_pob_path() == pob_dir

    def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POB_PATH", raising=False)
        monkeypatch.setenv("APPDATA", str(tmp_path / "nonexistent"))
        with pytest.raises((FileNotFoundError, BuildNotFoundError)):
            get_pob_path()

    def test_env_path_not_exists(self, monkeypatch):
        monkeypatch.setenv("POB_PATH", "/nonexistent/path/that/does/not/exist")
        monkeypatch.setenv("APPDATA", "/also/nonexistent")
        with pytest.raises((FileNotFoundError, BuildNotFoundError)):
            get_pob_path()


# ── get_builds_path ──────────────────────────────────────────────────────────


class TestGetBuildsPath:
    def test_env_override(self, tmp_path, monkeypatch):
        builds_dir = tmp_path / "builds"
        builds_dir.mkdir()
        monkeypatch.setenv("POB_BUILDS_PATH", str(builds_dir))
        assert get_builds_path() == builds_dir

    def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POB_BUILDS_PATH", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        with pytest.raises((FileNotFoundError, BuildNotFoundError)):
            get_builds_path()


# ── list_build_files ─────────────────────────────────────────────────────────


class TestListBuildFiles:
    def test_finds_xml(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        files = list_build_files()
        names = [f.name for f in files]
        assert "BuildA.xml" in names
        assert "BuildB.xml" in names
        assert "SomeOther.xml" in names
        assert "notes.txt" not in names

    def test_ignores_non_xml(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        files = list_build_files()
        for f in files:
            assert f.suffix == ".xml"


# ── resolve_build_file ───────────────────────────────────────────────────────


class TestResolveBuildFile:
    def test_exact_name(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        result = resolve_build_file("BuildA.xml")
        assert result.name == "BuildA.xml"

    def test_no_extension(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        result = resolve_build_file("BuildA")
        assert result.name == "BuildA.xml"

    def test_case_insensitive(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        result = resolve_build_file("builda")
        # On Windows, filesystem is case-insensitive so exact path match works
        # On Linux, the case-insensitive glob fallback returns the actual filename
        assert result.name.lower() == "builda.xml"

    def test_not_found(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        with pytest.raises((FileNotFoundError, BuildNotFoundError)):
            resolve_build_file("DoesNotExist")


# ── Path traversal guard ────────────────────────────────────────────────────


class TestPathTraversal:
    def test_reject_dotdot(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            resolve_build_file("../etc/passwd")

    def testvalidate_build_name_rejects_dotdot(self):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name("../foo")

    def testvalidate_build_name_rejects_backslash(self):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name("foo\\bar")

    def testvalidate_build_name_accepts_normal(self):
        # Should not raise
        validate_build_name("MyBuild")
        validate_build_name("My Build With Spaces")
        validate_build_name("build-v2")

    def test_validate_name_rejects_slash(self):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name("sub/dir")

    def test_validate_name_rejects_empty(self):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name("")

    def test_validate_name_rejects_whitespace(self):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name("   ")

    def test_validate_name_rejects_invalid_chars(self):
        with pytest.raises(BuildValidationError, match="invalid characters"):
            validate_build_name("build:name")

    def test_validate_name_rejects_reserved(self):
        with pytest.raises(BuildValidationError, match="reserved word"):
            validate_build_name("CON")


# ── resolve_or_file ──────────────────────────────────────────────────────────


class TestResolveOrFile:
    def test_with_file(self, tmp_path):
        p = tmp_path / "test.xml"
        p.write_text("<xml/>")
        result = resolve_or_file("ignored", str(p))
        assert result == p

    def test_with_name(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        result = resolve_or_file("BuildA", None)
        assert result.name == "BuildA.xml"


class TestPrefixMatching:
    def test_prefix_match(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_path))
        (tmp_path / "Ele Hit Ranger.xml").write_text("<PathOfBuilding/>")
        result = resolve_build_file("Ele")
        assert result.name == "Ele Hit Ranger.xml"

    def test_ambiguous_prefix_errors(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_path))
        (tmp_path / "Ele Hit Ranger.xml").write_text("<PathOfBuilding/>")
        (tmp_path / "Ele Bow Deadeye.xml").write_text("<PathOfBuilding/>")
        with pytest.raises(BuildNotFoundError, match="Ambiguous"):
            resolve_build_file("Ele")

    def test_exact_match_preferred(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_path))
        (tmp_path / "Build.xml").write_text("<PathOfBuilding/>")
        (tmp_path / "BuildExtra.xml").write_text("<PathOfBuilding/>")
        result = resolve_build_file("Build")
        assert result.name == "Build.xml"


# ── Parametrized validation negatives ────────────────────────────────────────


class TestValidateBuildNameInvalidChars:
    @pytest.mark.parametrize("ch", list(':*?"<>|'))
    def test_each_windows_invalid_char_rejected(self, ch):
        with pytest.raises(BuildValidationError, match="invalid characters"):
            validate_build_name(f"name{ch}foo")

    @pytest.mark.parametrize(
        "reserved",
        [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM0",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT0",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ],
    )
    def test_each_reserved_name_rejected(self, reserved):
        with pytest.raises(BuildValidationError, match="reserved word"):
            validate_build_name(reserved)

    @pytest.mark.parametrize(
        "reserved_lower",
        ["con", "prn", "aux", "nul", "com1", "lpt9"],
    )
    def test_reserved_names_case_insensitive(self, reserved_lower):
        with pytest.raises(BuildValidationError, match="reserved word"):
            validate_build_name(reserved_lower)

    @pytest.mark.parametrize(
        "reserved_with_xml",
        ["CON.xml", "NUL.xml", "COM1.xml", "LPT5.xml"],
    )
    def test_reserved_names_with_xml_extension_rejected(self, reserved_with_xml):
        with pytest.raises(BuildValidationError, match="reserved word"):
            validate_build_name(reserved_with_xml)

    @pytest.mark.parametrize(
        "name",
        [
            "../foo",
            "..\\foo",
            "foo/../bar",
            "foo\\..\\bar",
            "../../etc/passwd",
            "foo/bar",
            "foo\\bar",
            "..",
        ],
    )
    def test_path_traversal_variants_rejected(self, name):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name(name)

    @pytest.mark.parametrize("name", ["", " ", "\t", "\n", "   ", " \t\n "])
    def test_empty_or_whitespace_rejected(self, name):
        with pytest.raises(BuildValidationError, match="Invalid build name"):
            validate_build_name(name)


class TestResolveBuildFileExtensions:
    def test_resolve_appends_xml_extension(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        result = resolve_build_file("BuildA")
        assert result.suffix == ".xml"

    def test_resolve_does_not_double_append_xml(self, tmp_builds_dir, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_builds_dir))
        result = resolve_build_file("BuildA.xml")
        assert result.name == "BuildA.xml"
        assert not result.name.endswith(".xml.xml")

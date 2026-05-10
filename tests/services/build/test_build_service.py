from __future__ import annotations

import pytest

from poe.exceptions import BuildNotFoundError, BuildValidationError
from poe.services.build.build_service import BuildService
from tests.conftest import MINIMAL_BUILD_XML


class TestBuildService:
    def test_load(self, build_file):
        svc = BuildService()
        _path, build = svc.load("ignored", file_path=str(build_file))
        assert build.class_name == "Witch"
        assert build.level == 90

    def test_load_not_found(self, tmp_path):
        svc = BuildService()
        with pytest.raises(BuildNotFoundError):
            svc.load("ignored", file_path=str(tmp_path / "nope.xml"))

    def test_create(self, tmp_path):
        svc = BuildService()
        result = svc.create("new_build", file_path=str(tmp_path / "new.xml"))
        assert result.status == "ok"
        assert (tmp_path / "new.xml").exists()

    def test_create_exists(self, build_file):
        svc = BuildService()
        with pytest.raises(BuildValidationError):
            svc.create("test", file_path=str(build_file))

    def test_analyze(self, builds_dir):
        svc = BuildService()
        result = svc.analyze("TestBuild")
        assert result.class_name
        assert result.class_name == "Witch"

    def test_stats_all(self, builds_dir):
        svc = BuildService()
        result = svc.stats("TestBuild")
        assert "Life" in result.stats

    def test_stats_filtered(self, builds_dir):
        svc = BuildService()
        off = svc.stats("TestBuild", category="off")
        assert "TotalDPS" in off.stats
        assert "Life" not in off.stats

    def test_stats_rejects_invalid_category(self, builds_dir):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Unknown stat category"):
            svc.stats("TestBuild", category="invalid")

    def test_stats_accepts_full_category_names(self, builds_dir):
        svc = BuildService()
        for alias in ("defence", "defense", "offence", "offense"):
            result = svc.stats("TestBuild", category=alias)
            assert result is not None

    def test_notes_get(self, build_file):
        svc = BuildService()
        result = svc.notes_get("ignored", file_path=str(build_file))
        assert result.notes is not None

    def test_notes_set(self, build_file):
        svc = BuildService()
        result = svc.notes_set("ignored", "new notes", file_path=str(build_file))
        assert result.status == "ok"
        assert result.notes == "new notes"

    def test_notes_get_strips_pob_color_codes(self, tmp_path):
        from tests.conftest import PoBXmlBuilder

        builder = PoBXmlBuilder(tmp_path)
        builder.with_class("Witch", "Necromancer", level=90)
        builder.with_notes("^xE05030Red text^7 and ^1numbered color")
        build_file = builder.write()
        svc = BuildService()
        result = svc.notes_get("ignored", file_path=str(build_file))
        assert "^x" not in result.notes
        assert "^7" not in result.notes
        assert "^1" not in result.notes
        assert "Red text" in result.notes
        assert "and" in result.notes
        assert "numbered color" in result.notes

    def test_validate(self, builds_dir):
        svc = BuildService()
        result = svc.validate("TestBuild")
        assert result.issues is not None

    def test_export(self, builds_dir, tmp_path):
        svc = BuildService()
        dest = tmp_path / "exported.xml"
        result = svc.export("TestBuild", str(dest))
        assert result.status == "ok"
        assert dest.exists()

    def test_compare(self, builds_dir):
        (builds_dir / "Build2.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        svc = BuildService()
        result = svc.compare("TestBuild", "Build2")
        assert result.stat_comparison is not None

    def test_list_builds(self, builds_dir):
        svc = BuildService()
        result = svc.list_builds()
        assert len(result) >= 1

    def test_set_main_skill_out_of_range(self, build_file):
        svc = BuildService()
        with pytest.raises(BuildValidationError):
            svc.set_main_skill("ignored", 999, file_path=str(build_file))


class TestBuildServiceCoverage:
    def test_list_builds_includes_version(self, builds_dir):
        svc = BuildService()
        result = svc.list_builds()
        matching = [b for b in result if b.name == "TestBuild"]
        assert len(matching) == 1
        assert matching[0].version == "3_0"

    def test_list_builds_with_corrupt(self, builds_env):
        (builds_env / "Bad.xml").write_text("not xml")
        svc = BuildService()
        result = svc.list_builds()
        assert any(e.name == "Bad" for e in result)

    def test_load_for_write_with_file(self, rich_build):
        svc = BuildService()
        path, build, cloned = svc.load_for_write("ignored", file_path=str(rich_build))
        assert build.class_name == "Witch"
        assert cloned is None

    def test_load_for_write_not_found(self, tmp_path):
        svc = BuildService()
        with pytest.raises(BuildNotFoundError):
            svc.load_for_write("ignored", file_path=str(tmp_path / "nope.xml"))

    def test_create_with_ascendancy(self, tmp_path):
        svc = BuildService()
        result = svc.create(
            "test",
            class_name="Witch",
            ascendancy="Necromancer",
            file_path=str(tmp_path / "new.xml"),
        )
        assert result.status == "ok"

    def test_delete_with_confirm(self, builds_env):
        claude = builds_env / "Claude"
        claude.mkdir()
        (claude / "ToDelete.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        svc = BuildService()
        result = svc.delete("ToDelete", confirm=True)
        assert result.status == "ok"

    def test_delete_not_found(self, builds_env):
        svc = BuildService()
        with pytest.raises(BuildNotFoundError):
            svc.delete("NonExistent", confirm=True)

    def test_delete_outside_claude(self, builds_env):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Claude"):
            svc.delete("TestBuild", confirm=True)

    def test_delete_no_confirm(self, builds_env):
        claude = builds_env / "Claude"
        claude.mkdir()
        (claude / "TestBuild.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="confirm"):
            svc.delete("TestBuild")

    def test_delete_file_not_exists(self, tmp_path):
        svc = BuildService()
        with pytest.raises(BuildNotFoundError):
            svc.delete("x", file_path=str(tmp_path / "nope.xml"), confirm=True)

    def test_delete_with_file_path(self, tmp_path):
        f = tmp_path / "del.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        svc = BuildService()
        result = svc.delete("x", file_path=str(f), confirm=True)
        assert result.status == "ok"

    def test_set_main_skill(self, rich_build):
        svc = BuildService()
        result = svc.set_main_skill("ignored", 1, file_path=str(rich_build))
        assert result.status == "ok"

    def test_export_not_found(self, builds_env, tmp_path):
        svc = BuildService()
        with pytest.raises(BuildNotFoundError):
            svc.export("NonExistent", str(tmp_path))

    def test_export_to_dir(self, builds_env, tmp_path):
        svc = BuildService()
        result = svc.export("TestBuild", str(tmp_path))
        assert result.status == "ok"

    def test_notes_set_with_clone(self, builds_env):
        svc = BuildService()
        result = svc.notes_set("TestBuild", "hello")
        assert result.status == "ok"
        assert hasattr(result, "cloned_from") or "cloned_from" in getattr(result, "model_extra", {})


class TestBuildRename:
    def test_rename(self, rich_build, tmp_path, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_path))
        claude_dir = tmp_path / "Claude"
        claude_dir.mkdir(exist_ok=True)
        import shutil

        shutil.copy2(rich_build, claude_dir / "ToRename.xml")
        svc = BuildService()
        result = svc.rename("ToRename", "Renamed")
        assert result.status == "ok"
        assert (claude_dir / "Renamed.xml").exists()
        assert not (claude_dir / "ToRename.xml").exists()


class TestBuildDuplicate:
    def test_duplicate(self, rich_build, tmp_path, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_path))
        svc = BuildService()
        result = svc.duplicate("ignored", "Cloned", file_path=str(rich_build))
        assert result.status == "ok"


class TestBuildSetLevel:
    def test_set_level(self, rich_build):
        svc = BuildService()
        result = svc.set_level("ignored", 95, file_path=str(rich_build))
        assert result.status == "ok"
        assert result.level == 95

    def test_set_level_invalid(self, rich_build):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="1-100"):
            svc.set_level("ignored", 200, file_path=str(rich_build))


class TestBuildSetClass:
    def test_set_class(self, rich_build):
        svc = BuildService()
        result = svc.set_class("ignored", class_name="Ranger", file_path=str(rich_build))
        assert result.status == "ok"
        assert result.class_name == "Ranger"

    def test_set_ascendancy(self, rich_build):
        svc = BuildService()
        result = svc.set_class("ignored", ascendancy="Deadeye", file_path=str(rich_build))
        assert result.status == "ok"
        assert result.ascendancy == "Deadeye"

    def test_set_invalid_class(self, rich_build):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Unknown class"):
            svc.set_class("ignored", class_name="InvalidClass", file_path=str(rich_build))

    def test_set_invalid_ascendancy(self, rich_build):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Unknown ascendancy"):
            svc.set_class("ignored", ascendancy="FakeAscendancy", file_path=str(rich_build))


class TestSetClassRequiresInput:
    def test_no_args_raises(self, rich_build):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="at least one"):
            svc.set_class("ignored", file_path=str(rich_build))


class TestBuildSetBandit:
    def test_set_bandit(self, rich_build):
        svc = BuildService()
        result = svc.set_bandit("ignored", "Alira", file_path=str(rich_build))
        assert result.status == "ok"
        assert result.bandit == "Alira"


class TestBuildSetPantheon:
    def test_set_pantheon(self, rich_build):
        svc = BuildService()
        result = svc.set_pantheon(
            "ignored",
            major="TheBrineKing",
            minor="Garukhan",
            file_path=str(rich_build),
        )
        assert result.status == "ok"


class TestBuildSummary:
    def test_summary(self, rich_build):
        svc = BuildService()
        result = svc.summary("ignored", file_path=str(rich_build))
        assert result["class"] == "Witch"
        assert result["level"] == 90
        assert "life" in result
        assert "total_dps" in result


class TestSummaryResistFallback:
    def test_missing_resists_default_to_zero(self, tmp_path):
        from tests.conftest import PoBXmlBuilder

        builder = PoBXmlBuilder(tmp_path)
        builder.with_class("Witch", "Necromancer", level=90)
        builder.with_stat("Life", 5000)
        build_file = builder.write()
        svc = BuildService()
        result = svc.summary("ignored", file_path=str(build_file))
        assert result["fire_resist"] == 0
        assert result["cold_resist"] == 0
        assert result["lightning_resist"] == 0
        assert result["chaos_resist"] == 0
        assert result["fire_resist"] is not None


class TestBuildNameValidation:
    def test_reject_windows_invalid_chars(self):
        from poe.paths import validate_build_name

        for char in ':*?"<>|':
            with pytest.raises(BuildValidationError, match="invalid characters"):
                validate_build_name(f"test{char}build")

    def test_reject_reserved_words(self):
        from poe.paths import validate_build_name

        for word in ("CON", "NUL", "PRN", "COM1", "LPT3"):
            with pytest.raises(BuildValidationError, match="reserved word"):
                validate_build_name(word)

    def test_accept_valid_names(self):
        from poe.paths import validate_build_name

        for name in ("MyBuild", "test-build", "Build_v2", "über-build"):
            validate_build_name(name)


class TestSummaryDps:
    def test_summary_includes_combined_dps(self, rich_build):
        svc = BuildService()
        result = svc.summary("ignored", file_path=str(rich_build))
        assert "combined_dps" in result
        assert result["combined_dps"] >= result["total_dps"]


class TestSetClassMismatch:
    def test_rejects_mismatched_ascendancy(self, build_file):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="does not belong to"):
            svc.set_class(
                "ignored",
                class_name="Marauder",
                ascendancy="Necromancer",
                file_path=str(build_file),
            )

    def test_accepts_matching_ascendancy(self, build_file):
        svc = BuildService()
        result = svc.set_class(
            "ignored",
            class_name="Witch",
            ascendancy="Necromancer",
            file_path=str(build_file),
        )
        assert result.class_name == "Witch"
        assert result.ascendancy == "Necromancer"


class TestSetBanditValidation:
    def test_rejects_invalid(self, build_file):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Unknown bandit"):
            svc.set_bandit("ignored", "InvalidBandit", file_path=str(build_file))

    def test_accepts_valid(self, build_file):
        svc = BuildService()
        for bandit in ("None", "Alira", "Kraityn", "Oak"):
            result = svc.set_bandit("ignored", bandit, file_path=str(build_file))
            assert result.bandit == bandit


class TestSetPantheonValidation:
    def test_rejects_invalid_major(self, build_file):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Unknown major pantheon"):
            svc.set_pantheon("ignored", major="InvalidGod", file_path=str(build_file))

    def test_rejects_invalid_minor(self, build_file):
        svc = BuildService()
        with pytest.raises(BuildValidationError, match="Unknown minor pantheon"):
            svc.set_pantheon("ignored", minor="InvalidMinor", file_path=str(build_file))

    def test_accepts_valid_major(self, build_file):
        svc = BuildService()
        result = svc.set_pantheon("ignored", major="Lunaris", file_path=str(build_file))
        assert result.pantheon_major == "Lunaris"


class TestNewAscendancies:
    def test_warden_in_ascendancy_ids(self):
        from poe.services.build.constants import ASCENDANCY_IDS

        assert "Warden" in ASCENDANCY_IDS

    def test_reliquarian_in_ascendancy_ids(self):
        from poe.services.build.constants import ASCENDANCY_IDS

        assert "Reliquarian" in ASCENDANCY_IDS

    def test_warden_is_ranger(self):
        from poe.services.build.constants import ASCENDANCY_IDS, CLASS_IDS

        assert ASCENDANCY_IDS["Warden"][0] == CLASS_IDS["Ranger"]

    def test_reliquarian_is_witch(self):
        from poe.services.build.constants import ASCENDANCY_IDS, CLASS_IDS

        assert ASCENDANCY_IDS["Reliquarian"][0] == CLASS_IDS["Witch"]


class TestUnicodeBuildNames:
    def test_unicode_name(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POB_BUILDS_PATH", str(tmp_path))
        claude_dir = tmp_path / "Claude"
        claude_dir.mkdir()
        svc = BuildService()
        result = svc.create("über-build", file_path=str(claude_dir / "über-build.xml"))
        assert result.status == "ok"


class TestBuildNameValidationCharByChar:
    @pytest.mark.parametrize("char", ["<", ">", ":", '"', "|", "?", "*"])
    def test_each_windows_invalid_char_rejected(self, char):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError):
            validate_build_name(f"build{char}name")

    @pytest.mark.parametrize(
        "name",
        [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
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
    def test_each_reserved_name_rejected(self, name):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError, match="reserved"):
            validate_build_name(name)

    @pytest.mark.parametrize(
        "name",
        ["con", "Con", "cOn", "nul", "com1", "lpt9"],
    )
    def test_reserved_names_case_insensitive(self, name):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError, match="reserved"):
            validate_build_name(name)

    def test_reserved_with_xml_extension_still_rejected(self):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError, match="reserved"):
            validate_build_name("CON.xml")

    @pytest.mark.parametrize(
        "name",
        ["..", "../foo", "foo/..", "..\\foo"],
    )
    def test_path_traversal_rejected(self, name):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError):
            validate_build_name(name)

    @pytest.mark.parametrize(
        "name",
        ["sub/dir", "/abs", "a/b/c"],
    )
    def test_forward_slash_rejected(self, name):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError):
            validate_build_name(name)

    @pytest.mark.parametrize(
        "name",
        ["sub\\dir", "\\abs", "a\\b\\c"],
    )
    def test_backslash_rejected(self, name):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError):
            validate_build_name(name)

    @pytest.mark.parametrize("name", ["", "   ", "\t", "\n"])
    def test_empty_or_whitespace_rejected(self, name):
        from poe.paths import validate_build_name

        with pytest.raises(BuildValidationError):
            validate_build_name(name)

    @pytest.mark.parametrize(
        "name",
        ["MyBuild", "My Build With Spaces", "build-v2", "build_v2", "über-build", "build123"],
    )
    def test_valid_names_accepted(self, name):
        from poe.paths import validate_build_name

        validate_build_name(name)

    def test_reserved_substring_allowed(self):
        from poe.paths import validate_build_name

        validate_build_name("CONqueror")
        validate_build_name("PRNter")
        validate_build_name("MyAUXBuild")

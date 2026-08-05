from __future__ import annotations

import pytest

from poe.exceptions import BuildValidationError
from poe.models.build import Gem, GemGroup
from poe.services.build.gems_service import GemsService
from tests.conftest import PoBXmlBuilder


class TestGemsService:
    def test_list_sets(self, builds_dir):
        svc = GemsService()
        result = svc.list_sets("TestBuild")
        assert result.sets is not None

    def test_list_gems(self, builds_dir):
        svc = GemsService()
        result = svc.list_gems("TestBuild")
        assert isinstance(result, list)

    def test_add_group(self, build_file):
        svc = GemsService()
        result = svc.add_group("ignored", gems=["Fireball"], file_path=str(build_file))
        assert result.status == "ok"

    def test_remove_group_out_of_range(self, build_file):
        svc = GemsService()
        with pytest.raises(BuildValidationError):
            svc.remove_group("ignored", 999, file_path=str(build_file))


class TestGemsServiceAdditional:
    def test_edit_group_swap(self, rich_build):
        svc = GemsService()
        r = svc.edit_group(
            "ignored",
            0,
            swap=["Fireball,Ice Nova"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"
        assert "Ice Nova" in r.gems

    def test_edit_group_level(self, rich_build):
        svc = GemsService()
        r = svc.edit_group(
            "ignored",
            0,
            set_level=["Fireball,21"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_edit_group_quality(self, rich_build):
        svc = GemsService()
        r = svc.edit_group(
            "ignored",
            0,
            set_quality=["Fireball,23"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_edit_group_toggle(self, rich_build):
        svc = GemsService()
        r = svc.edit_group(
            "ignored",
            0,
            toggle=["Fireball"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_edit_group_set_slot(self, rich_build):
        svc = GemsService()
        r = svc.edit_group(
            "ignored",
            0,
            set_slot="Helmet",
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_edit_group_gem_not_found(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.edit_group(
                "ignored",
                0,
                swap=["NoSuchGem,Other"],
                file_path=str(rich_build),
            )

    def test_edit_group_invalid_index(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.edit_group("ignored", 99, file_path=str(rich_build))

    def test_set_active_invalid(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.set_active("ignored", 99, file_path=str(rich_build))

    def test_set_active(self, rich_build):
        svc = GemsService()
        r = svc.set_active("ignored", 1, file_path=str(rich_build))
        assert r.status == "ok"


class TestGemsServiceCoverage:
    def test_list_gems_with_quality_id(self, tmp_path, monkeypatch):
        builds = tmp_path / "gem_builds"
        builds.mkdir()
        builder = PoBXmlBuilder(builds)
        builder.with_class("Witch")
        builder._build.skill_groups.append(
            GemGroup(
                gems=[
                    Gem(
                        name_spec="Fireball",
                        quality_id="Anomalous",
                        skill_part="1",
                        skill_minion="SRS",
                    ),
                ]
            )
        )
        builder.write("GemsTest.xml")
        monkeypatch.setenv("POB_BUILDS_PATH", str(builds))
        svc = GemsService()
        result = svc.list_gems("GemsTest")
        gem = result[0].gems[0]
        assert gem.quality_id == "Anomalous"
        assert gem.skill_part == "1"
        assert gem.skill_minion == "SRS"


class TestEditGroupQualityId:
    def test_set_quality_id(self, rich_build):
        svc = GemsService()
        r = svc.edit_group(
            "ignored",
            0,
            set_quality_id=["Fireball,Anomalous"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"


class TestGemIndividualOps:
    def test_add_gem_to_group(self, rich_build):
        svc = GemsService()
        r = svc.add_gem_to_group(
            "ignored",
            0,
            gem_name="Added Cold Damage Support",
            file_path=str(rich_build),
        )
        assert r.status == "ok"
        assert "Added Cold Damage Support" in r.gems

    def test_add_gem_invalid_group(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.add_gem_to_group(
                "ignored",
                99,
                gem_name="Fireball",
                file_path=str(rich_build),
            )

    def test_remove_gem_from_group(self, rich_build):
        svc = GemsService()
        r = svc.remove_gem_from_group(
            "ignored",
            0,
            gem_name="Spell Echo Support",
            file_path=str(rich_build),
        )
        assert r.status == "ok"
        assert "Spell Echo Support" not in r.gems

    def test_remove_gem_not_found(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.remove_gem_from_group(
                "ignored",
                0,
                gem_name="Nonexistent Gem",
                file_path=str(rich_build),
            )

    def test_add_group_per_gem_config(self, rich_build):
        svc = GemsService()
        r = svc.add_group(
            "ignored",
            gems=[
                {"name": "Fireball", "level": 21, "quality": 23},
                {"name": "Spell Echo Support", "level": 20, "quality": 0},
            ],
            file_path=str(rich_build),
        )
        assert r.status == "ok"
        assert len(r.gems) == 2


class TestGemSets:
    def test_add_set(self, rich_build):
        svc = GemsService()
        r = svc.add_set("ignored", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_set(self, rich_build):
        svc = GemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        r = svc.remove_set("ignored", 2, file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_last_set(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="last"):
            svc.remove_set("ignored", 1, file_path=str(rich_build))

    def test_remove_set_not_found(self, rich_build):
        svc = GemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        with pytest.raises(BuildValidationError, match="not found"):
            svc.remove_set("ignored", 99, file_path=str(rich_build))


class TestEmptySkillGroups:
    def test_add_empty_group(self, rich_build):
        svc = GemsService()
        r = svc.add_group("ignored", gems=[], file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_all_gems_from_group(self, rich_build):
        svc = GemsService()
        svc.remove_gem_from_group(
            "ignored",
            0,
            gem_name="Fireball",
            file_path=str(rich_build),
        )
        r = svc.remove_gem_from_group(
            "ignored",
            0,
            gem_name="Spell Echo Support",
            file_path=str(rich_build),
        )
        assert r.gems == []


class TestAddGroupInvariants:
    def test_add_group_index_matches_position(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = GemsService()
        result = svc.add_group(
            "ignored",
            gems=["Fireball"],
            slot="Gloves",
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert build.skill_groups[result.index].slot == "Gloves"
        assert build.skill_groups[result.index].gems[0].name_spec == "Fireball"

    def test_remove_group_shifts_indices(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = GemsService()
        before = svc.add_group(
            "ignored",
            gems=["Frostbolt"],
            slot="Helmet",
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        before_count = len(build.skill_groups)
        result = svc.remove_group("ignored", before.index, file_path=str(rich_build))
        assert result.status == "ok"
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        assert len(after.skill_groups) == before_count - 1


class TestEditGroupGemNotFoundCases:
    def test_set_level_gem_not_found(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.edit_group(
                "ignored",
                0,
                set_level=["NoSuchGem,21"],
                file_path=str(rich_build),
            )

    def test_set_quality_gem_not_found(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.edit_group(
                "ignored",
                0,
                set_quality=["NoSuchGem,20"],
                file_path=str(rich_build),
            )

    def test_set_quality_id_gem_not_found(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.edit_group(
                "ignored",
                0,
                set_quality_id=["NoSuchGem,Anomalous"],
                file_path=str(rich_build),
            )

    def test_toggle_gem_not_found(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.edit_group(
                "ignored",
                0,
                toggle=["NoSuchGem"],
                file_path=str(rich_build),
            )


class TestAddGemBoundsAndInvariants:
    def test_remove_gem_invalid_group_index_negative(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.remove_gem_from_group(
                "ignored",
                -1,
                gem_name="Fireball",
                file_path=str(rich_build),
            )

    def test_remove_group_invalid_index_negative(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.remove_group("ignored", -1, file_path=str(rich_build))

    def test_edit_group_invalid_index_negative(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.edit_group("ignored", -1, file_path=str(rich_build))

    def test_add_gem_invalid_index_negative(self, rich_build):
        svc = GemsService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.add_gem_to_group(
                "ignored",
                -1,
                gem_name="Fireball",
                file_path=str(rich_build),
            )


class TestGemFindCaseInsensitive:
    def test_swap_uses_case_insensitive_lookup(self, rich_build):
        svc = GemsService()
        result = svc.edit_group(
            "ignored",
            0,
            swap=["fireball,Ice Nova"],
            file_path=str(rich_build),
        )
        assert "Ice Nova" in result.gems

    def test_toggle_case_insensitive(self, rich_build):
        svc = GemsService()
        result = svc.edit_group(
            "ignored",
            0,
            toggle=["FIREBALL"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"


class TestSkillSetMutations:
    def test_add_set_unique_id(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = GemsService()
        result = svc.add_set("ignored", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert result.new_set_id in build.skill_set_ids
        assert len(build.skill_set_ids) == len(set(build.skill_set_ids))

    def test_remove_set_switches_active(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = GemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        svc.set_active("ignored", 2, file_path=str(rich_build))
        svc.remove_set("ignored", 2, file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert build.active_skill_set in build.skill_set_ids


class TestEditGroupSwapClearsIds:
    def test_swap_clears_skill_id(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = GemsService()
        _, build_before = BuildService().load("ignored", file_path=str(rich_build))
        first_gem = build_before.skill_groups[0].gems[0]
        first_gem.skill_id = "some_id"
        first_gem.gem_id = "another_id"
        from poe.services.build.xml.writer import write_build_file

        write_build_file(build_before, rich_build)
        svc.edit_group(
            "ignored",
            0,
            swap=["Fireball,Ice Nova"],
            file_path=str(rich_build),
        )
        _, build_after = BuildService().load("ignored", file_path=str(rich_build))
        replaced = build_after.skill_groups[0].gems[0]
        assert replaced.name_spec == "Ice Nova"
        assert replaced.skill_id == ""
        assert replaced.gem_id == ""

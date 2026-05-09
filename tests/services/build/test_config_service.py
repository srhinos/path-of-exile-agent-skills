from __future__ import annotations

import pytest

from poe.exceptions import BuildValidationError
from poe.services.build.config_service import ConfigService
from tests.conftest import PoBXmlBuilder


class TestConfigService:
    def test_get(self, builds_dir):
        svc = ConfigService()
        result = svc.get("TestBuild")
        assert result.inputs is not None

    def test_set_boolean(self, build_file):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            boolean=["useCharges=true"],
            file_path=str(build_file),
        )
        assert result.status == "ok"

    def test_set_invalid_format(self, build_file):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="key=value"):
            svc.set(
                "ignored",
                boolean=["no_equals_sign"],
                file_path=str(build_file),
            )


class TestConfigServiceCoverage:
    def test_set_number(self, rich_build):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            number=["enemyLevel=84"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_set_string(self, rich_build):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            string=["boss=Shaper"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_set_remove(self, rich_build):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            remove=["useFrenzyCharges"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_set_invalid_boolean(self, rich_build):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="boolean"):
            svc.set(
                "ignored",
                boolean=["key=maybe"],
                file_path=str(rich_build),
            )

    def test_set_invalid_number(self, rich_build):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="number"):
            svc.set(
                "ignored",
                number=["key=notanumber"],
                file_path=str(rich_build),
            )

    def test_set_creates_config_if_missing(self, tmp_path):
        builder = PoBXmlBuilder(tmp_path)
        builder.with_class("Witch")
        path = builder.write("noconfig.xml")
        from poe.services.build.xml.parser import parse_build_file
        from poe.services.build.xml.writer import write_build_file

        b = parse_build_file(path)
        b.config_sets = []
        write_build_file(b, path)
        svc = ConfigService()
        result = svc.set("ignored", boolean=["test=true"], file_path=str(path))
        assert result.status == "ok"

    def test_get_no_config(self, tmp_path, monkeypatch):
        builds = tmp_path / "blds"
        builds.mkdir()
        builder = PoBXmlBuilder(builds)
        builder.with_class("Witch")
        path = builder.write("NoConfig.xml")
        from poe.services.build.xml.parser import parse_build_file
        from poe.services.build.xml.writer import write_build_file

        b = parse_build_file(path)
        b.config_sets = []
        write_build_file(b, path)
        monkeypatch.setenv("POB_BUILDS_PATH", str(builds))
        svc = ConfigService()
        with pytest.raises(BuildValidationError):
            svc.get("NoConfig")


class TestConfigOptions:
    def test_list_options_all(self):
        svc = ConfigService()
        options = svc.list_options()
        assert len(options) > 0
        assert all("key" in o and "type" in o and "description" in o for o in options)

    def test_list_options_filtered(self):
        svc = ConfigService()
        options = svc.list_options(query="charges")
        assert len(options) >= 1
        assert any("Charge" in o["description"] for o in options)

    def test_list_options_no_match(self):
        svc = ConfigService()
        options = svc.list_options(query="zzzzzzz")
        assert options == []


class TestConfigSetManagement:
    def test_list_sets(self, builds_dir):
        svc = ConfigService()
        sets = svc.list_sets("TestBuild")
        assert len(sets) >= 1
        assert sets[0]["active"] is True

    def test_add_set(self, rich_build):
        svc = ConfigService()
        r = svc.add_set("ignored", title="Boss Config", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_set(self, rich_build):
        svc = ConfigService()
        svc.add_set("ignored", title="Temp", file_path=str(rich_build))
        r = svc.remove_set("ignored", "2", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_last_set(self, rich_build):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="last"):
            svc.remove_set("ignored", "1", file_path=str(rich_build))

    def test_remove_set_not_found(self, rich_build):
        svc = ConfigService()
        svc.add_set("ignored", title="Extra", file_path=str(rich_build))
        with pytest.raises(BuildValidationError, match="not found"):
            svc.remove_set("ignored", "99", file_path=str(rich_build))

    def test_switch_set(self, rich_build):
        svc = ConfigService()
        svc.add_set("ignored", title="Alt", file_path=str(rich_build))
        r = svc.switch_set("ignored", "2", file_path=str(rich_build))
        assert r.status == "ok"

    def test_switch_set_not_found(self, rich_build):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="not found"):
            svc.switch_set("ignored", "99", file_path=str(rich_build))


class TestConfigPreset:
    def test_apply_preset(self, rich_build):
        svc = ConfigService()
        r = svc.apply_preset("ignored", "mapping", file_path=str(rich_build))
        assert r.status == "ok"
        assert r.preset == "mapping"

    def test_apply_preset_boss(self, rich_build):
        svc = ConfigService()
        r = svc.apply_preset("ignored", "boss", file_path=str(rich_build))
        assert r.status == "ok"

    def test_apply_invalid_preset(self, rich_build):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="Unknown preset"):
            svc.apply_preset("ignored", "nonexistent", file_path=str(rich_build))


class TestMultipleConfigSets:
    def test_multiple_config_sets(self, rich_build):
        svc = ConfigService()
        svc.add_set("ignored", title="Boss", file_path=str(rich_build))
        svc.add_set("ignored", title="Mapping", file_path=str(rich_build))
        sets = svc.list_sets("ignored", file_path=str(rich_build))
        assert len(sets) == 3

    def test_switch_between_sets(self, rich_build):
        svc = ConfigService()
        svc.add_set("ignored", title="Alt", file_path=str(rich_build))
        svc.switch_set("ignored", "2", file_path=str(rich_build))
        sets = svc.list_sets("ignored", file_path=str(rich_build))
        active = [s for s in sets if s["active"]]
        assert active[0]["id"] == "2"


class TestConfigSetParametrized:
    @pytest.mark.parametrize("value", ["true", "false", "True", "False", "TRUE", "FALSE"])
    def test_boolean_case_insensitive(self, rich_build, value):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            boolean=[f"buffFortify={value}"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    @pytest.mark.parametrize("value", ["yes", "no", "1", "0", "on", "off", ""])
    def test_boolean_invalid_value(self, rich_build, value):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="boolean"):
            svc.set(
                "ignored",
                boolean=[f"key={value}"],
                file_path=str(rich_build),
            )

    @pytest.mark.parametrize("value", ["84", "84.0", "0", "-5", "1e3", "3.14"])
    def test_number_parses(self, rich_build, value):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            number=[f"enemyLevel={value}"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    @pytest.mark.parametrize("value", ["abc", "12abc", "", "  "])
    def test_number_invalid(self, rich_build, value):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="number"):
            svc.set(
                "ignored",
                number=[f"enemyLevel={value}"],
                file_path=str(rich_build),
            )


class TestApplyPresetCoverage:
    @pytest.mark.parametrize("preset", ["mapping", "boss", "sirus", "shaper"])
    def test_each_preset_applies(self, rich_build, preset):
        svc = ConfigService()
        result = svc.apply_preset("ignored", preset, file_path=str(rich_build))
        assert result.status == "ok"
        assert result.preset == preset


class TestSetRemove:
    def test_remove_unknown_key_is_silent(self, rich_build):
        svc = ConfigService()
        result = svc.set(
            "ignored",
            remove=["totally_not_a_key"],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_remove_actually_removes_existing(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ConfigService()
        svc.set(
            "ignored",
            boolean=["temp_key=true"],
            file_path=str(rich_build),
        )
        svc.set(
            "ignored",
            remove=["temp_key"],
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        cfg = build.get_active_config()
        assert all(inp.name != "temp_key" for inp in cfg.inputs)


class TestSwitchSetInvariant:
    def test_switch_to_same_set(self, rich_build):
        svc = ConfigService()
        result = svc.switch_set("ignored", "1", file_path=str(rich_build))
        assert result.status == "ok"

    def test_remove_active_set_switches_active(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ConfigService()
        svc.add_set("ignored", title="Alt", file_path=str(rich_build))
        svc.switch_set("ignored", "2", file_path=str(rich_build))
        svc.remove_set("ignored", "2", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        existing = {cs.id for cs in build.config_sets}
        assert build.active_config_set in existing


class TestAddSetInvariant:
    def test_added_config_set_has_unique_id(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ConfigService()
        svc.add_set("ignored", title="A", file_path=str(rich_build))
        svc.add_set("ignored", title="B", file_path=str(rich_build))
        svc.add_set("ignored", title="C", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        ids = [cs.id for cs in build.config_sets]
        assert len(ids) == len(set(ids))


class TestSetParseKvFormatErrors:
    @pytest.mark.parametrize("kv", ["nokey", "key", " "])
    def test_invalid_format_raises(self, rich_build, kv):
        svc = ConfigService()
        with pytest.raises(BuildValidationError, match="key=value"):
            svc.set(
                "ignored",
                boolean=[kv],
                file_path=str(rich_build),
            )


class TestLegacyConfig:
    def test_legacy_config_without_configset(self, tmp_path):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding>
    <Build level="1" className="Scion" ascendClassName=""
           bandit="None" viewMode="TREE" targetVersion="3_0"
           mainSocketGroup="1" pantheonMajorGod="" pantheonMinorGod=""/>
    <Tree activeSpec="1">
        <Spec treeVersion="3_25" classId="0" ascendClassId="0" nodes="">
            <URL/>
        </Spec>
    </Tree>
    <Skills activeSkillSet="1">
        <SkillSet id="1"/>
    </Skills>
    <Items activeItemSet="1">
        <ItemSet id="1"/>
    </Items>
    <Config>
        <Input name="useFrenzyCharges" boolean="true"/>
        <Input name="enemyLevel" number="84"/>
    </Config>
    <Notes/>
</PathOfBuilding>"""
        path = tmp_path / "legacy.xml"
        path.write_text(xml, encoding="utf-8")
        from poe.services.build.xml.parser import parse_build_file

        build = parse_build_file(path)
        assert len(build.config_sets) == 1
        assert len(build.config_sets[0].inputs) == 2

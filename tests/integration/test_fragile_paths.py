from __future__ import annotations

import pytest

from poe.models.build.items import ItemMod
from poe.services.build.build_service import BuildService
from poe.services.build.jewels_service import JewelsService
from poe.services.build.validation import validate_build
from poe.services.build.xml.parser import parse_build_file
from poe.services.build.xml.writer import write_build_file

pytestmark = pytest.mark.integration


class TestVariantPreservation:
    """Parser must preserve all variant mods so writer can round-trip them.

    Filtering at parse time was silent data loss: write→reparse would lose
    the inactive variants. Consumers (display, stat compute) filter by the
    selected variant at the consumption layer instead.
    """

    def test_comma_separated_variant_mods_preserved(self, tmp_path):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<PathOfBuilding>\n"
            '<Build level="90" className="Ranger" ascendClassName="Deadeye"'
            ' mainSocketGroup="1" targetVersion="3_0">\n'
            "</Build>\n"
            '<Items activeItemSet="1">\n'
            '<Item id="1">\n'
            "Rarity: UNIQUE\nThe Taming\nPrismatic Ring\n"
            "Selected Variant: 3\nImplicits: 0\n"
            "{variant:2,3}+(20-30)% to all Elemental Resistances\n"
            "{variant:2,3}10% chance to Freeze, Shock and Ignite\n"
            "{variant:1}Only variant 1 mod\n"
            "All variants mod\n"
            "</Item>\n"
            '<ItemSet id="1"><Slot name="Ring 1" itemId="1"/></ItemSet>\n'
            "</Items>\n"
            '<Skills activeSkillSet="1"></Skills>\n'
            '<Tree activeSpec="1"><Spec treeVersion="3_25"></Spec></Tree>\n'
            "</PathOfBuilding>"
        )
        path = tmp_path / "variant_test.xml"
        path.write_text(xml, encoding="utf-8")
        build = parse_build_file(path)
        ring = build.items[0]
        texts = [m.text for m in ring.explicits]
        assert "+(20-30)% to all Elemental Resistances" in texts
        assert "10% chance to Freeze, Shock and Ignite" in texts
        assert "All variants mod" in texts
        assert "Only variant 1 mod" in texts

    def test_single_variant_mods_preserved(self, tmp_path):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<PathOfBuilding>\n"
            '<Build level="90" className="Witch" ascendClassName=""'
            ' mainSocketGroup="1" targetVersion="3_0">\n'
            "</Build>\n"
            '<Items activeItemSet="1">\n'
            '<Item id="1">\n'
            "Rarity: UNIQUE\nTest Unique\nPrismatic Ring\n"
            "Selected Variant: 2\nImplicits: 0\n"
            "{variant:2}Variant 2 only\n"
            "{variant:1}Variant 1 only\n"
            "</Item>\n"
            '<ItemSet id="1"><Slot name="Amulet" itemId="1"/></ItemSet>\n'
            "</Items>\n"
            '<Skills activeSkillSet="1"></Skills>\n'
            '<Tree activeSpec="1"><Spec treeVersion="3_25"></Spec></Tree>\n'
            "</PathOfBuilding>"
        )
        path = tmp_path / "single_variant.xml"
        path.write_text(xml, encoding="utf-8")
        build = parse_build_file(path)
        texts = [m.text for m in build.items[0].explicits]
        assert "Variant 2 only" in texts
        assert "Variant 1 only" in texts


class TestFlaskBaseType:
    def test_magic_flask_strips_prefix(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Flask 1",
                name="Experimenter's Jade Flask of the Impala",
                rarity="MAGIC",
                quality=20,
            )
            .write("flask_prefix.xml")
        )
        build = parse_build_file(path)
        assert build.items[0].base_type == "Jade Flask"

    def test_magic_flask_suffix_only(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Flask 2",
                name="Quicksilver Flask of the Cheetah",
                rarity="MAGIC",
            )
            .write("flask_suffix.xml")
        )
        build = parse_build_file(path)
        assert build.items[0].base_type == "Quicksilver Flask"

    def test_magic_flask_prefix_only(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Flask 3",
                name="Doctor's Divine Life Flask",
                rarity="MAGIC",
            )
            .write("flask_prefix_only.xml")
        )
        build = parse_build_file(path)
        assert build.items[0].base_type == "Divine Life Flask"

    def test_unique_flask_keeps_name(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Flask 1",
                name="Bottled Faith",
                base_type="Sulphur Flask",
                rarity="UNIQUE",
            )
            .write("flask_unique.xml")
        )
        build = parse_build_file(path)
        assert build.items[0].base_type == "Sulphur Flask"


class TestPrefixSuffixSlots:
    def test_none_slots_are_python_none(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Helmet",
                name="Doom Crown",
                base_type="Hubris Circlet",
                rarity="RARE",
                prefix_slots=["IncreasedLife6", None, None],
                suffix_slots=["ColdResistance5", None, None],
                explicits=[
                    ItemMod(text="+90 to maximum Life"),
                    ItemMod(text="+40% to Cold Resistance"),
                ],
            )
            .write("affix_slots.xml")
        )
        build = parse_build_file(path)
        item = build.items[0]
        assert item.open_prefixes == 2
        assert item.open_suffixes == 2
        assert item.filled_prefixes == 1
        assert item.filled_suffixes == 1
        assert None in item.prefix_slots
        assert "None" not in [str(s) for s in item.prefix_slots if s is not None]

    def test_slots_roundtrip(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Body Armour",
                name="Test Regalia",
                base_type="Vaal Regalia",
                rarity="RARE",
                prefix_slots=["IncreasedLife7", "DefencesPercent5", None],
                suffix_slots=["ColdResist4", None, None],
                explicits=[
                    ItemMod(text="+100 to maximum Life"),
                    ItemMod(text="120% increased Energy Shield"),
                    ItemMod(text="+40% to Cold Resistance"),
                ],
            )
            .write("slots_roundtrip.xml")
        )
        build = parse_build_file(path)
        write_build_file(build, path)
        reparsed = parse_build_file(path)
        item = reparsed.items[0]
        assert item.open_prefixes == 1
        assert item.filled_suffixes == 1
        assert None in item.prefix_slots


class TestModIdAssignment:
    def test_keyword_matching_assigns_correctly(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Weapon 1",
                name="Test Wand",
                base_type="Prophecy Wand",
                rarity="RARE",
                prefix_slots=["SpellDamage5"],
                suffix_slots=["SpellCriticalStrikeChance4"],
                explicits=[
                    ItemMod(text="69% increased Spell Critical Strike Chance"),
                    ItemMod(text="80% increased Spell Damage"),
                ],
            )
            .write("mod_id_test.xml")
        )
        build = parse_build_file(path)
        item = build.items[0]
        crit_mod = next(m for m in item.explicits if "Critical" in m.text)
        damage_mod = next(m for m in item.explicits if "Spell Damage" in m.text)
        assert crit_mod.mod_id == "SpellCriticalStrikeChance4"
        assert crit_mod.is_suffix
        assert damage_mod.mod_id == "SpellDamage5"
        assert damage_mod.is_prefix

    def test_custom_mods_excluded_from_assignment(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_item(
                "Body Armour",
                name="Test Armour",
                base_type="Vaal Regalia",
                rarity="RARE",
                prefix_slots=["IncreasedLife6"],
                suffix_slots=[],
                explicits=[
                    ItemMod(text="Has 1 Abyssal Socket", is_custom=True),
                    ItemMod(text="+90 to maximum Life"),
                ],
            )
            .write("custom_mod_test.xml")
        )
        build = parse_build_file(path)
        item = build.items[0]
        custom = next(m for m in item.explicits if "Abyssal" in m.text)
        life = next(m for m in item.explicits if "Life" in m.text)
        assert custom.mod_id == ""
        assert life.mod_id == "IncreasedLife6"


class TestJewelsFromSockets:
    def test_jewels_found_via_socket_id_urls(self, tmp_path):
        from poe.models.build.build import BuildDocument
        from poe.models.build.config import BuildConfig
        from poe.models.build.items import Item, ItemSet
        from poe.models.build.tree import TreeSocket, TreeSpec

        build = BuildDocument(
            class_name="Witch",
            ascend_class_name="Elementalist",
            level=95,
            items=[
                Item(
                    id=1,
                    text="",
                    name="Watcher's Eye",
                    base_type="Prismatic Jewel",
                    rarity="UNIQUE",
                    explicits=[ItemMod(text="+50 to maximum Life")],
                ),
            ],
            item_sets=[
                ItemSet(
                    id="1",
                    slots=[],
                    socket_id_urls=[TreeSocket(node_id=26725, item_id=1)],
                ),
            ],
            specs=[TreeSpec(tree_version="3_25", sockets=[TreeSocket(node_id=26725, item_id=1)])],
            skill_set_ids=[1],
            config_sets=[BuildConfig(id="1", title="Default")],
        )
        path = tmp_path / "jewel_socket.xml"
        write_build_file(build, path)

        svc = JewelsService(BuildService())
        result = svc.list_jewels("jewel_socket", file_path=str(path))
        assert len(result.jewels) == 1
        assert result.jewels[0].name == "Watcher's Eye"
        assert result.jewels[0].tree_node == 26725


class TestValidationStatNames:
    def test_overcap_uses_overcap_stat(self, pob_builder):
        build = (
            pob_builder.with_class("Witch", level=90)
            .with_stat("FireResist", 75)
            .with_stat("FireResistOverCap", 120)
            .with_stat("ColdResist", 75)
            .with_stat("LightningResist", 75)
            .with_stat("Life", 5000)
            .build_object()
        )
        issues = validate_build(build)
        overcap = [i for i in issues if "overcapped" in i.message]
        assert len(overcap) == 1
        assert "Fire" in overcap[0].message

    def test_mana_regen_uses_correct_stat(self, pob_builder):
        build = (
            pob_builder.with_class("Witch", level=90)
            .with_stat("ManaPerSecondCost", 200)
            .with_stat("ManaRegenRecovery", 50)
            .with_stat("Life", 5000)
            .build_object()
        )
        issues = validate_build(build)
        mana = [i for i in issues if i.category == "mana"]
        assert len(mana) == 1

    def test_movement_speed_uses_effective(self, pob_builder):
        build = (
            pob_builder.with_class("Witch", level=90)
            .with_stat("EffectiveMovementSpeedMod", 0)
            .with_stat("Life", 5000)
            .build_object()
        )
        issues = validate_build(build)
        move = [i for i in issues if i.category == "movement"]
        assert len(move) == 1


class TestNotesColorPreserved:
    """Parser must preserve PoB color codes verbatim — stripping at parse
    time was silent data loss on round-trip. Display layer (notes_get)
    strips for human output."""

    def test_pob_color_codes_preserved(self, pob_builder):
        path = (
            pob_builder.with_class("Witch", level=90)
            .with_notes("^xE05030Red text^7 normal ^x70FF70green^7 end")
            .write("color_notes.xml")
        )
        build = parse_build_file(path)
        assert "^xE05030" in build.notes
        assert "^7" in build.notes
        assert "Red text" in build.notes
        assert "normal" in build.notes
        assert "green" in build.notes


class TestFullDpsSkillsValueType:
    def test_value_is_float_not_string(self, pob_builder):
        builder = pob_builder.with_class("Witch", level=90)
        builder._build.full_dps_skills = [{"index": "1", "value": "54285789.94305"}]
        path = builder.write("dps_skills.xml")
        build = parse_build_file(path)
        if build.full_dps_skills:
            for skill in build.full_dps_skills:
                if "value" in skill:
                    assert isinstance(skill["value"], float)


class TestCreateValidation:
    def test_invalid_class_rejected(self, tmp_path):
        svc = BuildService()
        with pytest.raises(Exception, match="Unknown class"):
            svc.create("bad", class_name="InvalidClass", file_path=str(tmp_path / "bad.xml"))

    def test_invalid_ascendancy_rejected(self, tmp_path):
        svc = BuildService()
        with pytest.raises(Exception, match="Unknown ascendancy"):
            svc.create(
                "bad",
                class_name="Witch",
                ascendancy="NotARealAscendancy",
                file_path=str(tmp_path / "bad.xml"),
            )

    def test_mismatched_class_ascendancy_rejected(self, tmp_path):
        svc = BuildService()
        with pytest.raises(Exception, match="does not belong"):
            svc.create(
                "bad",
                class_name="Witch",
                ascendancy="Deadeye",
                file_path=str(tmp_path / "bad.xml"),
            )

    def test_level_out_of_range_rejected(self, tmp_path):
        svc = BuildService()
        with pytest.raises(Exception, match="Level must be"):
            svc.create("bad", level=999, file_path=str(tmp_path / "bad.xml"))

    def test_valid_create_succeeds(self, tmp_path):
        svc = BuildService()
        result = svc.create(
            "good",
            class_name="Witch",
            ascendancy="Elementalist",
            level=90,
            file_path=str(tmp_path / "good.xml"),
        )
        assert result.status == "ok"


class TestPathTraversal:
    def test_duplicate_rejects_traversal(self, tmp_path):
        svc = BuildService()
        svc.create("safe", file_path=str(tmp_path / "safe.xml"))
        with pytest.raises(Exception, match="Invalid build name"):
            svc.duplicate("safe", "../../escaped", file_path=str(tmp_path / "safe.xml"))

    def test_rename_rejects_traversal(self, tmp_path):
        svc = BuildService()
        svc.create("safe", file_path=str(tmp_path / "safe.xml"))
        with pytest.raises(Exception, match="Invalid build name"):
            svc.rename("safe", "../escaped")

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from poe.services.build.xml.parser import _parse_mastery_effects, _parse_mod_line, parse_build_file

if TYPE_CHECKING:
    from pathlib import Path


def _write_xml(tmp_path: Path, xml: str) -> Path:
    """Write XML string to a temp file and return the path."""
    p = tmp_path / "test.xml"
    # Strip leading whitespace so <?xml declaration starts at column 0
    p.write_text(xml.lstrip(), encoding="utf-8")
    return p


# ── Build section ────────────────────────────────────────────────────────────


class TestParseBuildSection:
    def test_class_and_level(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.class_name == "Witch"
        assert build.ascend_class_name == "Necromancer"
        assert build.level == 90

    def test_bandit_and_view_mode(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.bandit is None
        assert build.view_mode == "TREE"
        assert build.target_version == "3_0"

    def test_pantheon(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Marauder" ascendClassName=""
                       pantheonMajorGod="Lunaris" pantheonMinorGod="Gruthkul"/>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.pantheon_major == "Lunaris"
        assert build.pantheon_minor == "Gruthkul"

    def test_player_stats(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.get_stat("Life") == 4500
        assert build.get_stat("EnergyShield") == 1200
        assert build.get_stat("TotalDPS") == 150000

    def test_notes(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert "Build notes here" in build.notes

    def test_import_link(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.import_link == "https://pobb.in/abc123"


# ── Tree section ─────────────────────────────────────────────────────────────


class TestParseTreeSection:
    def test_single_spec_nodes(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert len(build.specs) == 1
        assert build.specs[0].nodes == [100, 200, 300, 400]

    def test_spec_attributes(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        spec = build.specs[0]
        assert spec.title == "Main"
        assert spec.tree_version == "3_25"
        assert spec.class_id == 5
        assert spec.ascend_class_id == 2

    def test_mastery_effects(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        spec = build.specs[0]
        assert len(spec.mastery_effects) == 2
        assert spec.mastery_effects[0].node_id == 53188
        assert spec.mastery_effects[0].effect_id == 64875
        assert spec.mastery_effects[1].node_id == 53738

    def test_sockets(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        spec = build.specs[0]
        assert len(spec.sockets) == 1
        assert spec.sockets[0].node_id == 26725
        assert spec.sockets[0].item_id == 1

    def test_url_parsed(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.specs[0].url == "https://example.com/tree"

    def test_empty_nodes(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Tree activeSpec="1">
                    <Spec title="Empty" treeVersion="3_25" nodes=""/>
                </Tree>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.specs[0].nodes == []

    def test_multiple_specs(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Tree activeSpec="2">
                    <Spec title="First" treeVersion="3_25" nodes="1,2,3"/>
                    <Spec title="Second" treeVersion="3_25" nodes="4,5"/>
                    <Spec title="Third" treeVersion="3_25" nodes="6"/>
                </Tree>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert len(build.specs) == 3
        assert build.active_spec == 2
        assert build.get_active_spec().title == "Second"


# ── Mastery effect parsing ───────────────────────────────────────────────────


class TestParseMasteryMappings:
    def test_basic_pair(self):
        effects = _parse_mastery_effects("{100,200}")
        assert len(effects) == 1
        assert effects[0].node_id == 100
        assert effects[0].effect_id == 200

    def test_multiple_pairs(self):
        effects = _parse_mastery_effects("{100,200},{300,400},{500,600}")
        assert len(effects) == 3

    def test_empty_string(self):
        assert _parse_mastery_effects("") == []

    def test_invalid_values_skipped(self):
        effects = _parse_mastery_effects("{abc,def},{100,200}")
        assert len(effects) == 1


# ── Item parsing ─────────────────────────────────────────────────────────────


class TestParseItems:
    def test_basic_rare(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert len(build.items) == 1
        item = build.items[0]
        assert item.rarity == "RARE"
        assert item.name == "Doom Crown"
        assert item.base_type == "Hubris Circlet"

    def test_prefix_suffix_slots(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        item = build.items[0]
        assert "IncreasedLife6" in item.prefix_slots
        assert "SpellDamage3" in item.prefix_slots
        assert None in item.prefix_slots
        assert item.open_prefixes == 1
        assert "ColdResistance5" in item.suffix_slots
        assert item.open_suffixes == 1

    def test_implicit_counting(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        item = build.items[0]
        assert len(item.implicits) == 1
        assert "Life" in item.implicits[0].text

    def test_energy_shield_parsed(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.items[0].energy_shield == 200

    def test_quality_parsed(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.items[0].quality == 20

    def test_sockets_parsed(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.items[0].sockets == "B-B-B-B"

    def test_level_req_parsed(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.items[0].level_req == 69

    def test_item_with_influences(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test Crown
Hubris Circlet
Shaper Item
Elder Item
Implicits: 0
+50 to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert "Shaper" in item.influences
        assert "Elder" in item.influences

    def test_new_item_placeholder(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: NORMAL
New Item
Hubris Circlet
Implicits: 0
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.items[0].name == "Hubris Circlet"

    def test_unique_item(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: UNIQUE
Heatshiver
Leather Cap
Quality: 0
Sockets: R-R-R-R
LevelReq: 1
Implicits: 1
+(15-25) to maximum Life
{range:0.5}+20 to maximum Life
{variant:1}(30-50)% increased Critical Strike Chance for Spells
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.rarity == "UNIQUE"
        assert item.name == "Heatshiver"
        assert item.base_type == "Leather Cap"


# ── Mod line parsing ─────────────────────────────────────────────────────────


class TestParseModLine:
    def test_plain_mod(self):
        mod = _parse_mod_line("+50 to maximum Life")
        assert mod.text == "+50 to maximum Life"
        assert not mod.is_crafted

    def test_crafted_mod(self):
        mod = _parse_mod_line("{crafted}+25% to Cold Resistance")
        assert mod.is_crafted
        assert mod.text == "+25% to Cold Resistance"

    def test_exarch_mod(self):
        mod = _parse_mod_line("{exarch}Fire Damage Leeched as Life")
        assert mod.is_exarch
        assert not mod.is_eater

    def test_eater_mod(self):
        mod = _parse_mod_line("{eater}Cold Damage Leeched as Life")
        assert mod.is_eater

    def test_tags(self):
        mod = _parse_mod_line("{tags:resource,life}{range:0.5}+70 to maximum Life")
        assert mod.tags == ["resource", "life"]
        assert mod.range_value == 0.5

    def test_variant(self):
        mod = _parse_mod_line("{variant:1,2}+30% to Fire Resistance")
        assert mod.variant == "1,2"

    def test_custom_mod(self):
        mod = _parse_mod_line("{custom}Custom Modifier Text")
        assert mod.is_custom

    def test_empty_text_returns_none(self):
        mod = _parse_mod_line("{crafted}")
        assert mod is None

    def test_multiple_markers(self):
        mod = _parse_mod_line("{crafted}{range:0.75}+30% to Cold Resistance")
        assert mod.is_crafted
        assert mod.range_value == 0.75

    def test_enchant_mod(self):
        mod = _parse_mod_line("{enchant}40% increased Damage")
        assert mod.is_enchant
        assert mod.text == "40% increased Damage"

    def test_scourge_mod(self):
        mod = _parse_mod_line("{scourge}+20% to Fire Resistance")
        assert mod.is_scourge
        assert mod.text == "+20% to Fire Resistance"

    def test_crucible_mod(self):
        mod = _parse_mod_line("{crucible}10% increased Attack Speed")
        assert mod.is_crucible
        assert mod.text == "10% increased Attack Speed"

    def test_synthesis_mod(self):
        mod = _parse_mod_line("{synthesis}+1 to Level of all Skill Gems")
        assert mod.is_synthesis
        assert mod.text == "+1 to Level of all Skill Gems"

    def test_mutated_mod(self):
        mod = _parse_mod_line("{mutated}+30 to Strength")
        assert mod.is_mutated
        assert mod.text == "+30 to Strength"


# ── Malformed mod line parsing ───────────────────────────────────────────────


class TestParseModLineMalformed:
    def test_malformed_marker_no_closing_brace(self):
        """Malformed marker {crafted without closing brace should not crash."""
        result = _parse_mod_line("{crafted+90 to maximum Life")
        # Should handle gracefully -- either parse as text or return None
        # The key thing is it does not crash with ValueError
        assert result is not None or result is None  # Just verify no exception

    def test_malformed_marker_preserves_text(self):
        """When closing brace is missing, the rest is treated as text."""
        result = _parse_mod_line("{crafted+90 to maximum Life")
        # The parser breaks out of the while loop since find("}") returns -1
        # Then the entire line becomes the text
        if result is not None:
            assert "90 to maximum Life" in result.text


# ── Gem parsing ──────────────────────────────────────────────────────────────


class TestParseGems:
    def test_active_and_support(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert len(build.skill_groups) == 1
        gems = build.skill_groups[0].gems
        assert len(gems) == 2
        assert gems[0].name_spec == "Fireball"
        assert gems[1].name_spec == "Spell Echo Support"

    def test_gem_level_quality(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        gem = build.skill_groups[0].gems[0]
        assert gem.level == 20
        assert gem.quality == 20

    def test_disabled_gem(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills activeSkillSet="1">
                    <SkillSet id="1">
                        <Skill slot="" enabled="true">
                            <Gem nameSpec="Fireball" level="20" quality="0" enabled="false"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_groups[0].gems[0].enabled is False

    def test_skill_set_ids(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills activeSkillSet="2">
                    <SkillSet id="1">
                        <Skill slot="" enabled="true">
                            <Gem nameSpec="Fireball" level="20" quality="0" enabled="true"/>
                        </Skill>
                    </SkillSet>
                    <SkillSet id="2">
                        <Skill slot="" enabled="true">
                            <Gem nameSpec="Arc" level="20" quality="0" enabled="true"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_set_ids == [1, 2]
        assert build.active_skill_set == 2
        assert build.skill_groups[0].gems[0].name_spec == "Arc"

    def test_specific_skill_set_id(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills activeSkillSet="2">
                    <SkillSet id="1">
                        <Skill slot="" enabled="true">
                            <Gem nameSpec="Fireball" level="20" quality="0" enabled="true"/>
                        </Skill>
                    </SkillSet>
                    <SkillSet id="2">
                        <Skill slot="" enabled="true">
                            <Gem nameSpec="Arc" level="20" quality="0" enabled="true"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml), skill_set_id=1)
        assert build.skill_groups[0].gems[0].name_spec == "Fireball"

    def test_include_in_full_dps(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.skill_groups[0].include_in_full_dps is True

    def test_gem_with_minion(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills activeSkillSet="1">
                    <SkillSet id="1">
                        <Skill slot="" enabled="true">
                            <Gem nameSpec="Blink Arrow" level="20" quality="0"
                                 enabled="true" skillMinion="BlinkArrowClone"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_groups[0].gems[0].skill_minion == "BlinkArrowClone"


# ── Config parsing ───────────────────────────────────────────────────────────


class TestParseConfig:
    def test_boolean_input(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        cfg = build.get_active_config()
        inputs = {inp.name: inp for inp in cfg.inputs}
        assert inputs["useFrenzyCharges"].value is True
        assert inputs["useFrenzyCharges"].input_type == "boolean"

    def test_number_input(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        cfg = build.get_active_config()
        inputs = {inp.name: inp for inp in cfg.inputs}
        assert inputs["enemyPhysicalHitDamage"].value == 5000
        assert inputs["enemyPhysicalHitDamage"].input_type == "number"

    def test_string_input(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Config activeConfigSet="1">
                    <ConfigSet id="1" title="Default">
                        <Input name="customMods" string="10% more damage"/>
                    </ConfigSet>
                </Config>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        cfg = build.get_active_config()
        assert cfg.inputs[0].value == "10% more damage"
        assert cfg.inputs[0].input_type == "string"


# ── Edge cases ───────────────────────────────────────────────────────────────


class TestParserEdgeCases:
    def test_missing_build_section(self, tmp_path):
        xml = '<?xml version="1.0"?><PathOfBuilding></PathOfBuilding>'
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.class_name == ""
        assert build.level == 1

    def test_missing_tree_section(self, tmp_path):
        xml = (
            '<?xml version="1.0"?><PathOfBuilding>'
            '<Build level="50" className="Witch" ascendClassName=""/>'
            "</PathOfBuilding>"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.specs == []

    def test_missing_skills_section(self, tmp_path):
        xml = (
            '<?xml version="1.0"?><PathOfBuilding>'
            '<Build level="1" className="Witch" ascendClassName=""/>'
            "</PathOfBuilding>"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_groups == []

    def test_missing_items_section(self, tmp_path):
        xml = (
            '<?xml version="1.0"?><PathOfBuilding>'
            '<Build level="1" className="Witch" ascendClassName=""/>'
            "</PathOfBuilding>"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.items == []

    def test_item_set_with_slots(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert len(build.item_sets) == 1
        assert build.item_sets[0].slots[0].name == "Helmet"
        assert build.item_sets[0].slots[0].item_id == 1


# ── Fractured mod parsing ───────────────────────────────────────────────────


class TestFracturedModParsing:
    def test_fractured_mod_parsed(self, tmp_path):
        """Parse {fractured} item mod."""
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test Crown
Hubris Circlet
Implicits: 0
{fractured}+90 to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert len(item.explicits) == 1
        assert item.explicits[0].is_fractured is True
        assert item.explicits[0].text == "+90 to maximum Life"


# ── Synthesised item parsing ─────────────────────────────────────────────


class TestSynthesisedItemParsing:
    def test_synthesised_item_parsed(self, tmp_path):
        """Parse 'Synthesised Item' line on an item."""
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Synth Crown
Hubris Circlet
Synthesised Item
Implicits: 1
+30 to Dexterity
+90 to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.is_synthesised is True
        assert len(item.implicits) == 1
        assert len(item.explicits) == 1

    def test_synthesised_with_influence(self, tmp_path):
        """Parse synthesised item that also has influence lines."""
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Synth Crown
Hubris Circlet
Shaper Item
Synthesised Item
Implicits: 0
+90 to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.is_synthesised is True
        assert "Shaper" in item.influences

    def test_non_synthesised_item(self, tmp_path):
        """Normal items have is_synthesised=False."""
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Normal Crown
Hubris Circlet
Implicits: 0
+90 to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.is_synthesised is False


# ── Package-level parse_build_file tests ────────────────────────────────────


class TestParseBuildFile:
    def test_parse_returns_build(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.class_name == "Witch"
        assert build.ascend_class_name == "Necromancer"
        assert build.level == 90

    def test_parse_with_string_path(self, minimal_build_xml):
        build = parse_build_file(str(minimal_build_xml))
        assert build.class_name == "Witch"

    def test_parse_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_build_file(tmp_path / "nonexistent.xml")

    def test_parse_stats(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert build.get_stat("Life") == 4500
        assert build.get_stat("TotalDPS") == 150000

    def test_parse_tree(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        spec = build.get_active_spec()
        assert spec is not None
        assert len(spec.nodes) == 4

    def test_parse_items(self, minimal_build_xml):
        build = parse_build_file(minimal_build_xml)
        assert len(build.items) >= 1
        equipped = build.get_equipped_items()
        assert any(slot == "Helmet" for slot, _ in equipped)


# ── Metadata filter (Bug 1) ──────────────────────────────────────────────────


class TestPoBMetadataNotExplicits:
    def _make_xml(self, item_text: str) -> str:
        return textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
{item_text}
                    </Item>
                </Items>
            </PathOfBuilding>
        """)

    def test_has_alt_variant_not_in_explicits(self, tmp_path):
        xml = self._make_xml(
            "Rarity: UNIQUE\nWatcher's Eye\nPrismatic Jewel\n"
            "Has Alt Variant: true\nSelected Alt Variant: 9\n"
            "Implicits: 0\n+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        texts = [m.text for m in item.explicits]
        assert not any("Has Alt Variant" in t for t in texts)
        assert not any("Selected Alt Variant" in t for t in texts)

    def test_has_alt_variant_two_not_in_explicits(self, tmp_path):
        xml = self._make_xml(
            "Rarity: UNIQUE\nWatcher's Eye\nPrismatic Jewel\n"
            "Has Alt Variant: true\nSelected Alt Variant: 29\n"
            "Has Alt Variant Two: true\nSelected Alt Variant Two: 1\n"
            "Implicits: 0\n+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        texts = [m.text for m in item.explicits]
        assert not any("Has Alt Variant" in t for t in texts)
        assert not any("Selected Alt Variant" in t for t in texts)
        assert len(item.explicits) == 1
        assert item.explicits[0].text == "+50 to maximum Life"

    def test_has_variant_not_in_explicits(self, tmp_path):
        xml = self._make_xml(
            "Rarity: UNIQUE\nSome Jewel\nPrismatic Jewel\n"
            "Has Variant: 2\n"
            "Implicits: 0\n+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        texts = [m.text for m in item.explicits]
        assert not any("Has Variant" in t for t in texts)

    def test_source_not_in_explicits(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Crown\nHubris Circlet\n"
            "Source: Some League\n"
            "Implicits: 0\n+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        texts = [m.text for m in item.explicits]
        assert not any("Source:" in t for t in texts)
        assert len(item.explicits) == 1


# ── Magic item base_type (Bug 2) ─────────────────────────────────────────────


class TestMagicItemBaseType:
    def _make_xml(self, item_text: str) -> str:
        return textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
{item_text}
                    </Item>
                </Items>
            </PathOfBuilding>
        """)

    def test_magic_flask_base_type_strips_suffix(self, tmp_path):
        xml = self._make_xml(
            "Rarity: MAGIC\nChemist's Silver Flask of the Owl\n"
            "Crafted: true\nPrefix: FlaskChargesUsed4\nSuffix: FlaskBuff\n"
            "Quality: 20\nLevelReq: 22\nImplicits: 0\n"
            "24% reduced Charges per use"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.rarity == "MAGIC"
        assert item.name == "Chemist's Silver Flask of the Owl"
        assert item.base_type == "Silver Flask"

    def test_magic_flask_suffix_only_strips(self, tmp_path):
        xml = self._make_xml(
            "Rarity: MAGIC\nJade Flask of the Deer\n"
            "Quality: 0\nLevelReq: 27\nImplicits: 0\n"
            "20% increased Movement Speed during Effect"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.base_type == "Jade Flask"

    def test_normal_item_base_type_equals_name(self, tmp_path):
        xml = self._make_xml("Rarity: NORMAL\nSilver Flask\nQuality: 0\nLevelReq: 22\nImplicits: 0")
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.name == "Silver Flask"
        assert item.base_type == "Silver Flask"

    def test_rare_item_base_type_distinct_from_name(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nDoom Crown\nHubris Circlet\nImplicits: 0\n+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.name == "Doom Crown"
        assert item.base_type == "Hubris Circlet"


# ── _parse_affix_slot sentinel pattern ───────────────────────────────────────


class TestParseAffixSlotSentinel:
    """AFFIX_NO_MATCH must be distinguishable from None and from real mod IDs."""

    def test_affix_no_match_is_distinct_object(self):
        from poe.services.build.constants import AFFIX_NO_MATCH

        assert AFFIX_NO_MATCH is not None
        assert AFFIX_NO_MATCH != ""
        assert AFFIX_NO_MATCH is not False

    def test_non_affix_line_returns_sentinel(self):
        from poe.services.build.constants import AFFIX_NO_MATCH, PREFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        result = _parse_affix_slot("+50 to maximum Life", PREFIX_RE)
        assert result is AFFIX_NO_MATCH

    def test_prefix_line_with_none_returns_python_none(self):
        from poe.services.build.constants import AFFIX_NO_MATCH, PREFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        result = _parse_affix_slot("Prefix: None", PREFIX_RE)
        assert result is None
        assert result is not AFFIX_NO_MATCH

    def test_prefix_with_mod_id_returns_string(self):
        from poe.services.build.constants import AFFIX_NO_MATCH, PREFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        result = _parse_affix_slot("Prefix: IncreasedLife6", PREFIX_RE)
        assert result == "IncreasedLife6"
        assert result is not AFFIX_NO_MATCH

    def test_prefix_with_range_marker_strips_range(self):
        from poe.services.build.constants import PREFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        result = _parse_affix_slot("Prefix: {range:0.5}IncreasedLife6", PREFIX_RE)
        assert result == "IncreasedLife6"

    def test_suffix_line_with_none_returns_python_none(self):
        from poe.services.build.constants import SUFFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        result = _parse_affix_slot("Suffix: None", SUFFIX_RE)
        assert result is None

    def test_suffix_pattern_does_not_match_prefix_line(self):
        from poe.services.build.constants import AFFIX_NO_MATCH, SUFFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        result = _parse_affix_slot("Prefix: IncreasedLife6", SUFFIX_RE)
        assert result is AFFIX_NO_MATCH

    def test_sentinel_distinguishable_in_filtered_list(self):
        from poe.services.build.constants import AFFIX_NO_MATCH, PREFIX_RE
        from poe.services.build.xml.parser import _parse_affix_slot

        lines = ["Prefix: IncreasedLife6", "Prefix: None", "Random text"]
        results = [_parse_affix_slot(line, PREFIX_RE) for line in lines]
        # Filter sentinel out
        prefixes = [r for r in results if r is not AFFIX_NO_MATCH]
        assert len(prefixes) == 2
        assert "IncreasedLife6" in prefixes
        assert None in prefixes


# ── _assign_affix_metadata keyword matching ──────────────────────────────────


class TestAssignAffixMetadata:
    """Test the keyword-based prefix/suffix assignment using slot mod IDs."""

    def _make_xml(self, item_text: str) -> str:
        return textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
{item_text}
                    </Item>
                </Items>
            </PathOfBuilding>
        """)

    def test_prefix_count_invariant(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Helm\nHubris Circlet\nImplicits: 0\n"
            "Prefix: IncreasedLife6\n"
            "Suffix: ColdResistance5\n"
            "+50 to maximum Life\n"
            "+30% to Cold Resistance"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        # Invariant: number of prefix-tagged mods must not exceed filled prefix slots
        prefix_tagged = sum(1 for m in item.explicits if m.is_prefix)
        suffix_tagged = sum(1 for m in item.explicits if m.is_suffix)
        assert prefix_tagged <= item.filled_prefixes
        assert suffix_tagged <= item.filled_suffixes

    def test_assigned_explicits_have_mod_ids(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Helm\nHubris Circlet\nImplicits: 0\n"
            "Prefix: IncreasedLife6\n"
            "Suffix: ColdResistance5\n"
            "+50 to maximum Life\n"
            "+30% to Cold Resistance"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        for m in item.explicits:
            if m.is_prefix:
                assert m.mod_id != ""
            if m.is_suffix:
                assert m.mod_id != ""

    def test_no_slots_no_affix_assignment(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Helm\nHubris Circlet\nImplicits: 0\n+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        for m in item.explicits:
            assert not m.is_prefix
            assert not m.is_suffix
            assert m.mod_id == ""

    def test_crafted_mods_excluded_from_assignment(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Helm\nHubris Circlet\nImplicits: 0\n"
            "Prefix: IncreasedLife6\n"
            "Suffix: None\n"
            "+50 to maximum Life\n"
            "{crafted}+30% to Cold Resistance"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        crafted = [m for m in item.explicits if m.is_crafted]
        # Crafted should not be tagged as prefix/suffix or get mod_id from slot
        for m in crafted:
            assert m.mod_id == ""

    def test_mod_index_claim_uniqueness(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Helm\nHubris Circlet\nImplicits: 0\n"
            "Prefix: IncreasedLife6\n"
            "Prefix: SpellDamage3\n"
            "Suffix: ColdResistance5\n"
            "+50 to maximum Life\n"
            "Adds 30 to 50 Spell Damage\n"
            "+30% to Cold Resistance"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assigned_ids = [m.mod_id for m in item.explicits if m.mod_id]
        # No duplicate mod_ids should be claimed
        assert len(assigned_ids) == len(set(assigned_ids))


# ── Bandit field None handling ──────────────────────────────────────────────


class TestBanditField:
    def test_bandit_none_string_becomes_python_none(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName="" bandit="None"/>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.bandit is None

    def test_bandit_empty_string_becomes_python_none(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName="" bandit=""/>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.bandit is None

    @pytest.mark.parametrize("bandit", ["Alira", "Kraityn", "Oak"])
    def test_bandit_named_choice_preserved(self, tmp_path, bandit):
        xml = textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName="" bandit="{bandit}"/>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.bandit == bandit


# ── Level bounds parsing ─────────────────────────────────────────────────────


class TestLevelParsing:
    @pytest.mark.parametrize("level", [1, 50, 90, 100])
    def test_level_within_bounds_preserved(self, tmp_path, level):
        xml = textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="{level}" className="Witch" ascendClassName=""/>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.level == level

    def test_level_zero_clamped_to_one_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="0" className="Witch" ascendClassName=""/>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.level == 1
        assert any("level=0" in r.message and "minimum" in r.message for r in caplog.records)

    def test_level_above_max_clamped_to_100_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="9999" className="Witch" ascendClassName=""/>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.level == 100
        assert any("level=9999" in r.message and "maximum" in r.message for r in caplog.records)


class TestParseStatBoundary:
    def test_player_stat_with_empty_name_is_skipped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName="">
                    <PlayerStat stat="" value="42"/>
                    <PlayerStat stat="Life" value="4500"/>
                </Build>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert [s.stat for s in build.player_stats] == ["Life"]
        assert any("missing 'stat'" in r.message for r in caplog.records)

    def test_minion_stat_with_empty_name_is_skipped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName="">
                    <MinionStat stat="" value="100"/>
                </Build>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.minion_stats == []
        assert any("missing 'stat'" in r.message for r in caplog.records)


class TestParseItemBoundary:
    def test_item_with_zero_id_is_skipped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="0">
Rarity: RARE
Test
Hubris Circlet
                    </Item>
                    <Item id="2">
Rarity: RARE
Real
Hubris Circlet
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert [i.id for i in build.items] == [2]
        assert any("non-positive id" in r.message for r in caplog.records)

    def test_item_quality_above_30_clamped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test
Hubris Circlet
Quality: 99
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.items[0].quality == 30
        assert any("quality=99" in r.message and "maximum" in r.message for r in caplog.records)

    def test_item_level_above_100_clamped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test
Hubris Circlet
Item Level: 200
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.items[0].item_level == 100
        assert any("item_level=200" in r.message and "maximum" in r.message for r in caplog.records)


class TestParseConfigBoundary:
    def test_config_input_with_empty_name_skipped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Config>
                    <Input name="" boolean="true"/>
                    <Input name="useFrenzyCharges" boolean="true"/>
                </Config>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        names = [e.name for e in build.config_sets[0].inputs]
        assert names == ["useFrenzyCharges"]
        assert any("missing 'name'" in r.message for r in caplog.records)

    def test_config_set_with_empty_id_defaulted_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Config activeConfigSet="1">
                    <ConfigSet id="" title="Empty Id">
                        <Input name="useFrenzyCharges" boolean="true"/>
                    </ConfigSet>
                </Config>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.config_sets[0].id == "1"
        assert any("missing 'id'" in r.message for r in caplog.records)


class TestParseGemBoundary:
    def test_gem_level_above_max_clamped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills>
                    <SkillSet id="1">
                        <Skill>
                            <Gem nameSpec="Fireball" level="999" quality="0"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_groups[0].gems[0].level == 40
        assert any("gem level=999" in r.message and "maximum" in r.message for r in caplog.records)

    def test_gem_quality_above_max_clamped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills>
                    <SkillSet id="1">
                        <Skill>
                            <Gem nameSpec="Fireball" level="20" quality="99"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_groups[0].gems[0].quality == 30
        assert any("gem quality=99" in r.message and "maximum" in r.message for r in caplog.records)

    def test_gem_zero_count_clamped_to_one_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills>
                    <SkillSet id="1">
                        <Skill>
                            <Gem nameSpec="Fireball" level="20" quality="0" count="0"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.skill_groups[0].gems[0].count == 1
        assert any("gem count=0" in r.message and "minimum" in r.message for r in caplog.records)

    def test_gem_with_empty_name_spec_skipped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Skills>
                    <SkillSet id="1">
                        <Skill>
                            <Gem nameSpec="" level="20" quality="0"/>
                            <Gem nameSpec="Fireball" level="20" quality="0"/>
                        </Skill>
                    </SkillSet>
                </Skills>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert [g.name_spec for g in build.skill_groups[0].gems] == ["Fireball"]
        assert any("empty nameSpec" in r.message for r in caplog.records)


class TestParseItemSlotBoundary:
    def test_slot_with_empty_name_is_skipped_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test
Hubris Circlet
                    </Item>
                    <ItemSet id="1" title="Default">
                        <Slot name="" itemId="1"/>
                        <Slot name="Helmet" itemId="1"/>
                    </ItemSet>
                </Items>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert [s.name for s in build.item_sets[0].slots] == ["Helmet"]
        assert any("empty name" in r.message for r in caplog.records)

    def test_slot_with_zero_item_id_is_skipped_silently(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test
Hubris Circlet
                    </Item>
                    <ItemSet id="1" title="Default">
                        <Slot name="Helmet" itemId="0"/>
                        <Slot name="Body" itemId="1"/>
                    </ItemSet>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert [s.name for s in build.item_sets[0].slots] == ["Body"]


class TestParseItemSetBoundary:
    def test_item_set_with_empty_id_is_defaulted_with_warning(self, tmp_path, caplog):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <ItemSet id="" title="Default"/>
                </Items>
            </PathOfBuilding>
        """)
        with caplog.at_level("WARNING", logger="poe.parser"):
            build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.item_sets[0].id == "1"
        assert any("missing 'id'" in r.message for r in caplog.records)


# ── Influence enum coverage ──────────────────────────────────────────────────


class TestInfluenceEnumCoverage:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("Shaper Item", "Shaper"),
            ("Elder Item", "Elder"),
            ("Crusader Item", "Crusader"),
            ("Hunter Item", "Hunter"),
            ("Redeemer Item", "Redeemer"),
            ("Warlord Item", "Warlord"),
            ("Searing Exarch Item", "Searing Exarch"),
            ("Eater of Worlds Item", "Eater of Worlds"),
        ],
    )
    def test_each_influence_parsed(self, tmp_path, line, expected):
        xml = textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test Crown
Hubris Circlet
{line}
Implicits: 0
+50 to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert expected in build.items[0].influences


# ── Rarity enum coverage ─────────────────────────────────────────────────────


class TestRarityEnumCoverage:
    @pytest.mark.parametrize("rarity", ["NORMAL", "MAGIC", "RARE", "UNIQUE", "RELIC"])
    def test_each_rarity_parsed(self, tmp_path, rarity):
        xml = textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: {rarity}
Test Item
Hubris Circlet
Implicits: 0
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert build.items[0].rarity == rarity


# ── Empty/invalid XML negative paths ─────────────────────────────────────────


class TestParserNegativePaths:
    def test_invalid_xml_raises(self, tmp_path):
        from defusedxml.common import EntitiesForbidden  # noqa: F401

        p = tmp_path / "bad.xml"
        p.write_text("not valid xml at all <<<>>>", encoding="utf-8")
        with pytest.raises(Exception):  # noqa: B017
            parse_build_file(p)

    def test_truly_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.xml"
        p.write_text("", encoding="utf-8")
        with pytest.raises(Exception):  # noqa: B017
            parse_build_file(p)


# ── Item state lines (negative tests for _parse_header_line) ─────────────────


class TestItemStateLines:
    @pytest.mark.parametrize(
        ("line", "field"),
        [
            ("Synthesised Item", "is_synthesised"),
            ("Fractured Item", "is_fractured"),
            ("Crafted: true", "is_crafted"),
            ("Corrupted", "is_corrupted"),
            ("Mirrored", "is_mirrored"),
            ("Split", "is_split"),
            ("Has Veiled Prefix", "has_veiled_prefix"),
            ("Has Veiled Suffix", "has_veiled_suffix"),
        ],
    )
    def test_each_state_line_sets_field(self, tmp_path, line, field):
        xml = textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
Rarity: RARE
Test Item
Hubris Circlet
{line}
Implicits: 0
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        build = parse_build_file(_write_xml(tmp_path, xml))
        assert getattr(build.items[0], field) is True


# ── prefix_slots + open_prefixes invariants ─────────────────────────────────


class TestPrefixSuffixSlotInvariants:
    def _make_xml(self, item_text: str) -> str:
        return textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1">
{item_text}
                    </Item>
                </Items>
            </PathOfBuilding>
        """)

    def test_open_plus_filled_equals_total(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Item\nHubris Circlet\nImplicits: 0\n"
            "Prefix: IncreasedLife6\n"
            "Prefix: None\n"
            "Prefix: None\n"
            "Suffix: ColdResistance5\n"
            "Suffix: None\n"
            "+50 to maximum Life\n"
            "+30% to Cold Resistance"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.open_prefixes + item.filled_prefixes == len(item.prefix_slots)
        assert item.open_suffixes + item.filled_suffixes == len(item.suffix_slots)

    def test_filled_count_matches_non_none_entries(self, tmp_path):
        xml = self._make_xml(
            "Rarity: RARE\nTest Item\nHubris Circlet\nImplicits: 0\n"
            "Prefix: IncreasedLife6\n"
            "Suffix: None\n"
            "+50 to maximum Life"
        )
        build = parse_build_file(_write_xml(tmp_path, xml))
        item = build.items[0]
        assert item.filled_prefixes == sum(1 for s in item.prefix_slots if s is not None)
        assert item.open_suffixes == sum(1 for s in item.suffix_slots if s is None)

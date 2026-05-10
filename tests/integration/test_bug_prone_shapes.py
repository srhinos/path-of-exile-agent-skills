"""Integration tests that exercise the bug-prone XML shapes that synthetic builds miss.

These tests target the failure modes a parallel-agent audit surfaced:
- PoB color codes (^xRRGGBB) in <Notes> being lost on round-trip.
- Multi-variant items losing inactive-variant mods on round-trip.
- Strict model bounds without parser coercion crashing on real PoB XML
  (level=0, targetVersion="", duplicate tree nodes, inf/nan stats, Item
  id=0, ItemMod range_value > 1, malformed classId/nodeId attributes).
- Enum/lookup table desync (Influence enum vs INFLUENCE_TAG_MAP).

Each test writes a raw XML string with the bug-prone shape and asserts the
parser tolerates it (per the boundary-contract architecture: coerce + warn,
never crash on weird input).
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from poe.services.build.xml.parser import parse_build_file
from poe.services.build.xml.writer import write_build_file

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _write_xml(tmp_path: Path, xml: str, name: str = "test.xml") -> Path:
    p = tmp_path / name
    p.write_text(xml.lstrip(), encoding="utf-8")
    return p


# ── Round-trip data preservation ────────────────────────────────────────────


class TestNotesRoundTripPreservesColorCodes:
    """<Notes> with ^xRRGGBB color codes must survive parse → write → parse."""

    def test_color_codes_survive_roundtrip(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="90" className="Witch" ascendClassName=""/>
                <Notes>^xFF0000Critical:^7 cap resists. ^x00FF00Tip:^7 use flask.</Notes>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "with_colors.xml")
        build = parse_build_file(p)
        assert "^xFF0000" in build.notes, (
            "Color codes stripped on parse — they should be preserved so the "
            "writer can round-trip them without data loss."
        )

        out = tmp_path / "rewritten.xml"
        write_build_file(build, out)
        reparsed = parse_build_file(out)
        assert "^xFF0000" in reparsed.notes


class TestMultiVariantItemsRoundTrip:
    """Items with {variant:N} mods must preserve inactive variants on round-trip."""

    def test_inactive_variant_mods_survive(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="90" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="1" variant="2">
Rarity: UNIQUE
Watcher's Eye
Prismatic Jewel
Variant: Anger
Variant: Hatred
Variant: Wrath
Selected Variant: 2
Implicits: 0
{variant:1}+(15-25)% to Fire Resistance while affected by Anger
{variant:2}+(15-25)% to Cold Resistance while affected by Hatred
{variant:3}+(15-25)% to Lightning Resistance while affected by Wrath
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "watchers_eye.xml")
        build = parse_build_file(p)

        out = tmp_path / "watchers_eye_out.xml"
        write_build_file(build, out)
        reparsed = parse_build_file(out)

        item = reparsed.items[0]
        text = "\n".join(m.text for m in item.implicits + item.explicits)
        assert "Anger" in text and "Hatred" in text and "Wrath" in text, (
            "All three variant mods must round-trip; inactive variants are part "
            "of the unique's identity, not optional decoration."
        )


# ── Strict bounds + parser coercion ─────────────────────────────────────────


class TestParserToleratesEdgeXMLValues:
    """Strict model constraints require the parser to coerce, not crash."""

    def test_level_zero_does_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="0" className="Witch" ascendClassName=""/>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "level_zero.xml")
        build = parse_build_file(p)
        assert build.level >= 1

    def test_empty_target_version_does_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName="" targetVersion=""/>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "empty_version.xml")
        build = parse_build_file(p)
        assert build.target_version, "Empty targetVersion should coerce to a default, not raise"

    def test_duplicate_tree_nodes_do_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Tree activeSpec="1">
                    <Spec title="Main" treeVersion="3_25" nodes="100,200,100,300"/>
                </Tree>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "dup_nodes.xml")
        build = parse_build_file(p)
        nodes = build.specs[0].nodes
        assert len(nodes) == len(set(nodes)), "Duplicate node IDs must be deduped, not crash"
        assert {100, 200, 300}.issubset(set(nodes))

    def test_player_stat_inf_does_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="90" className="Witch" ascendClassName="">
                    <PlayerStat stat="Life" value="4500"/>
                    <PlayerStat stat="OverCapResist" value="inf"/>
                </Build>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "inf_stat.xml")
        build = parse_build_file(p)
        stat_names = {s.stat for s in build.player_stats}
        assert "Life" in stat_names, "valid stats must still parse"

    def test_player_stat_nan_does_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="90" className="Witch" ascendClassName="">
                    <PlayerStat stat="Life" value="4500"/>
                    <PlayerStat stat="DivByZero" value="nan"/>
                </Build>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "nan_stat.xml")
        build = parse_build_file(p)
        stat_names = {s.stat for s in build.player_stats}
        assert "Life" in stat_names

    def test_malformed_tree_class_id_does_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Tree activeSpec="1">
                    <Spec title="Main" treeVersion="3_25" classId="bad" ascendClassId="-1"
                          nodes="100,200"/>
                </Tree>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "bad_class.xml")
        build = parse_build_file(p)
        assert build.specs[0].class_id >= 0

    def test_item_with_id_zero_does_not_crash(self, tmp_path):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <PathOfBuilding>
                <Build level="1" className="Witch" ascendClassName=""/>
                <Items activeItemSet="1">
                    <Item id="0">
Rarity: NORMAL
Cheap Ring
Coral Ring
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "id_zero.xml")
        build = parse_build_file(p)
        assert isinstance(build.items, list), "id=0 item should be skipped, not crash"

    def test_item_mod_range_above_one_does_not_crash(self, tmp_path):
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
{range:1.5}+(50-70) to maximum Life
                    </Item>
                </Items>
            </PathOfBuilding>
        """)
        p = _write_xml(tmp_path, xml, "range_high.xml")
        build = parse_build_file(p)
        assert len(build.items) == 1, "Out-of-range marker must clamp, not drop the whole item"


# ── Enum/lookup agreement ───────────────────────────────────────────────────


class TestEnumLookupAgreement:
    """Enums and the lookup tables that depend on them must stay in sync."""

    def test_every_influence_is_classified(self):
        """Every Influence enum value must be either a conqueror (in TAG_MAP)
        or eldritch (in ELDRITCH_INFLUENCES). No silent fallthrough.
        """
        from poe.services.repoe.constants import ELDRITCH_INFLUENCES, INFLUENCE_TAG_MAP
        from poe.types import Influence

        conqueror_values = set(INFLUENCE_TAG_MAP.values())
        classified = conqueror_values | set(ELDRITCH_INFLUENCES)
        unclassified = {i.value for i in Influence} - classified
        assert not unclassified, (
            f"Influence enum has values not classified as conqueror or eldritch: "
            f"{sorted(unclassified)}. Add to INFLUENCE_TAG_MAP (conqueror) or "
            f"ELDRITCH_INFLUENCES (eldritch implicit) so get_mod_pool handles them."
        )

    def test_eldritch_influences_skipped_in_mod_pool(self, repoe_data):
        """get_mod_pool must skip eldritch influences without crashing or
        producing garbage codenames."""
        # Should not raise; should treat as no-influence query effectively.
        pool = repoe_data.get_mod_pool("Hubris Circlet", ilvl=84, influences=["Searing Exarch"])
        # Eldritch influence is skipped — pool is whatever non-influenced mods exist.
        assert isinstance(pool, list)

from __future__ import annotations

import pytest

from poe.models.build.build import BuildDocument
from poe.models.build.config import BuildConfig
from poe.models.build.items import ItemSet
from poe.models.build.stats import StatEntry
from poe.models.build.tree import TreeOverride, TreeSpec
from poe.services.build.xml.parser import parse_build_file
from poe.services.build.xml.writer import write_build_file

pytestmark = pytest.mark.integration


def _base_build(**kwargs):
    defaults = {
        "class_name": "Witch",
        "ascend_class_name": "Necromancer",
        "level": 90,
        "specs": [TreeSpec(tree_version="3_25", class_id=5, ascend_class_id=2, nodes=[100, 200])],
        "skill_set_ids": [1],
        "items": [],
        "item_sets": [ItemSet(id="1")],
        "config_sets": [BuildConfig(id="1", title="Default")],
    }
    defaults.update(kwargs)
    return BuildDocument(**defaults)


def _roundtrip(build, tmp_path, filename):
    path = tmp_path / filename
    write_build_file(build, path)
    return parse_build_file(path)


class TestBuildAttrs:
    def test_character_level_auto_mode(self, tmp_path):
        build = _base_build(character_level_auto_mode=True)
        reparsed = _roundtrip(build, tmp_path, "auto_mode.xml")
        assert reparsed.character_level_auto_mode

    def test_character_level_auto_mode_false_omitted(self, tmp_path):
        build = _base_build(character_level_auto_mode=False)
        reparsed = _roundtrip(build, tmp_path, "no_auto.xml")
        assert not reparsed.character_level_auto_mode


class TestTreeFeatures:
    def test_secondary_ascend_class_id(self, tmp_path):
        build = _base_build(
            specs=[
                TreeSpec(
                    tree_version="3_25",
                    class_id=5,
                    ascend_class_id=2,
                    secondary_ascend_class_id=3,
                    nodes=[100, 200],
                ),
            ],
        )
        reparsed = _roundtrip(build, tmp_path, "secondary_asc.xml")
        assert reparsed.specs[0].secondary_ascend_class_id == 3

    def test_tree_override_effect_image(self, tmp_path):
        build = _base_build(
            specs=[
                TreeSpec(
                    tree_version="3_25",
                    class_id=5,
                    ascend_class_id=2,
                    nodes=[100, 200],
                    overrides=[
                        TreeOverride(
                            node_id=12345,
                            name="Overridden Notable",
                            icon="Art/icon.png",
                            effect_image="Art/effect.png",
                            text="Some override text",
                        ),
                    ],
                ),
            ],
        )
        reparsed = _roundtrip(build, tmp_path, "override_img.xml")
        override = reparsed.specs[0].overrides[0]
        assert override.node_id == 12345
        assert override.name == "Overridden Notable"
        assert override.icon == "Art/icon.png"
        assert override.effect_image == "Art/effect.png"
        assert override.text == "Some override text"


class TestSpectresAndTimeless:
    def test_spectres(self, tmp_path):
        build = _base_build(spectres=["SolarGuard", "HostChieftain", "SlaveDriver"])
        reparsed = _roundtrip(build, tmp_path, "spectres.xml")
        assert reparsed.spectres == ["SolarGuard", "HostChieftain", "SlaveDriver"]

    def test_timeless_data_simple(self, tmp_path):
        build = _base_build(
            timeless_data={
                "timelessType": "Glorious Vanity",
                "timelessSeed": "7500",
                "timelessConqueror": "Doryani",
            },
        )
        reparsed = _roundtrip(build, tmp_path, "timeless.xml")
        assert reparsed.timeless_data["timelessType"] == "Glorious Vanity"
        assert reparsed.timeless_data["timelessSeed"] == "7500"
        assert reparsed.timeless_data["timelessConqueror"] == "Doryani"

    def test_timeless_data_with_children(self, tmp_path):
        # Children now live under a "children" subdict so a child tag
        # matching an attribute name (e.g. SearchResult attribute +
        # <SearchResult/> child) can't silently overwrite each other.
        build = _base_build(
            timeless_data={
                "timelessType": "Lethal Pride",
                "timelessSeed": "12345",
                "children": {
                    "TimelessJewelSocket": [
                        {"nodeId": "100", "socketIndex": "1"},
                        {"nodeId": "200", "socketIndex": "2"},
                    ],
                },
            },
        )
        reparsed = _roundtrip(build, tmp_path, "timeless_children.xml")
        assert reparsed.timeless_data["timelessType"] == "Lethal Pride"
        sockets = reparsed.timeless_data.get("children", {}).get("TimelessJewelSocket", [])
        assert len(sockets) == 2


class TestMinionAndDps:
    def test_minion_stats(self, tmp_path):
        build = _base_build(
            minion_stats=[
                StatEntry(stat="MinionLife", value=5000),
                StatEntry(stat="MinionDPS", value=80000),
            ],
        )
        reparsed = _roundtrip(build, tmp_path, "minion_stats.xml")
        assert len(reparsed.minion_stats) == 2
        stats = {s.stat: s.value for s in reparsed.minion_stats}
        assert stats["MinionLife"] == 5000
        assert stats["MinionDPS"] == 80000

    def test_full_dps_skills(self, tmp_path):
        build = _base_build(
            full_dps_skills=[
                {"index": "1", "dps": "500000"},
                {"index": "2", "dps": "250000"},
            ],
        )
        reparsed = _roundtrip(build, tmp_path, "full_dps.xml")
        assert len(reparsed.full_dps_skills) == 2
        assert reparsed.full_dps_skills[0]["index"] == "1"
        assert reparsed.full_dps_skills[1]["dps"] == "250000"


class TestImportAttrs:
    def test_all_import_attrs(self, tmp_path):
        build = _base_build(
            import_link="https://pobb.in/test123",
            import_last_realm="pc",
            import_last_character_hash="abc123",
            import_last_account_hash="def456",
            import_export_party="party1",
        )
        reparsed = _roundtrip(build, tmp_path, "import_attrs.xml")
        assert reparsed.import_link == "https://pobb.in/test123"
        assert reparsed.import_last_realm == "pc"
        assert reparsed.import_last_character_hash == "abc123"
        assert reparsed.import_last_account_hash == "def456"
        assert reparsed.import_export_party == "party1"

    def test_import_with_only_link(self, tmp_path):
        build = _base_build(import_link="https://pobb.in/simple")
        reparsed = _roundtrip(build, tmp_path, "import_link.xml")
        assert reparsed.import_link == "https://pobb.in/simple"
        assert reparsed.import_last_realm == ""


class TestPassthroughSections:
    def test_party_roundtrip(self, tmp_path):
        party_xml = '<Party><Member name="Support" buildCode="abc"/></Party>'
        build = _base_build(passthrough_sections={"Party": party_xml})
        reparsed = _roundtrip(build, tmp_path, "party.xml")
        assert "Party" in reparsed.passthrough_sections
        assert "Support" in reparsed.passthrough_sections["Party"]

    def test_calcs_roundtrip(self, tmp_path):
        calcs_xml = '<Calcs override="true"><Input name="test" number="42"/></Calcs>'
        build = _base_build(passthrough_sections={"Calcs": calcs_xml})
        reparsed = _roundtrip(build, tmp_path, "calcs.xml")
        assert "Calcs" in reparsed.passthrough_sections
        assert "test" in reparsed.passthrough_sections["Calcs"]

    def test_tree_view_roundtrip(self, tmp_path):
        build = _base_build(
            passthrough_sections={"TreeView": '<TreeView zoomLevel="3" x="100" y="200"/>'},
        )
        reparsed = _roundtrip(build, tmp_path, "tree_view.xml")
        assert "TreeView" in reparsed.passthrough_sections
        assert "zoomLevel" in reparsed.passthrough_sections["TreeView"]

    def test_trade_search_weights_roundtrip(self, tmp_path):
        tsw_xml = '<TradeSearchWeights><Weight stat="Life" weight="100"/></TradeSearchWeights>'
        build = _base_build(passthrough_sections={"TradeSearchWeights": tsw_xml})
        reparsed = _roundtrip(build, tmp_path, "trade_weights.xml")
        assert "TradeSearchWeights" in reparsed.passthrough_sections
        assert "Life" in reparsed.passthrough_sections["TradeSearchWeights"]

    def test_multiple_passthrough_sections(self, tmp_path):
        build = _base_build(
            passthrough_sections={
                "Party": '<Party><Member name="Support"/></Party>',
                "Calcs": "<Calcs/>",
                "TreeView": '<TreeView zoomLevel="5"/>',
                "TradeSearchWeights": "<TradeSearchWeights/>",
            },
        )
        reparsed = _roundtrip(build, tmp_path, "all_pass.xml")
        assert len(reparsed.passthrough_sections) == 4
        assert "Party" in reparsed.passthrough_sections
        assert "Calcs" in reparsed.passthrough_sections
        assert "TreeView" in reparsed.passthrough_sections
        assert "TradeSearchWeights" in reparsed.passthrough_sections


class TestFullFeatureRoundtrip:
    def test_kitchen_sink_build(self, tmp_path):
        build = BuildDocument(
            class_name="Witch",
            ascend_class_name="Necromancer",
            level=100,
            character_level_auto_mode=True,
            spectres=["SolarGuard", "HostChieftain"],
            timeless_data={"timelessType": "Glorious Vanity", "timelessSeed": "7500"},
            minion_stats=[StatEntry(stat="MinionLife", value=5000)],
            full_dps_skills=[{"index": "1", "dps": "500000"}],
            player_stats=[StatEntry(stat="Life", value=6000)],
            specs=[
                TreeSpec(
                    title="Main",
                    tree_version="3_25",
                    class_id=5,
                    ascend_class_id=2,
                    secondary_ascend_class_id=3,
                    nodes=[100, 200, 300],
                    overrides=[
                        TreeOverride(
                            node_id=999,
                            name="Override",
                            effect_image="Art/fx.png",
                        ),
                    ],
                ),
            ],
            skill_set_ids=[1],
            default_gem_level=20,
            default_gem_quality=20,
            sort_gems_by_dps=True,
            show_alt_quality_gems=True,
            skill_set_titles={1: "Main Skills"},
            skill_sets={1: []},
            items=[],
            item_sets=[ItemSet(id="1")],
            config_sets=[BuildConfig(id="1", title="Default")],
            import_link="https://pobb.in/kitchen",
            import_last_realm="pc",
            import_last_character_hash="hash1",
            import_last_account_hash="hash2",
            import_export_party="party1",
            passthrough_sections={
                "Party": '<Party><Member name="Support"/></Party>',
                "Calcs": "<Calcs/>",
            },
        )

        reparsed = _roundtrip(build, tmp_path, "kitchen_sink.xml")

        assert reparsed.character_level_auto_mode
        assert reparsed.spectres == ["SolarGuard", "HostChieftain"]
        assert reparsed.timeless_data["timelessType"] == "Glorious Vanity"
        assert len(reparsed.minion_stats) == 1
        assert len(reparsed.full_dps_skills) == 1
        assert reparsed.specs[0].secondary_ascend_class_id == 3
        assert reparsed.specs[0].overrides[0].effect_image == "Art/fx.png"
        assert reparsed.default_gem_level == 20
        assert reparsed.sort_gems_by_dps
        assert reparsed.show_alt_quality_gems
        assert reparsed.skill_set_titles.get(1) == "Main Skills"
        assert reparsed.import_link == "https://pobb.in/kitchen"
        assert reparsed.import_export_party == "party1"
        assert "Party" in reparsed.passthrough_sections
        assert "Calcs" in reparsed.passthrough_sections

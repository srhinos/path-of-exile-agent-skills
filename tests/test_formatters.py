from __future__ import annotations

import pytest

from poe.formatters import register_formatters
from poe.models.build.build import (
    BuildComparison,
    BuildMetadata,
    MutationResult,
    ValidationIssue,
    ValidationResult,
)
from poe.models.build.config import BuildConfig, ConfigEntry
from poe.models.build.gems import Gem, GemGroup
from poe.models.build.items import EquippedItem, ItemMod
from poe.models.build.jewels import EquippedJewel, JewelListResult
from poe.models.build.stats import StatBlock
from poe.models.build.tree import TreeSpecList, TreeSummary
from poe.models.ninja.economy import PriceResult
from poe.output import _format_human, _format_json

register_formatters()


class TestBuildMetadataFormatter:
    def test_human_differs_from_json(self):
        meta = BuildMetadata(name="Test", class_name="Witch", ascendancy="Necromancer", level=95)
        human = _format_human(meta)
        json_out = _format_json(meta)
        assert human != json_out

    def test_human_contains_name_and_class(self):
        meta = BuildMetadata(name="Test", class_name="Witch", ascendancy="Necromancer", level=95)
        human = _format_human(meta)
        assert "Test" in human
        assert "Necromancer" in human

    def test_file_path_shown(self):
        meta = BuildMetadata(
            name="Test", class_name="Witch", level=90, file_path="/builds/test.xml"
        )
        human = _format_human(meta)
        assert "/builds/test.xml" in human


class TestStatBlockFormatter:
    def test_human_differs_from_json(self):
        block = StatBlock(category="all", stats={"Life": 5000, "TotalDPS": 100000})
        human = _format_human(block)
        json_out = _format_json(block)
        assert human != json_out


class TestMutationResultFormatter:
    def test_excludes_warning_from_fields(self):
        m = MutationResult(status="ok", warning="Stats are stale", path="/test.xml")
        human = _format_human(m)
        assert "path: /test.xml" in human
        assert "[Stats are stale]" in human

    def test_no_warning(self):
        m = MutationResult(status="ok", path="/test.xml")
        human = _format_human(m)
        assert "path: /test.xml" in human
        assert "[" not in human


class TestEquippedItemFormatter:
    def test_basic_item(self):
        item = EquippedItem(
            slot="Helmet",
            name="Doom Crown",
            base_type="Hubris Circlet",
            rarity="RARE",
            id=1,
            text="",
        )
        human = _format_human(item)
        assert "[Helmet]" in human
        assert "Doom Crown" in human
        assert "Hubris Circlet" in human
        assert "RARE" in human

    def test_with_mods_and_defenses(self):
        item = EquippedItem(
            slot="Body Armour",
            name="Test Regalia",
            base_type="Vaal Regalia",
            rarity="RARE",
            energy_shield=300,
            quality=20,
            item_level=86,
            id=1,
            text="",
            implicits=[ItemMod(text="+50 to Life")],
            explicits=[
                ItemMod(text="+100 to Life"),
                ItemMod(text="+40% Cold Res", is_crafted=True),
                ItemMod(text="+30% Fire Res", is_fractured=True),
            ],
            prefix_slots=["IncreasedLife6", None, None],
            suffix_slots=["ColdResist4", None, None],
        )
        human = _format_human(item)
        assert "es=300" in human
        assert "item_level: 86" in human
        assert "(crafted)" in human
        assert "(fractured)" in human
        assert "2P / 2S" in human

    def test_unique_same_name_base(self):
        item = EquippedItem(
            slot="Belt",
            name="Headhunter",
            base_type="Headhunter",
            rarity="UNIQUE",
            id=1,
            text="",
        )
        human = _format_human(item)
        assert human.count("Headhunter") == 1

    def test_influences_shown(self):
        item = EquippedItem(
            slot="Helmet",
            name="Test",
            base_type="Hubris Circlet",
            influences=["Shaper", "Elder"],
            id=1,
            text="",
        )
        human = _format_human(item)
        assert "Shaper" in human
        assert "Elder" in human


class TestPriceResultFormatter:
    def test_basic_price(self):
        p = PriceResult(name="Divine Orb", chaos_value=300.0)
        human = _format_human(p)
        assert "Divine Orb" in human
        assert "300.0" in human

    def test_with_qualifiers(self):
        p = PriceResult(
            name="Awakened Enlighten",
            chaos_value=150000.0,
            divine_value=500.0,
            variant="5/23",
            gem_level=5,
            gem_quality=23,
            corrupted=True,
            listing_count=42,
            low_confidence=True,
        )
        human = _format_human(p)
        assert "5/23" in human
        assert "Lv5" in human
        assert "Q23" in human
        assert "corrupted" in human
        assert "Listings: 42" in human
        assert "low confidence" in human.lower()

    def test_small_value(self):
        p = PriceResult(name="Scroll", chaos_value=0.005)
        human = _format_human(p)
        assert "0.0050" in human

    def test_with_links(self):
        p = PriceResult(name="Carcass Jack", chaos_value=50.0, links=6)
        human = _format_human(p)
        assert "6L" in human


class TestGemGroupFormatter:
    def test_basic_group(self):
        g = GemGroup(
            slot="Helmet",
            gems=[
                Gem(name_spec="Glacial Cascade", level=21, quality=20),
                Gem(name_spec="Minefield Support", level=20, quality=0),
            ],
        )
        human = _format_human(g)
        assert "Helmet" in human
        assert "Glacial Cascade" in human
        assert "Lv21" in human
        assert "Q20" in human
        assert "Minefield Support" in human

    def test_disabled_group(self):
        g = GemGroup(
            slot="Weapon",
            enabled=False,
            gems=[Gem(name_spec="Shield Charge", level=1)],
        )
        human = _format_human(g)
        assert "(disabled)" in human

    def test_disabled_gem(self):
        g = GemGroup(
            slot="Body",
            gems=[Gem(name_spec="Fireball", level=20, enabled=False)],
        )
        human = _format_human(g)
        assert "(disabled)" in human

    def test_with_label(self):
        g = GemGroup(
            label="Main 6L",
            gems=[Gem(name_spec="Arc", level=20)],
        )
        human = _format_human(g)
        assert "Main 6L" in human


class TestValidationResultFormatter:
    def test_no_issues(self):
        v = ValidationResult(build="Test Build", issues=[], issue_count=0)
        human = _format_human(v)
        assert "Test Build" in human
        assert "No issues" in human

    def test_with_issues(self):
        v = ValidationResult(
            build="Test Build",
            issues=[
                ValidationIssue(
                    severity="critical", category="resistances", message="Fire uncapped"
                ),
                ValidationIssue(severity="high", category="life_pool", message="Low life"),
            ],
            issue_count=2,
        )
        human = _format_human(v)
        assert "2 issue" in human
        assert "[critical]" in human
        assert "Fire uncapped" in human
        assert "[high]" in human


class TestBuildComparisonFormatter:
    def test_shows_diffs_only(self):
        c = BuildComparison(
            build1=BuildMetadata(name="Build A"),
            build2=BuildMetadata(name="Build B"),
            stat_comparison={
                "Life": {"Build A": 3000.0, "Build B": 5000.0, "diff": 2000.0, "pct": 66.7},
                "Mana": {"Build A": 500.0, "Build B": 500.0, "diff": 0.0, "pct": None},
            },
            config_diff={"enemyIsBoss": {"Build A": "None", "Build B": "Boss"}},
        )
        human = _format_human(c)
        assert "Build A vs Build B" in human
        assert "Life" in human
        assert "2,000.0" in human
        assert "Mana" not in human
        assert "enemyIsBoss" in human

    def test_empty_comparison(self):
        c = BuildComparison(
            build1=BuildMetadata(name="A"),
            build2=BuildMetadata(name="B"),
        )
        human = _format_human(c)
        assert "A vs B" in human


class TestJewelListResultFormatter:
    def test_no_jewels(self):
        j = JewelListResult()
        human = _format_human(j)
        assert "No jewels" in human

    def test_with_jewels(self):
        j = JewelListResult(
            jewels=[
                EquippedJewel(
                    slot="Jewel 1",
                    name="Watcher's Eye",
                    base_type="Prismatic Jewel",
                    tree_node=26725,
                    id=1,
                    text="",
                ),
            ],
            cluster_jewels=[
                EquippedJewel(
                    slot="Jewel 2",
                    name="Large Cluster",
                    base_type="Large Cluster Jewel",
                    id=2,
                    text="",
                ),
            ],
        )
        human = _format_human(j)
        assert "Jewels (1)" in human
        assert "Watcher's Eye" in human
        assert "node 26725" in human
        assert "Cluster Jewels (1)" in human


class TestTreeSpecListFormatter:
    def test_basic(self):
        t = TreeSpecList(
            active_spec=1,
            specs=[
                TreeSummary(
                    index=1, title="Endgame", tree_version="3_25", node_count=120, active=True
                ),
                TreeSummary(index=2, title="Leveling", tree_version="3_25", node_count=45),
            ],
        )
        human = _format_human(t)
        assert "active: #1" in human
        assert "#1: Endgame" in human
        assert "120 nodes" in human
        assert "*" in human
        assert "#2: Leveling" in human
        assert "45 nodes" in human

    def test_untitled_spec(self):
        t = TreeSpecList(
            active_spec=1,
            specs=[TreeSummary(index=1, title="", tree_version="3_25", node_count=10)],
        )
        human = _format_human(t)
        assert "(untitled)" in human


class TestBuildConfigFormatter:
    def test_with_inputs(self):
        c = BuildConfig(
            id="2",
            title="Bossing",
            inputs=[
                ConfigEntry(name="usePowerCharges", value=True),
                ConfigEntry(name="enemyPhysicalHitDamage", value=5000.0, input_type="number"),
                ConfigEntry(name="customMod", value="extra damage", input_type="string"),
            ],
        )
        human = _format_human(c)
        assert "Bossing" in human
        assert "id=2" in human
        assert "usePowerCharges: true" in human
        assert "enemyPhysicalHitDamage: 5000" in human
        assert "customMod: extra damage" in human

    def test_empty_config(self):
        c = BuildConfig(id="1", title="Default")
        human = _format_human(c)
        assert "Default" in human
        assert "(no inputs)" in human


# ── Formatter structural invariants (Pattern 1) ─────────────────────────────


class TestFormatterStructureStable:
    def test_register_formatters_idempotent(self):
        register_formatters()
        register_formatters()

    @pytest.mark.parametrize(
        "model",
        [
            BuildMetadata(name="Test", class_name="Witch", level=90),
            StatBlock(category="all", stats={"Life": 5000.0}),
            MutationResult(status="ok", path="/x.xml"),
            ValidationResult(build="x"),
            BuildComparison(build1=BuildMetadata(name="A"), build2=BuildMetadata(name="B")),
            JewelListResult(),
            TreeSpecList(active_spec=1),
            BuildConfig(id="1", title="x"),
            PriceResult(name="Divine", chaos_value=200.0),
        ],
    )
    def test_human_output_is_string(self, model):
        out = _format_human(model)
        assert isinstance(out, str)
        assert out

    @pytest.mark.parametrize(
        "model",
        [
            BuildMetadata(name="Test", class_name="Witch", level=90),
            StatBlock(category="all", stats={"Life": 5000.0}),
            MutationResult(status="ok", path="/x.xml"),
            ValidationResult(build="x"),
        ],
    )
    def test_human_differs_from_json(self, model):
        human = _format_human(model)
        json_out = _format_json(model)
        assert human != json_out


class TestEquippedItemFormatterEdge:
    def test_armour_only(self):
        item = EquippedItem(
            slot="Body Armour",
            id=1,
            text="",
            rarity="RARE",
            armour=2000,
        )
        human = _format_human(item)
        assert "armour=2000" in human

    def test_evasion_and_ward(self):
        item = EquippedItem(
            slot="Body Armour",
            id=1,
            text="",
            rarity="RARE",
            evasion=1500,
            ward=300,
        )
        human = _format_human(item)
        assert "evasion=1500" in human
        assert "ward=300" in human

    def test_no_defenses_section_when_zero(self):
        item = EquippedItem(
            slot="Belt",
            id=1,
            text="",
            rarity="RARE",
            name="Plain Belt",
        )
        human = _format_human(item)
        assert "defenses:" not in human


class TestPriceResultFormatterEdge:
    def test_chaos_value_exactly_one(self):
        p = PriceResult(name="x", chaos_value=1.0)
        out = _format_human(p)
        assert "1.0" in out

    def test_chaos_value_below_one_uses_4_decimal(self):
        p = PriceResult(name="x", chaos_value=0.001)
        out = _format_human(p)
        assert "0.0010" in out

    def test_listing_count_zero_shown(self):
        p = PriceResult(name="x", chaos_value=1.0, listing_count=0)
        out = _format_human(p)
        assert "Listings: 0" in out

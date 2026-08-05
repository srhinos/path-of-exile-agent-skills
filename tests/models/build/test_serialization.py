import pytest

from poe.models.build import (
    BuildComparison,
    BuildConfig,
    BuildDocument,
    BuildMetadata,
    BuildNotes,
    ConfigEntry,
    EngineInfo,
    Flask,
    Gem,
    GemGroup,
    GemSet,
    GemSummary,
    Item,
    ItemDiff,
    ItemMod,
    ItemSet,
    ItemSlot,
    ItemSummary,
    Jewel,
    MasteryMapping,
    StatBlock,
    StatDiff,
    StatEntry,
    TreeDiff,
    TreeOverride,
    TreeSocket,
    TreeSpec,
    TreeSummary,
    ValidationIssue,
)
from poe.models.sim import (
    BenchCraft,
    CurrencyPrices,
    Essence,
    Fossil,
    IdentifiedMod,
    Mod,
    ModTier,
    ModWeight,
    SimulationResult,
)

# --- Tree models ---


class TestTreeModels:
    def test_mastery_mapping_roundtrip(self):
        m = MasteryMapping(node_id=100, effect_id=200)
        d = m.model_dump()
        assert d == {"node_id": 100, "effect_id": 200}
        assert MasteryMapping.model_validate(d) == m

    def test_tree_socket(self):
        s = TreeSocket(node_id=1, item_id=2)
        assert s.node_id == 1
        assert s.item_id == 2

    def test_tree_override(self):
        o = TreeOverride(node_id=1, name="test", icon="icon.png", text="desc")
        assert o.name == "test"

    def test_tree_spec_defaults(self):
        spec = TreeSpec()
        assert spec.nodes == []
        assert spec.mastery_effects == []
        assert spec.sockets == []

    def test_tree_spec_with_data(self):
        spec = TreeSpec(
            title="Main",
            tree_version="3_28",
            nodes=[100, 200, 300],
            class_id=1,
            ascend_class_id=2,
            mastery_effects=[MasteryMapping(node_id=100, effect_id=200)],
        )
        assert len(spec.nodes) == 3
        assert spec.mastery_effects[0].effect_id == 200
        j = spec.model_dump_json()
        rebuilt = TreeSpec.model_validate_json(j)
        assert rebuilt == spec

    def test_tree_summary(self):
        s = TreeSummary(index=1, title="Main", node_count=50, active=True)
        assert s.active is True

    def test_tree_diff(self):
        d = TreeDiff(added_nodes=[1, 2], removed_nodes=[3])
        assert len(d.added_nodes) == 2


# --- Item models ---


class TestItemModels:
    def test_item_mod_minimal(self):
        m = ItemMod(text="+50 to Maximum Life")
        assert m.text == "+50 to Maximum Life"
        assert m.is_crafted is False

    def test_item_mod_full(self):
        m = ItemMod(
            text="+50 to Maximum Life",
            mod_id="IncreasedLife6",
            is_prefix=True,
            is_crafted=True,
            tags=["life"],
            range_value=0.5,
        )
        d = m.model_dump(exclude_none=True)
        assert d["mod_id"] == "IncreasedLife6"
        assert d["tags"] == ["life"]

    def test_item_computed_fields(self):
        item = Item(
            id=1,
            text="test",
            rarity="RARE",
            prefix_slots=["IncreasedLife6", None, None],
            suffix_slots=["AddedFireRes4", None, None],
        )
        assert item.open_prefixes == 2
        assert item.open_suffixes == 2
        assert item.filled_prefixes == 1
        assert item.filled_suffixes == 1

    def test_item_serialization(self):
        item = Item(
            id=1,
            text="test",
            rarity="RARE",
            name="Test Ring",
            base_type="Coral Ring",
            influences=["Shaper"],
            implicits=[ItemMod(text="+30 to Maximum Life")],
        )
        j = item.model_dump_json()
        rebuilt = Item.model_validate_json(j)
        assert rebuilt.name == "Test Ring"
        assert rebuilt.influences == ["Shaper"]
        assert len(rebuilt.implicits) == 1

    def test_item_slot(self):
        s = ItemSlot(name="Ring 1", item_id=5)
        assert s.name == "Ring 1"

    def test_item_set(self):
        s = ItemSet(
            id="1",
            slots=[ItemSlot(name="Ring 1", item_id=5)],
        )
        assert len(s.slots) == 1

    def test_item_summary(self):
        s = ItemSummary(
            slot="Ring 1",
            name="Test Ring",
            base_type="Coral Ring",
            rarity="RARE",
        )
        assert s.slot == "Ring 1"

    def test_item_diff(self):
        d = ItemDiff(slot="Ring 1", field="name", old_value="Old", new_value="New")
        assert d.field == "name"


# --- Gem models ---


class TestGemModels:
    def test_gem_defaults(self):
        g = Gem(name_spec="Fireball")
        assert g.level == 20
        assert g.quality == 0
        assert g.quality_id == "Default"
        assert g.enabled is True

    def test_gem_group(self):
        group = GemGroup(
            slot="Body Armour",
            label="Main Setup",
            gems=[Gem(name_spec="Fireball"), Gem(name_spec="Spell Echo")],
        )
        assert len(group.gems) == 2

    def test_gem_set(self):
        gs = GemSet(id=1, groups=[GemGroup(label="test")])
        assert gs.id == 1

    def test_gem_summary(self):
        s = GemSummary(name="Fireball", level=21, quality=23)
        assert s.level == 21


class TestGemInvariants:
    def test_name_spec_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            Gem(name_spec="")

    def test_level_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            Gem(name_spec="Fireball", level=0)

    def test_level_rejects_above_40(self):
        with pytest.raises((ValueError, TypeError)):
            Gem(name_spec="Fireball", level=41)

    def test_quality_rejects_above_30(self):
        with pytest.raises((ValueError, TypeError)):
            Gem(name_spec="Fireball", quality=99)

    def test_quality_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            Gem(name_spec="Fireball", quality=-1)

    def test_count_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            Gem(name_spec="Fireball", count=0)

    def test_gem_summary_rejects_empty_name(self):
        with pytest.raises((ValueError, TypeError)):
            GemSummary(name="")

    def test_gem_group_main_active_skill_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            GemGroup(main_active_skill=0)


class TestFlaskInvariants:
    def test_slot_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            Flask(slot="", name="Divine Life Flask", base_type="Divine Life Flask")

    def test_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            Flask(slot="Flask 1", name="", base_type="Divine Life Flask")

    def test_base_type_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            Flask(slot="Flask 1", name="Divine Life Flask", base_type="")

    def test_quality_rejects_above_30(self):
        with pytest.raises((ValueError, TypeError)):
            Flask(
                slot="Flask 1",
                name="Divine Life Flask",
                base_type="Divine Life Flask",
                quality=99,
            )


class TestJewelInvariants:
    def test_item_id_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            Jewel(node_id=100, item_id=0)

    def test_item_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            Jewel(node_id=100, item_id=-1)

    def test_node_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            Jewel(node_id=-1, item_id=5)


class TestConfigInvariants:
    def test_config_entry_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            ConfigEntry(name="", value=True, input_type="boolean")

    def test_config_entry_input_type_rejects_unknown(self):
        with pytest.raises((ValueError, TypeError)):
            ConfigEntry(name="x", value="hi", input_type="garbage")

    def test_build_config_id_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            BuildConfig(id="")


# --- Flask, Jewel models ---


class TestFlaskJewelModels:
    def test_flask(self):
        f = Flask(slot="Flask 1", name="Divine Life Flask", base_type="Divine Life Flask")
        assert f.slot == "Flask 1"

    def test_jewel(self):
        j = Jewel(node_id=100, item_id=5, name="Cobalt Jewel")
        assert j.node_id == 100


# --- Config models ---


class TestConfigModels:
    def test_config_entry_boolean(self):
        e = ConfigEntry(name="useCharges", value=True, input_type="boolean")
        assert e.value is True

    def test_config_entry_number(self):
        e = ConfigEntry(name="enemyLevel", value=84, input_type="number")
        assert e.value == 84

    def test_build_config(self):
        bc = BuildConfig(
            id="1",
            title="Default",
            inputs=[ConfigEntry(name="test", value=True)],
        )
        assert len(bc.inputs) == 1


# --- Stat models ---


class TestStatModels:
    def test_stat_entry(self):
        s = StatEntry(stat="Life", value=5000)
        assert s.stat == "Life"

    def test_stat_block(self):
        sb = StatBlock(category="def", stats={"Life": 5000, "EnergyShield": 1000})
        assert sb.stats["Life"] == 5000

    def test_stat_diff(self):
        d = StatDiff(stat="Life", value1=5000, value2=6000, diff=1000, pct=20.0)
        assert d.diff == 1000


# --- Build models ---


class TestBuildModels:
    def test_build_metadata(self):
        m = BuildMetadata(name="test", class_name="Witch", ascendancy="Necromancer", level=95)
        d = m.model_dump()
        assert d["name"] == "test"
        assert d["class_name"] == "Witch"

    def test_build_notes(self):
        n = BuildNotes(build_name="test", notes="some notes")
        assert n.notes == "some notes"

    def test_validation_issue(self):
        v = ValidationIssue(severity="critical", category="resistances", message="Fire res low")
        assert v.severity == "critical"

    def test_build_document_minimal(self):
        doc = BuildDocument()
        assert doc.class_name == ""
        assert doc.level == 1
        assert doc.items == []

    def test_build_document_get_stat(self):
        doc = BuildDocument(
            player_stats=[StatEntry(stat="Life", value=5000), StatEntry(stat="Mana", value=1000)]
        )
        assert doc.get_stat("Life") == 5000
        assert doc.get_stat("Missing") is None

    def test_build_document_get_active_spec(self):
        spec1 = TreeSpec(title="Spec 1")
        spec2 = TreeSpec(title="Spec 2")
        doc = BuildDocument(specs=[spec1, spec2], active_spec=2)
        assert doc.get_active_spec() == spec2

    def test_build_document_get_active_spec_empty(self):
        doc = BuildDocument()
        assert doc.get_active_spec() is None

    def test_build_document_get_active_config(self):
        cfg = BuildConfig(id="2", title="Boss")
        doc = BuildDocument(config_sets=[cfg], active_config_set="2")
        assert doc.get_active_config() == cfg

    def test_build_document_get_active_config_fallback(self):
        cfg = BuildConfig(id="1")
        doc = BuildDocument(config_sets=[cfg], active_config_set="99")
        assert doc.get_active_config() == cfg

    def test_build_document_get_equipped_items(self):
        item = Item(id=5, text="test", name="Ring", base_type="Coral Ring")
        item_set = ItemSet(id="1", slots=[ItemSlot(name="Ring 1", item_id=5)])
        doc = BuildDocument(items=[item], item_sets=[item_set])
        equipped = doc.get_equipped_items()
        assert len(equipped) == 1
        assert equipped[0][0] == "Ring 1"
        assert equipped[0][1].name == "Ring"

    def test_build_document_get_equipped_items_empty(self):
        doc = BuildDocument()
        assert doc.get_equipped_items() == []

    def test_build_comparison(self):
        c = BuildComparison(
            build1=BuildMetadata(name="build1"),
            build2=BuildMetadata(name="build2"),
        )
        assert c.build1.name == "build1"

    def test_build_document_full_serialization(self):
        doc = BuildDocument(
            class_name="Witch",
            ascend_class_name="Necromancer",
            level=95,
            player_stats=[StatEntry(stat="Life", value=5000)],
            specs=[TreeSpec(title="Main", nodes=[1, 2, 3])],
            skill_groups=[
                GemGroup(
                    label="Main",
                    gems=[Gem(name_spec="Fireball")],
                )
            ],
            items=[Item(id=1, text="test", name="Ring")],
            item_sets=[ItemSet(id="1", slots=[ItemSlot(name="Ring 1", item_id=1)])],
            config_sets=[BuildConfig(id="1", inputs=[ConfigEntry(name="test", value=True)])],
        )
        j = doc.model_dump_json()
        rebuilt = BuildDocument.model_validate_json(j)
        assert rebuilt.class_name == "Witch"
        assert rebuilt.level == 95
        assert len(rebuilt.specs) == 1
        assert len(rebuilt.skill_groups) == 1
        assert len(rebuilt.items) == 1


# --- Craft models ---


class TestCraftModels:
    def test_mod_weight(self):
        mw = ModWeight(tag="fire", multiplier=1.5)
        assert mw.tag == "fire"

    def test_mod(self):
        m = Mod(mod_id="test", name="Test Mod", affix="prefix", group="Life", weight=1000)
        assert m.weight == 1000

    def test_mod_tier(self):
        t = ModTier(tier=1, ilvl=84, values=[[50, 60]], weight=1000)
        assert t.tier == 1

    def test_fossil(self):
        f = Fossil(name="Pristine", mod_weights={"life": 1.5}, blocked=["attack"])
        assert f.blocked == ["attack"]

    def test_essence(self):
        e = Essence(name="Deafening Essence of Contempt", tier="Deafening")
        assert "Contempt" in e.name

    def test_bench_craft(self):
        bc = BenchCraft(name="% increased Maximum Life", mod="+50 to Maximum Life")
        assert bc.name == "% increased Maximum Life"

    def test_currency_prices(self):
        p = CurrencyPrices(currency={"exalt": 150.0, "divine": 200.0})
        assert p.currency["divine"] == 200.0

    def test_identified_mod(self):
        m = IdentifiedMod(text="+50 to Life", mod_id="IncreasedLife6", tier=1, affix="prefix")
        assert m.tier == 1


# --- Engine models ---


class TestEngineModels:
    def test_engine_info(self):
        info = EngineInfo(pob_path="/path/to/pob", initialized=True)
        assert info.initialized is True


# --- Re-export test ---


class TestReExports:
    def test_all_models_importable_from_package(self):
        from poe.models.build import __all__

        assert len(__all__) >= 40


# ── Pydantic semantic invariants for sim models (Pattern 5) ─────────────────
#
# These tests assert constraints that should hold for sim model fields.
# Many use xfail(strict=True) — these document gaps where model_validators
# do not yet exist in production code. Production should NOT be modified.


class TestSimulationResultInvariants:
    def test_minimum_construction(self):
        r = SimulationResult(base="Hubris Circlet", ilvl=84, method="chaos", targets=["Life"])
        assert r.base == "Hubris Circlet"

    def test_avg_attempts_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                avg_attempts=float("nan"),
            )

    def test_avg_attempts_rejects_inf(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                avg_attempts=float("inf"),
            )

    def test_avg_attempts_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                avg_attempts=-5.0,
            )

    def test_cost_per_attempt_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                cost_per_attempt=float("nan"),
            )

    def test_avg_cost_chaos_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                avg_cost_chaos=float("nan"),
            )

    def test_iterations_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                iterations=-1,
            )

    def test_ilvl_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(base="Hubris Circlet", ilvl=-5, method="chaos", targets=["Life"])

    def test_ilvl_rejects_above_100(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(base="Hubris Circlet", ilvl=999, method="chaos", targets=["Life"])

    def test_method_rejects_unknown(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="bogus_method_does_not_exist",
                targets=["Life"],
            )

    def test_hit_rate_rejects_arbitrary_string(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                hit_rate="not a percentage",
            )

    def test_match_mode_rejects_unknown(self):
        with pytest.raises((ValueError, TypeError)):
            SimulationResult(
                base="Hubris Circlet",
                ilvl=84,
                method="chaos",
                targets=["Life"],
                match_mode="impossible_mode",
            )


class TestModInvariants:
    def test_minimal_construction(self):
        m = Mod(mod_id="x", name="x", affix="prefix", group="g", weight=100)
        assert m.weight == 100

    def test_weight_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            Mod(mod_id="x", name="x", affix="prefix", group="g", weight=-100)

    def test_affix_rejects_unknown(self):
        with pytest.raises((ValueError, TypeError)):
            Mod(mod_id="x", name="x", affix="not-an-affix", group="g", weight=100)

    def test_zero_weight_currently_accepted(self):
        m = Mod(mod_id="x", name="x", affix="prefix", group="g", weight=0)
        assert m.weight == 0


class TestModTierInvariants:
    def test_tier_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            ModTier(tier=0, ilvl=84)

    def test_weight_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            ModTier(tier=1, ilvl=84, weight=-1)

    def test_ilvl_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            ModTier(tier=1, ilvl=-1)


class TestModWeightInvariants:
    def test_multiplier_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            ModWeight(tag="fire", multiplier=float("nan"))

    def test_multiplier_rejects_neg_inf(self):
        with pytest.raises((ValueError, TypeError)):
            ModWeight(tag="fire", multiplier=float("-inf"))

    def test_tag_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            ModWeight(tag="", multiplier=1.0)


class TestFossilInvariants:
    def test_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            Fossil(name="")

    def test_mod_weights_value_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            Fossil(name="Pristine", mod_weights={"life": float("nan")})


class TestEssenceInvariants:
    def test_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            Essence(name="")


class TestBenchCraftInvariants:
    def test_name_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            BenchCraft(name="")


class TestIdentifiedModInvariants:
    def test_tier_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            IdentifiedMod(text="+50 Life", tier=-1)

    def test_affix_rejects_unknown_when_set(self):
        with pytest.raises((ValueError, TypeError)):
            IdentifiedMod(text="+50 Life", affix="weird")

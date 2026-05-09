from __future__ import annotations

import pytest

from poe.models.build import BuildDocument, Item, ItemSet, ItemSlot, StatEntry
from poe.services.build.validation import validate_build


def _build_with_stats(**kwargs) -> BuildDocument:
    """Create a BuildDocument with given stat name=value pairs."""
    stats = [StatEntry(stat=k, value=v) for k, v in kwargs.items()]
    return BuildDocument(player_stats=stats)


def _build_with_flasks(**kwargs) -> BuildDocument:
    stats = [StatEntry(stat=k, value=v) for k, v in kwargs.items()]
    flask_data = [
        ("Eternal Life Flask", "Eternal Life Flask"),
        ("Diamond Flask", "Diamond Flask"),
        ("Quicksilver Flask", "Quicksilver Flask"),
        ("Basalt Flask", "Basalt Flask"),
        ("Jade Flask", "Jade Flask"),
    ]
    gear_data = [
        ("Helmet", "Hubris Circlet"),
        ("Body Armour", "Vaal Regalia"),
        ("Gloves", "Sorcerer Gloves"),
        ("Boots", "Sorcerer Boots"),
        ("Amulet", "Onyx Amulet"),
        ("Ring 1", "Coral Ring"),
        ("Ring 2", "Coral Ring"),
        ("Belt", "Leather Belt"),
    ]
    items = [
        Item(id=i + 1, text="", base_type=bt, name=n, rarity="MAGIC")
        for i, (bt, n) in enumerate(flask_data)
    ]
    gear_items = [
        Item(id=i + 100, text="", base_type=bt, name=bt, rarity="RARE")
        for i, (_, bt) in enumerate(gear_data)
    ]
    items.extend(gear_items)
    slots = [ItemSlot(name=f"Flask {i}", item_id=i) for i in range(1, 6)]
    gear_slots = [
        ItemSlot(name=slot_name, item_id=i + 100) for i, (slot_name, _) in enumerate(gear_data)
    ]
    slots.extend(gear_slots)
    return BuildDocument(
        player_stats=stats,
        items=items,
        item_sets=[ItemSet(id="1", slots=slots)],
        active_item_set="1",
    )


# ── Resistance checks ────────────────────────────────────────────────────────


class TestResistanceValidation:
    def test_resists_capped(self):
        build = _build_with_stats(
            FireResist=75,
            ColdResist=75,
            LightningResist=75,
            Life=5000,
            EnergyShield=0,
        )
        issues = validate_build(build)
        resist_issues = [i for i in issues if i.category == "resistances"]
        assert resist_issues == []

    def test_fire_resist_uncapped(self):
        build = _build_with_stats(
            FireResist=60,
            ColdResist=75,
            LightningResist=75,
            Life=5000,
        )
        issues = validate_build(build)
        resist_issues = [i for i in issues if "Fire" in i.message]
        assert len(resist_issues) == 1
        assert resist_issues[0].severity == "critical"

    def test_cold_resist_uncapped(self):
        build = _build_with_stats(
            FireResist=75,
            ColdResist=50,
            LightningResist=75,
            Life=5000,
        )
        issues = validate_build(build)
        resist_issues = [i for i in issues if "Cold" in i.message]
        assert len(resist_issues) == 1

    def test_lightning_resist_uncapped(self):
        build = _build_with_stats(
            FireResist=75,
            ColdResist=75,
            LightningResist=40,
            Life=5000,
        )
        issues = validate_build(build)
        resist_issues = [i for i in issues if "Lightning" in i.message]
        assert len(resist_issues) == 1

    def test_chaos_resist_negative(self):
        build = _build_with_stats(
            FireResist=75,
            ColdResist=75,
            LightningResist=75,
            ChaosResist=-30,
            Life=5000,
        )
        issues = validate_build(build)
        chaos_issues = [i for i in issues if "Chaos" in i.message]
        assert len(chaos_issues) == 1
        assert chaos_issues[0].severity == "high"

    def test_chaos_resist_positive_ok(self):
        build = _build_with_stats(
            FireResist=75,
            ColdResist=75,
            LightningResist=75,
            ChaosResist=30,
            Life=5000,
        )
        issues = validate_build(build)
        chaos_issues = [i for i in issues if "Chaos" in i.message]
        assert chaos_issues == []


# ── Life pool checks ─────────────────────────────────────────────────────────


class TestLifePoolValidation:
    def test_critical_low_life(self):
        build = _build_with_stats(Life=1500, EnergyShield=0)
        issues = validate_build(build)
        life_issues = [i for i in issues if i.category == "life_pool"]
        assert len(life_issues) == 1
        assert life_issues[0].severity == "critical"

    def test_warning_low_life(self):
        build = _build_with_stats(Life=3000, EnergyShield=0)
        issues = validate_build(build)
        life_issues = [i for i in issues if i.category == "life_pool"]
        assert len(life_issues) == 1
        assert life_issues[0].severity == "high"

    def test_adequate_life(self):
        build = _build_with_stats(Life=5000, EnergyShield=0)
        issues = validate_build(build)
        life_issues = [i for i in issues if i.category == "life_pool"]
        assert life_issues == []

    def test_es_contributes_to_pool(self):
        # Low life but high ES — total HP should pass
        build = _build_with_stats(Life=1000, EnergyShield=5000)
        issues = validate_build(build)
        life_issues = [i for i in issues if i.category == "life_pool"]
        assert life_issues == []

    def test_no_life_stat(self):
        # No Life/ES stats at all — defaults to 0
        build = BuildDocument()
        issues = validate_build(build)
        life_issues = [i for i in issues if i.category == "life_pool"]
        assert len(life_issues) == 1
        assert life_issues[0].severity == "critical"


# ── Spell suppression ────────────────────────────────────────────────────────


class TestSpellSuppressionValidation:
    def test_partial_suppression(self):
        build = _build_with_stats(
            EffectiveSpellSuppressionChance=60,
            Life=5000,
        )
        issues = validate_build(build)
        supp_issues = [i for i in issues if "suppression" in i.message.lower()]
        assert len(supp_issues) == 1
        assert supp_issues[0].severity == "medium"

    def test_full_suppression(self):
        build = _build_with_stats(
            EffectiveSpellSuppressionChance=100,
            Life=5000,
        )
        issues = validate_build(build)
        supp_issues = [i for i in issues if "suppression" in i.message.lower()]
        assert supp_issues == []

    def test_no_suppression(self):
        build = _build_with_stats(Life=5000)
        issues = validate_build(build)
        supp_issues = [i for i in issues if "suppression" in i.message.lower()]
        assert supp_issues == []

    def test_zero_suppression_no_warning(self):
        build = _build_with_stats(
            EffectiveSpellSuppressionChance=0,
            Life=5000,
        )
        issues = validate_build(build)
        supp_issues = [i for i in issues if "suppression" in i.message.lower()]
        assert supp_issues == []


# ── Block validation ─────────────────────────────────────────────────────────


class TestBlockValidation:
    def test_block_without_spell_block(self):
        build = _build_with_stats(
            EffectiveBlockChance=50,
            EffectiveSpellBlockChance=10,
            Life=5000,
        )
        issues = validate_build(build)
        block_issues = [i for i in issues if "block" in i.message.lower()]
        assert len(block_issues) == 1
        assert block_issues[0].severity == "medium"

    def test_balanced_block(self):
        build = _build_with_stats(
            EffectiveBlockChance=50,
            EffectiveSpellBlockChance=40,
            Life=5000,
        )
        issues = validate_build(build)
        block_issues = [i for i in issues if "block" in i.message.lower()]
        assert block_issues == []

    def test_no_block(self):
        build = _build_with_stats(Life=5000)
        issues = validate_build(build)
        block_issues = [i for i in issues if "block" in i.message.lower()]
        assert block_issues == []


# ── Attribute validation ─────────────────────────────────────────────────────


class TestAttributeValidation:
    def test_str_insufficient(self):
        build = _build_with_stats(Str=100, ReqStr=155, Life=5000)
        issues = validate_build(build)
        attr_issues = [i for i in issues if i.category == "attributes"]
        assert len(attr_issues) == 1
        assert "Str" in attr_issues[0].message

    def test_attributes_sufficient(self):
        build = _build_with_stats(
            Str=200,
            ReqStr=155,
            Dex=200,
            ReqDex=100,
            Int=300,
            ReqInt=200,
            Life=5000,
        )
        issues = validate_build(build)
        attr_issues = [i for i in issues if i.category == "attributes"]
        assert attr_issues == []


# ── Compound scenarios ───────────────────────────────────────────────────────


class TestCompoundValidation:
    def test_all_good(self):
        build = _build_with_flasks(
            FireResist=75,
            ColdResist=75,
            LightningResist=75,
            ChaosResist=30,
            Life=5000,
            EnergyShield=1000,
            EffectiveSpellSuppressionChance=100,
            Str=200,
            ReqStr=100,
            Dex=200,
            ReqDex=100,
            Int=200,
            ReqInt=100,
        )
        issues = validate_build(build)
        assert issues == []

    def test_multiple_issues(self):
        build = _build_with_stats(
            FireResist=50,
            ColdResist=40,
            LightningResist=30,
            ChaosResist=-60,
            Life=1500,
            EnergyShield=0,
            EffectiveSpellSuppressionChance=50,
            EffectiveBlockChance=40,
            EffectiveSpellBlockChance=5,
        )
        issues = validate_build(build)
        # Should have: 3 resist, 1 chaos, 1 life, 1 suppress, 1 block, 1 flask = 8
        assert len(issues) >= 7

    def test_empty_build(self):
        build = BuildDocument()
        issues = validate_build(build)
        life_issues = [i for i in issues if i.category == "life_pool"]
        assert len(life_issues) >= 1


class TestAccuracyValidation:
    def test_low_hit_chance(self):
        build = _build_with_stats(HitChance=75, Life=5000)
        issues = validate_build(build)
        acc_issues = [i for i in issues if i.category == "accuracy"]
        assert len(acc_issues) == 1
        assert acc_issues[0].severity == "high"

    def test_good_hit_chance(self):
        build = _build_with_stats(HitChance=95, Life=5000)
        issues = validate_build(build)
        acc_issues = [i for i in issues if i.category == "accuracy"]
        assert acc_issues == []


class TestManaValidation:
    def test_mana_cost_exceeds_regen(self):
        build = _build_with_stats(ManaPerSecondCost=100, ManaRegenRecovery=50, Life=5000)
        issues = validate_build(build)
        mana_issues = [i for i in issues if i.category == "mana"]
        assert len(mana_issues) == 1

    def test_mana_sustainable(self):
        build = _build_with_stats(ManaPerSecondCost=50, ManaRegenRecovery=100, Life=5000)
        issues = validate_build(build)
        mana_issues = [i for i in issues if i.category == "mana"]
        assert mana_issues == []


class TestAilmentValidation:
    def test_partial_freeze_avoidance(self):
        build = _build_with_stats(AvoidFreeze=60, Life=5000)
        issues = validate_build(build)
        ailment_issues = [i for i in issues if i.category == "ailments"]
        assert len(ailment_issues) == 1

    def test_full_freeze_immunity(self):
        build = _build_with_stats(AvoidFreeze=100, Life=5000)
        issues = validate_build(build)
        ailment_issues = [i for i in issues if "Freeze" in i.message]
        assert ailment_issues == []


class TestGearValidation:
    def test_empty_gear_slots(self):
        build = _build_with_stats(Life=5000)
        issues = validate_build(build)
        gear_issues = [i for i in issues if i.category == "gear"]
        assert len(gear_issues) == 1
        assert "Helmet" in gear_issues[0].message

    def test_full_gear_no_issue(self):
        build = _build_with_flasks(Life=5000)
        issues = validate_build(build)
        gear_issues = [i for i in issues if i.category == "gear"]
        assert gear_issues == []


class TestOvercappedResistance:
    def test_overcapped_fire(self):
        build = _build_with_stats(
            FireResist=75,
            FireResistOverCap=120,
            ColdResist=75,
            LightningResist=75,
            Life=5000,
        )
        issues = validate_build(build)
        overcap = [i for i in issues if "overcapped" in i.message]
        assert len(overcap) == 1

    def test_not_overcapped(self):
        build = _build_with_stats(
            FireResist=75,
            FireResistOverCap=30,
            ColdResist=75,
            LightningResist=75,
            Life=5000,
        )
        issues = validate_build(build)
        overcap = [i for i in issues if "overcapped" in i.message]
        assert overcap == []


class TestMovementSpeed:
    def test_no_movement_speed_bonus(self):
        build = _build_with_stats(EffectiveMovementSpeedMod=0, Life=5000)
        issues = validate_build(build)
        move_issues = [i for i in issues if i.category == "movement"]
        assert len(move_issues) == 1

    def test_has_movement_speed(self):
        build = _build_with_stats(EffectiveMovementSpeedMod=30, Life=5000)
        issues = validate_build(build)
        move_issues = [i for i in issues if i.category == "movement"]
        assert move_issues == []


class TestEachAilmentValidation:
    @pytest.mark.parametrize("ailment", ["Freeze", "Ignite", "Shock"])
    def test_partial_avoidance_warns(self, ailment):
        build = _build_with_stats(Life=5000, **{f"Avoid{ailment}": 60})
        issues = validate_build(build)
        ailment_issues = [i for i in issues if ailment in i.message]
        assert len(ailment_issues) == 1
        assert ailment_issues[0].severity == "medium"

    @pytest.mark.parametrize("ailment", ["Freeze", "Ignite", "Shock"])
    def test_full_avoidance_clean(self, ailment):
        build = _build_with_stats(Life=5000, **{f"Avoid{ailment}": 100})
        issues = validate_build(build)
        ailment_issues = [i for i in issues if ailment in i.message]
        assert ailment_issues == []

    @pytest.mark.parametrize("ailment", ["Freeze", "Ignite", "Shock"])
    def test_zero_avoidance_no_warning(self, ailment):
        build = _build_with_stats(Life=5000, **{f"Avoid{ailment}": 0})
        issues = validate_build(build)
        ailment_issues = [i for i in issues if ailment in i.message]
        assert ailment_issues == []


class TestEachResistanceParametrized:
    @pytest.mark.parametrize("res", ["Fire", "Cold", "Lightning"])
    def test_each_resist_uncapped_critical(self, res):
        kwargs = {"Life": 5000, f"{res}Resist": 70}
        for other in {"Fire", "Cold", "Lightning"} - {res}:
            kwargs[f"{other}Resist"] = 75
        build = _build_with_stats(**kwargs)
        issues = validate_build(build)
        matching = [i for i in issues if res in i.message and "overcapped" not in i.message]
        assert len(matching) == 1
        assert matching[0].severity == "critical"

    @pytest.mark.parametrize("res", ["Fire", "Cold", "Lightning"])
    def test_each_resist_overcapped_medium(self, res):
        kwargs = {"Life": 5000}
        for other in ("Fire", "Cold", "Lightning"):
            kwargs[f"{other}Resist"] = 75
        kwargs[f"{res}ResistOverCap"] = 120
        build = _build_with_stats(**kwargs)
        issues = validate_build(build)
        overcap_issues = [i for i in issues if "overcapped" in i.message and res in i.message]
        assert len(overcap_issues) == 1
        assert overcap_issues[0].severity == "medium"


class TestEachAttributeValidation:
    @pytest.mark.parametrize(
        ("attr", "req_attr"),
        [("Str", "ReqStr"), ("Dex", "ReqDex"), ("Int", "ReqInt")],
    )
    def test_each_attribute_insufficient(self, attr, req_attr):
        build = _build_with_stats(Life=5000, **{attr: 100, req_attr: 200})
        issues = validate_build(build)
        attr_issues = [i for i in issues if attr in i.message]
        assert len(attr_issues) == 1
        assert attr_issues[0].severity == "critical"


class TestNoLifeFlaskWarning:
    def test_no_life_flask_warns(self):
        items = [
            Item(id=1, text="", base_type="Diamond Flask", rarity="MAGIC"),
            Item(id=2, text="", base_type="Quicksilver Flask", rarity="MAGIC"),
        ]
        slots = [
            ItemSlot(name="Flask 1", item_id=1),
            ItemSlot(name="Flask 2", item_id=2),
        ]
        build = BuildDocument(
            player_stats=[StatEntry(stat="Life", value=5000)],
            items=items,
            item_sets=[ItemSet(id="1", slots=slots)],
            active_item_set="1",
        )
        issues = validate_build(build)
        flask_issues = [i for i in issues if "Life Flask" in i.message]
        assert len(flask_issues) == 1
        assert flask_issues[0].severity == "medium"


class TestFewerThanFiveFlasksWarning:
    def test_fewer_than_5_flasks(self):
        items = [
            Item(id=1, text="", base_type="Eternal Life Flask", rarity="MAGIC"),
            Item(id=2, text="", base_type="Diamond Flask", rarity="MAGIC"),
        ]
        slots = [
            ItemSlot(name="Flask 1", item_id=1),
            ItemSlot(name="Flask 2", item_id=2),
        ]
        build = BuildDocument(
            player_stats=[StatEntry(stat="Life", value=5000)],
            items=items,
            item_sets=[ItemSet(id="1", slots=slots)],
            active_item_set="1",
        )
        issues = validate_build(build)
        flask_count_issues = [i for i in issues if "Fewer than 5 flasks" in i.message]
        assert len(flask_count_issues) == 1


class TestStunAvoidance:
    def test_partial_stun_avoidance_warns(self):
        build = _build_with_stats(Life=5000, StunAvoidChance=30)
        issues = validate_build(build)
        stun = [i for i in issues if "Stun" in i.message]
        assert len(stun) == 1
        assert stun[0].severity == "medium"

    def test_full_stun_avoidance_no_warn(self):
        # threshold is 50; >=50 not warned
        build = _build_with_stats(Life=5000, StunAvoidChance=50)
        issues = validate_build(build)
        stun = [i for i in issues if "Stun" in i.message]
        assert stun == []


class TestZeroValuesNoSpuriousWarnings:
    def test_zero_block_no_warn(self):
        build = _build_with_stats(Life=5000, EffectiveBlockChance=0)
        issues = validate_build(build)
        block_issues = [i for i in issues if "block" in i.message.lower()]
        assert block_issues == []

    def test_zero_hit_chance_warns(self):
        build = _build_with_stats(Life=5000, HitChance=0)
        issues = validate_build(build)
        acc_issues = [i for i in issues if i.category == "accuracy"]
        assert len(acc_issues) == 1


class TestValidationIssueSeverityValues:
    def test_severity_categories_known(self):
        build = _build_with_stats(
            FireResist=50,
            ColdResist=50,
            LightningResist=50,
            ChaosResist=-30,
            Life=1500,
            EnergyShield=0,
        )
        issues = validate_build(build)
        for i in issues:
            assert i.severity in {"critical", "high", "medium", "low"}
            assert i.category
            assert i.message

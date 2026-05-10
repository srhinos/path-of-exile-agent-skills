from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from poe.models.build.items import ItemMod
from poe.services.build.xml.parser import parse_build_file
from tests.conftest import PoBXmlBuilder


@pytest.fixture()
def pob_builder(tmp_path: Path) -> PoBXmlBuilder:
    return PoBXmlBuilder(tmp_path)


# ── Generated builds ─────────────────────────────────────────────────────────


def _create_necromancer_build(d: Path) -> Path:
    """Necromancer with influences, crafted mods, cluster jewels, abyss jewels."""
    builder = PoBXmlBuilder(d)
    return (
        builder.with_class("Witch", "Necromancer", 95)
        .with_stat("Life", 4500)
        .with_stat("EnergyShield", 2000)
        .with_stat("TotalDPS", 500000)
        .with_stat("FireResist", 75)
        .with_stat("ColdResist", 75)
        .with_stat("LightningResist", 75)
        .with_stat("ChaosResist", 30)
        .with_tree_spec(
            "Main",
            [100, 200, 300, 400, 500],
            masteries=[(53188, 64875), (53738, 29161)],
            class_id=5,
            ascend_class_id=2,
            sockets=[(26725, 1), (36634, 2)],
            url="https://example.com/necro_tree",
        )
        .with_item(
            "Helmet",
            rarity="RARE",
            name="Doom Crown",
            base_type="Hubris Circlet",
            energy_shield=200,
            quality=20,
            sockets="B-B-B-B",
            level_req=69,
            influences=["Shaper"],
            implicits=[
                ItemMod(text="+(50-70) to maximum Life", tags=["resource", "life"], range_value=0.5)
            ],
            explicits=[
                ItemMod(text="+90 to maximum Life", range_value=0.5),
                ItemMod(text="+40% to Cold Resistance", range_value=0.5),
            ],
            prefix_slots=["IncreasedLife6", "SpellDamage3", None],
            suffix_slots=["ColdResistance5", "LightningResistance4", None],
        )
        .with_item(
            "Body Armour",
            rarity="RARE",
            name="Soul Shell",
            base_type="Vaal Regalia",
            energy_shield=400,
            quality=20,
            is_crafted=True,
            implicits=[],
            explicits=[
                ItemMod(text="+100 to maximum Life"),
                ItemMod(text="+15% to all Elemental Resistances", is_crafted=True),
            ],
        )
        .with_item(
            "Jewel 1",
            rarity="RARE",
            name="Large Cluster Jewel",
            base_type="Large Cluster Jewel",
            implicits=[ItemMod(text="Adds 12 Passive Skills")],
            explicits=[ItemMod(text="1 Added Passive Skill is Rotten Claws")],
        )
        .with_item(
            "Abyssal Socket 1",
            rarity="RARE",
            name="Ghastly Eye Jewel",
            base_type="Ghastly Eye Jewel",
            implicits=[],
            explicits=[ItemMod(text="Minions deal 10 to 15 additional Physical Damage")],
        )
        .with_skill_group(
            "Body Armour",
            gems=[
                {
                    "name_spec": "Raise Spectre",
                    "level": 21,
                    "quality": 20,
                    "skill_minion": "SolarGuard",
                },
                {"name_spec": "Spell Echo Support", "level": 20, "quality": 20},
                {"name_spec": "Minion Damage Support", "level": 20, "quality": 20},
            ],
            include_in_full_dps=True,
        )
        .with_skill_group(
            "Helmet",
            gems=[
                {"name_spec": "Vaal Haste", "level": 21, "quality": 0, "enabled": False},
            ],
        )
        .with_config(
            useFrenzyCharges=True, enemyCondNearbyRareCruiser=True, enemyPhysicalHitDamage=5000
        )
        .with_notes("Necromancer build for integration tests")
        .with_import_link("https://pobb.in/necro123")
        .write("necromancer.xml")
    )


def _create_deadeye_build(d: Path) -> Path:
    """Deadeye with exarch/eater mods, weapons, flasks, multiple specs."""
    builder = PoBXmlBuilder(d)
    return (
        builder.with_class("Ranger", "Deadeye", 100)
        .with_stat("Life", 5000)
        .with_stat("EnergyShield", 0)
        .with_stat("TotalDPS", 2000000)
        .with_stat("FireResist", 75)
        .with_stat("ColdResist", 75)
        .with_stat("LightningResist", 75)
        .with_stat("ChaosResist", -30)
        .with_stat("Evasion", 30000)
        .with_stat("EffectiveSpellSuppressionChance", 100)
        .with_tree_spec(
            "Mapping",
            [1000, 1001, 1002, 1003],
            masteries=[(10000, 20000)],
            class_id=2,
            ascend_class_id=1,
            version="3_25",
        )
        .with_tree_spec(
            "Bossing",
            [2000, 2001, 2002, 2003, 2004],
            masteries=[(10000, 20000), (10001, 20001)],
            class_id=2,
            ascend_class_id=1,
            version="3_25",
        )
        .with_item(
            "Weapon 1",
            rarity="RARE",
            name="Tempest Reach",
            base_type="Spine Bow",
            evasion=0,
            quality=20,
            influences=["Searing Exarch"],
            implicits=[
                ItemMod(text="5% increased Attack Speed", is_exarch=True),
                ItemMod(text="3% increased Area of Effect", is_eater=True),
            ],
            explicits=[ItemMod(text="Adds 50 to 100 Cold Damage")],
        )
        .with_item(
            "Flask 1",
            rarity="MAGIC",
            name="Experimenter's Diamond Flask",
            base_type="Diamond Flask",
            implicits=[],
            explicits=[ItemMod(text="Lucky Critical Strike Chance")],
        )
        .with_item(
            "Ring 1",
            rarity="RARE",
            name="Sol Band",
            base_type="Diamond Ring",
            implicits=[ItemMod(text="+30 to all Attributes")],
            explicits=[ItemMod(text="+70 to maximum Life")],
        )
        .with_item(
            "Amulet",
            rarity="UNIQUE",
            name="Hyrri's Truth",
            base_type="Jade Amulet",
            implicits=[ItemMod(text="+30 to Dexterity")],
            explicits=[ItemMod(text="Adds 25 to 50 Cold Damage to Attacks")],
        )
        .with_item(
            "Belt",
            rarity="RARE",
            name="Storm Strap",
            base_type="Leather Belt",
            implicits=[ItemMod(text="+40 to maximum Life")],
            explicits=[ItemMod(text="+90 to maximum Life")],
        )
        .with_item(
            "Jewel 1",
            rarity="RARE",
            name="Viridian Jewel",
            base_type="Viridian Jewel",
            implicits=[],
            explicits=[ItemMod(text="7% increased maximum Life")],
        )
        .with_skill_group(
            "Weapon 1",
            gems=[
                {"name_spec": "Lightning Arrow", "level": 21, "quality": 20},
                {"name_spec": "Trinity Support", "level": 20, "quality": 20},
                {"name_spec": "Inspiration Support", "level": 20, "quality": 20},
                {"name_spec": "Empower Support", "level": 4, "quality": 0},
            ],
            include_in_full_dps=True,
        )
        .with_skill_group(
            "",
            gems=[
                {"name_spec": "Enlighten Support", "level": 4, "quality": 0},
                {"name_spec": "Grace", "level": 20, "quality": 0},
                {"name_spec": "Determination", "level": 20, "quality": 0},
            ],
        )
        .with_config(useFrenzyCharges=True, usePowerCharges=True, enemyPhysicalHitDamage=8000)
        .with_notes("Deadeye bow build")
        .write("deadeye.xml")
    )


def _create_hierophant_build(d: Path) -> Path:
    """Hierophant with totem and minion gems, different class."""
    builder = PoBXmlBuilder(d)
    return (
        builder.with_class("Templar", "Hierophant", 92)
        .with_stat("Life", 5500)
        .with_stat("Mana", 3000)
        .with_stat("TotalDPS", 800000)
        .with_stat("FireResist", 76)
        .with_stat("ColdResist", 76)
        .with_stat("LightningResist", 76)
        .with_stat("ChaosResist", 40)
        .with_tree_spec(
            "Main",
            [3000, 3001, 3002, 3003, 3004, 3005],
            masteries=[(30000, 40000), (30001, 40001), (30002, 40002)],
            class_id=3,
            ascend_class_id=2,
            version="3_25",
            sockets=[(50000, 3)],
        )
        .with_item(
            "Body Armour",
            rarity="RARE",
            name="Havoc Ward",
            base_type="Vaal Regalia",
            energy_shield=500,
            armour=200,
            quality=28,
            implicits=[],
            explicits=[
                ItemMod(text="+120 to maximum Life"),
                ItemMod(text="+50% to Fire Resistance"),
            ],
            prefix_slots=["IncreasedLife7", None, None],
            suffix_slots=["FireResistance6", None, None],
        )
        .with_item(
            "Helmet",
            rarity="RARE",
            name="Mind Crown",
            base_type="Hubris Circlet",
            energy_shield=250,
            implicits=[],
            explicits=[ItemMod(text="+80 to maximum Life")],
        )
        .with_skill_group(
            "Body Armour",
            gems=[
                {"name_spec": "Freezing Pulse", "level": 20, "quality": 20},
                {"name_spec": "Spell Totem Support", "level": 20, "quality": 20},
                {"name_spec": "Faster Casting Support", "level": 20, "quality": 20},
            ],
            include_in_full_dps=True,
        )
        .with_config(useFrenzyCharges=False, enemyPhysicalHitDamage=3000, customLabel="totem test")
        .with_notes("Hierophant totem build")
        .write("hierophant.xml")
    )


def _create_simple_build(d: Path) -> Path:
    """Minimal build — single spec, single item set."""
    builder = PoBXmlBuilder(d)
    return (
        builder.with_class("Marauder", "", 50)
        .with_stat("Life", 3000)
        .with_stat("Armour", 10000)
        .with_stat("FireResist", 75)
        .with_stat("ColdResist", 75)
        .with_stat("LightningResist", 75)
        .with_stat("ChaosResist", 0)
        .with_tree_spec(
            "Default", [9000, 9001, 9002], class_id=1, ascend_class_id=0, version="3_25"
        )
        .with_item(
            "Body Armour",
            rarity="NORMAL",
            name="Simple Plate",
            base_type="Astral Plate",
            armour=700,
            implicits=[ItemMod(text="+12% to all Elemental Resistances")],
            explicits=[],
        )
        .with_skill_group(
            "Body Armour",
            gems=[
                {"name_spec": "Ground Slam", "level": 15, "quality": 0},
            ],
        )
        .write("simple.xml")
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def integration_builds_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("builds")
    _create_necromancer_build(d)
    _create_deadeye_build(d)
    _create_hierophant_build(d)
    _create_simple_build(d)
    return d


@pytest.fixture(scope="session")
def all_build_paths(integration_builds_dir) -> list[Path]:
    return sorted(integration_builds_dir.glob("*.xml"))


@pytest.fixture()
def all_builds(all_build_paths) -> list[tuple[str, object]]:
    """Re-parse all generated builds for each test.

    Function-scope (not session): tests like test_remove_all_items_roundtrip
    mutate the BuildDocument (build.items.clear(), spec.nodes.append(...)),
    which would pollute every subsequent test under session scope.
    """
    results = []
    for p in all_build_paths:
        build = parse_build_file(p)
        results.append((p.stem, build))
    return results


def build_by_name(builds: list[tuple[str, object]], name_fragment: str):
    """Find a parsed build by partial name match."""
    for bname, build in builds:
        if name_fragment.lower() in bname.lower():
            return build
    return None


# ── Craft data ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def repoe_data():
    from poe.services.repoe.data import RepoEData

    cd = RepoEData()
    data_dir = cd._data_dir
    if not (data_dir / "base_items.json").exists():
        pytest.skip("Pre-built RePoE data not found. Run: poe dev build-data")
    return cd

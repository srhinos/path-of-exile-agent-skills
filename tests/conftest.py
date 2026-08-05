from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from poe.models.build.build import BuildDocument
from poe.models.build.config import BuildConfig, ConfigEntry
from poe.models.build.gems import Gem, GemGroup
from poe.models.build.items import Item, ItemSet, ItemSlot
from poe.models.build.stats import StatEntry
from poe.models.build.tree import MasteryMapping, TreeSocket, TreeSpec
from poe.services.build.xml.writer import write_build_file

if TYPE_CHECKING:
    from pathlib import Path


class CliResult:
    def __init__(self, output: str, exit_code: int, exception: BaseException | None = None) -> None:
        self.output = output
        self.exit_code = exit_code
        self.exception = exception


def invoke_cli(app, args: list[str]) -> CliResult:
    buf = io.StringIO()
    console = Console(file=buf, highlight=False, color_system=None)
    exit_code = 0
    exception = None
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            app(args, exit_on_error=False, console=console)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    except Exception as e:
        exception = e
        exit_code = 1
    return CliResult(output=buf.getvalue(), exit_code=exit_code, exception=exception)


# ── Minimal PoB XML ──────────────────────────────────────────────────────────

MINIMAL_BUILD_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding>
    <Build level="90" className="Witch" ascendClassName="Necromancer"
           bandit="None" viewMode="TREE" targetVersion="3_0"
           mainSocketGroup="1" pantheonMajorGod="" pantheonMinorGod="">
        <PlayerStat stat="Life" value="4500"/>
        <PlayerStat stat="EnergyShield" value="1200"/>
        <PlayerStat stat="TotalDPS" value="150000"/>
        <PlayerStat stat="FireResist" value="75"/>
        <PlayerStat stat="ColdResist" value="75"/>
        <PlayerStat stat="LightningResist" value="75"/>
        <PlayerStat stat="ChaosResist" value="20"/>
    </Build>
    <Tree activeSpec="1">
        <Spec title="Main" treeVersion="3_25" classId="5" ascendClassId="2"
              nodes="100,200,300,400"
              masteryEffects="{53188,64875},{53738,29161}">
            <URL>https://example.com/tree</URL>
            <Sockets>
                <Socket nodeId="26725" itemId="1"/>
            </Sockets>
        </Spec>
    </Tree>
    <Skills activeSkillSet="1">
        <SkillSet id="1">
            <Skill slot="Body Armour" enabled="true" includeInFullDPS="true">
                <Gem nameSpec="Fireball" skillId="Fireball" gemId="gem_fireball"
                     level="20" quality="20" enabled="true" count="1"/>
                <Gem nameSpec="Spell Echo Support" skillId="SpellEcho"
                     level="20" quality="0" enabled="true" count="1"/>
            </Skill>
        </SkillSet>
    </Skills>
    <Items activeItemSet="1">
        <Item id="1" variant="">
Rarity: RARE
Doom Crown
Hubris Circlet
Energy Shield: 200
Quality: 20
Sockets: B-B-B-B
LevelReq: 69
Implicits: 1
{tags:resource,life}{range:0.5}+(50-70) to maximum Life
Prefix: {range:0.5}IncreasedLife6
Prefix: {range:0.5}SpellDamage3
Prefix: None
Suffix: {range:0.5}ColdResistance5
Suffix: {range:0.5}LightningResistance4
Suffix: None
{range:0.5}+90 to maximum Life
{range:0.5}Adds 30 to 50 Spell Damage
{range:0.5}+40% to Cold Resistance
{range:0.5}+35% to Lightning Resistance
        </Item>
        <ItemSet id="1">
            <Slot name="Helmet" itemId="1"/>
        </ItemSet>
    </Items>
    <Config activeConfigSet="1">
        <ConfigSet id="1" title="Default">
            <Input name="useFrenzyCharges" boolean="true"/>
            <Input name="enemyCondNearbyRareCruiser" boolean="true"/>
            <Input name="enemyPhysicalHitDamage" number="5000"/>
        </ConfigSet>
    </Config>
    <Notes>Build notes here</Notes>
    <Import importLink="https://pobb.in/abc123"/>
</PathOfBuilding>
"""


@pytest.fixture
def minimal_build_xml(tmp_path: Path) -> Path:
    p = tmp_path / "test_build.xml"
    p.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
    return p


@pytest.fixture
def tmp_builds_dir(tmp_path: Path) -> Path:
    builds = tmp_path / "builds"
    builds.mkdir()
    for name in ["BuildA.xml", "BuildB.xml", "SomeOther.xml"]:
        (builds / name).write_text(MINIMAL_BUILD_XML, encoding="utf-8")
    (builds / "notes.txt").write_text("not a build")
    return builds


@pytest.fixture
def fixture_path():
    """Return path to a named test fixture file."""
    from pathlib import Path

    base = Path(__file__).parent / "fixtures"

    def _get(name: str) -> Path:
        p = base / name
        assert p.exists(), f"Fixture not found: {p}"
        return p

    return _get


# ── Craft pipeline mock data ─────────────────────────────────────────────────

REPOE_DATA = {
    "base_items": {
        "Hubris Circlet": {
            "id": "Metadata/Items/Armours/Helmets/HelmetInt10",
            "item_class": "Helmet",
            "drop_level": 69,
            "tags": ["int_armour", "helmet", "armour", "default"],
            "properties": {"energy_shield": {"min": 100, "max": 120}},
            "max_prefixes": 3,
            "max_suffixes": 3,
        },
        "Vaal Regalia": {
            "id": "Metadata/Items/Armours/BodyArmours/BodyInt10",
            "item_class": "Body Armour",
            "drop_level": 68,
            "tags": ["int_armour", "body_armour", "armour", "default"],
            "properties": {},
            "max_prefixes": 3,
            "max_suffixes": 3,
        },
    },
    "mods": {
        "IncreasedLife4": {
            "name": "Increased Life",
            "group": "IncreasedLife",
            "affix": "prefix",
            "required_level": 1,
            "implicit_tags": ["resource", "life"],
            "stats": [{"id": "base_maximum_life", "min": 10, "max": 20}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 1000},
                {"tag": "body_armour", "weight": 1000},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "IncreasedLife3": {
            "name": "Increased Life",
            "group": "IncreasedLife",
            "affix": "prefix",
            "required_level": 36,
            "implicit_tags": ["resource", "life"],
            "stats": [{"id": "base_maximum_life", "min": 30, "max": 40}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 800},
                {"tag": "body_armour", "weight": 800},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "IncreasedLife2": {
            "name": "Increased Life",
            "group": "IncreasedLife",
            "affix": "prefix",
            "required_level": 68,
            "implicit_tags": ["resource", "life"],
            "stats": [{"id": "base_maximum_life", "min": 60, "max": 80}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 500},
                {"tag": "body_armour", "weight": 500},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "IncreasedLife1": {
            "name": "Increased Life",
            "group": "IncreasedLife",
            "affix": "prefix",
            "required_level": 82,
            "implicit_tags": ["resource", "life"],
            "stats": [{"id": "base_maximum_life", "min": 90, "max": 100}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 200},
                {"tag": "body_armour", "weight": 200},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "ColdResistance2": {
            "name": "Cold Resistance",
            "group": "ColdResistance",
            "affix": "suffix",
            "required_level": 1,
            "implicit_tags": ["elemental", "resistance", "cold"],
            "stats": [{"id": "cold_damage_resistance_%", "min": 10, "max": 20}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 1000},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "ColdResistance1": {
            "name": "Cold Resistance",
            "group": "ColdResistance",
            "affix": "suffix",
            "required_level": 60,
            "implicit_tags": ["elemental", "resistance", "cold"],
            "stats": [{"id": "cold_damage_resistance_%", "min": 30, "max": 40}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 500},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "FireResistance1": {
            "name": "Fire Resistance",
            "group": "FireResistance",
            "affix": "suffix",
            "required_level": 1,
            "implicit_tags": ["elemental", "resistance", "fire"],
            "stats": [{"id": "fire_damage_resistance_%", "min": 10, "max": 20}],
            "spawn_weights": [
                {"tag": "helmet", "weight": 1000},
                {"tag": "default", "weight": 0},
            ],
            "influence": None,
            "is_essence_only": False,
        },
        "ShaperIncreasedLife1": {
            "name": "Shaper Life",
            "group": "ShaperLife",
            "affix": "prefix",
            "required_level": 68,
            "implicit_tags": ["resource", "life"],
            "stats": [{"id": "base_maximum_life", "min": 5, "max": 10}],
            "spawn_weights": [
                {"tag": "helmet_shaper", "weight": 300},
                {"tag": "default", "weight": 0},
            ],
            "influence": "Shaper",
            "is_essence_only": False,
        },
    },
    "mod_pool": {
        "Metadata/Items/Armours/Helmets/HelmetInt10": [
            "IncreasedLife4",
            "IncreasedLife3",
            "IncreasedLife2",
            "IncreasedLife1",
            "ColdResistance2",
            "ColdResistance1",
            "FireResistance1",
            "ShaperIncreasedLife1",
        ],
        "Metadata/Items/Armours/BodyArmours/BodyInt10": [
            "IncreasedLife4",
            "IncreasedLife3",
            "IncreasedLife2",
            "IncreasedLife1",
        ],
    },
    "fossils": {
        "Pristine Fossil": {
            "positive_weights": {"life": 10.0},
            "negative_weights": {"defences": 0.0},
            "forced_mods": [],
            "added_mods": [],
            "blocked_tags": ["defences"],
        },
        "Frigid Fossil": {
            "positive_weights": {"cold": 10.0},
            "negative_weights": {"fire": 0.0},
            "forced_mods": [],
            "added_mods": [],
            "blocked_tags": ["fire"],
        },
        "Metallic Fossil": {
            "positive_weights": {"lightning": 10.0},
            "negative_weights": {"physical": 0.0},
            "forced_mods": [],
            "added_mods": [],
            "blocked_tags": ["physical"],
        },
    },
    "essences": {
        "Essence of Greed": {
            "tier": 5,
            "level_restriction": 45,
            "mods": {"Helmet": "IncreasedLife2", "Body Armour": "IncreasedLife2"},
            "is_corruption_only": False,
        },
    },
    "bench_crafts": [
        {
            "mod_id": "IncreasedLife4",
            "item_classes": ["Helmet", "Body Armour", "Gloves", "Boots"],
            "cost": {"Chaos Orb": 4},
            "bench_tier": 1,
        },
        {
            "mod_id": "ColdResistance2",
            "item_classes": ["Helmet", "Body Armour", "Gloves", "Boots"],
            "cost": {"Orb of Alteration": 6},
            "bench_tier": 1,
        },
    ],
    "stat_translations": {
        "base_maximum_life": "{0} to maximum Life",
        "cold_damage_resistance_%": "{0}% to Cold Resistance",
    },
}

REPOE_PRICES_DATA = {
    "league": "Settlers",
    "currency": {
        "Orb of Alteration": 0.08,
        "Exalted Orb": 15,
        "Divine Orb": 180,
        "Orb of Annulment": 4,
        "Orb of Scouring": 0.3,
        "Regal Orb": 1,
    },
    "fossils": {
        "Pristine Fossil": 3,
        "Frigid Fossil": 2,
    },
    "essences": {},
    "resonators": {
        "Primitive Alchemical Resonator": 1,
        "Potent Alchemical Resonator": 3,
    },
    "beasts": {},
    "other": {},
}


def make_repoe_data(data: dict | None = None):
    from pathlib import Path
    from unittest.mock import MagicMock

    from poe.services.repoe.data import RepoEData

    fixture = data or REPOE_DATA
    cd = RepoEData(data_dir=Path("/fake"))
    cd._load = MagicMock(side_effect=lambda name: fixture[name])
    return cd


@pytest.fixture
def repoe_data():
    return make_repoe_data()


# ── PoBXmlBuilder ─────────────────────────────────────────────────────────────


class PoBXmlBuilder:
    """Fluent builder for constructing PoB build XML files in tests."""

    def __init__(self, base_dir: Path):
        self._dir = base_dir
        self._build = BuildDocument(
            specs=[TreeSpec(tree_version="3_25")],
            skill_set_ids=[1],
            item_sets=[ItemSet(id="1")],
            config_sets=[BuildConfig(id="1", title="Default")],
        )
        self._next_item_id = 1

    def with_class(self, class_name: str, ascendancy: str = "", level: int = 1) -> PoBXmlBuilder:
        self._build.class_name = class_name
        self._build.ascend_class_name = ascendancy
        self._build.level = level
        return self

    def with_stat(self, stat: str, value: float) -> PoBXmlBuilder:
        self._build.player_stats.append(StatEntry(stat=stat, value=value))
        return self

    def with_tree_spec(
        self,
        title: str,
        nodes: list[int],
        masteries: list[tuple[int, int]] | None = None,
        class_id: int = 0,
        ascend_class_id: int = 0,
        version: str = "3_25",
        sockets: list[tuple[int, int]] | None = None,
        url: str = "",
    ) -> PoBXmlBuilder:
        spec = TreeSpec(
            title=title,
            tree_version=version,
            class_id=class_id,
            ascend_class_id=ascend_class_id,
            nodes=nodes,
            mastery_effects=[MasteryMapping(node_id=n, effect_id=e) for n, e in (masteries or [])],
            sockets=[TreeSocket(node_id=n, item_id=i) for n, i in (sockets or [])],
            url=url,
        )
        if len(self._build.specs) == 1 and not self._build.specs[0].nodes:
            self._build.specs[0] = spec
        else:
            self._build.specs.append(spec)
        return self

    def with_item(self, slot: str, **kwargs) -> PoBXmlBuilder:
        item_id = self._next_item_id
        self._next_item_id += 1

        defaults = {
            "rarity": "RARE",
            "name": "New Item",
            "base_type": "",
            "influences": [],
            "armour": 0,
            "evasion": 0,
            "energy_shield": 0,
            "quality": 0,
            "sockets": "",
            "level_req": 0,
            "implicits": [],
            "explicits": [],
            "is_crafted": False,
            "prefix_slots": [],
            "suffix_slots": [],
        }
        defaults.update(kwargs)
        for list_field in ("influences", "implicits", "explicits", "prefix_slots", "suffix_slots"):
            if defaults[list_field] is None:
                defaults[list_field] = []

        item = Item(id=item_id, text="", **defaults)
        self._build.items.append(item)
        self._build.item_sets[0].slots.append(ItemSlot(name=slot, item_id=item_id))
        return self

    def with_skill_group(
        self,
        slot: str = "",
        gems: list[dict] | None = None,
        *,
        include_in_full_dps: bool = False,
        enabled: bool = True,
        label: str = "",
        main_active_skill_calcs: int = 0,
        group_count: int = 0,
    ) -> PoBXmlBuilder:
        gem_objects = []
        for g in gems or []:
            kw = dict(g)
            kw.setdefault("name_spec", "Unknown")
            gem_objects.append(Gem(**kw))
        group = GemGroup(
            slot=slot,
            label=label,
            enabled=enabled,
            include_in_full_dps=include_in_full_dps,
            gems=gem_objects,
            main_active_skill_calcs=main_active_skill_calcs,
            group_count=group_count,
        )
        self._build.skill_groups.append(group)
        return self

    def with_config(self, **kwargs) -> PoBXmlBuilder:
        cfg = self._build.config_sets[0]
        for k, v in kwargs.items():
            if isinstance(v, bool):
                cfg.inputs.append(ConfigEntry(name=k, value=v, input_type="boolean"))
            elif isinstance(v, (int, float)):
                cfg.inputs.append(ConfigEntry(name=k, value=float(v), input_type="number"))
            else:
                cfg.inputs.append(ConfigEntry(name=k, value=str(v), input_type="string"))
        return self

    def with_notes(self, text: str) -> PoBXmlBuilder:
        self._build.notes = text
        return self

    def with_import_link(self, link: str) -> PoBXmlBuilder:
        self._build.import_link = link
        return self

    def build_object(self) -> BuildDocument:
        return self._build

    def write(self, filename: str = "build.xml") -> Path:
        path = self._dir / filename
        write_build_file(self._build, path)
        return path

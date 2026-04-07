from __future__ import annotations

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

from poe.app import app as cli
from poe.services.ninja.errors import NetworkError
from poe.services.repoe.sim import BestTier, ModPoolEntry
from tests.conftest import invoke_cli

# Imports are now at the top of craft/cli.py, so patch where they're used.
_PATCH_CD = "poe.services.repoe.sim_service.RepoEData"
_PATCH_ENGINE = "poe.services.repoe.sim_service.CraftingEngine"
_PATCH_RESOLVE = "poe.services.repoe.sim_service.resolve_build_file"
_PATCH_PARSE = "poe.services.repoe.sim_service.parse_build_file"


# ── helpers ──────────────────────────────────────────────────────────────────


def _mock_repoe_data(**overrides):
    """Return a MagicMock pretending to be RepoEData."""
    cd = MagicMock()
    # Defaults — override per test
    cd.get_mod_pool.return_value = []
    cd.get_base_item.return_value = None
    cd.get_mod_tiers.return_value = []
    cd.get_fossils.return_value = []
    cd.get_essences.return_value = []
    cd.get_bench_crafts.return_value = []
    cd.search_base_items.return_value = []
    cd.get_prices.return_value = {}
    for k, v in overrides.items():
        getattr(cd, k).return_value = v
    return cd


SAMPLE_MODS = [
    ModPoolEntry(
        mod_id="IncreasedLife1",
        name="Increased Life",
        affix="prefix",
        group="IncreasedLife",
        weight=1000,
        tier_count=4,
        best_tier=BestTier(ilvl=82, values=((90, 100),), weight=200),
        implicit_tags=("resource", "life"),
        influence=None,
    ),
    ModPoolEntry(
        mod_id="ColdResistance1",
        name="Cold Resistance",
        affix="suffix",
        group="ColdResistance",
        weight=500,
        tier_count=2,
        best_tier=BestTier(ilvl=60, values=((30, 40),), weight=500),
        implicit_tags=("elemental", "resistance", "cold"),
        influence=None,
    ),
]


# ── craft mods ───────────────────────────────────────────────────────────────


class TestCraftMods:
    def test_success(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "mods", "Hubris Circlet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["base"] == "Hubris Circlet"
        assert data["total_mods"] == 2
        assert len(data["mods"]) == 2

    def test_success_with_options(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS[:1])
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "mods",
                    "Hubris Circlet",
                    "--ilvl",
                    "86",
                    "--influence",
                    "shaper",
                    "--type",
                    "prefix",
                    "--limit",
                    "5",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ilvl"] == 86
        assert data["influences"] == ["Shaper"]
        assert data["filter"] == "prefix"

    def test_base_not_found(self):
        cd = _mock_repoe_data(get_mod_pool=[], get_base_item=None)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "mods", "FakeItem"])
        assert result.exit_code != 0
        assert result.exit_code != 0

    def test_no_mods_for_filters(self):
        """Base exists but no mods match the filters."""
        cd = _mock_repoe_data(
            get_mod_pool=[],
            get_base_item={
                "id": "Metadata/Items/Armours/Helmets/HelmetInt10",
                "item_class": "Helmet",
            },
        )
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "mods", "Hubris Circlet"])
        assert result.exit_code != 0
        assert result.exit_code != 0

    def test_exception(self):
        cd = _mock_repoe_data()
        cd.get_mod_pool.side_effect = RuntimeError("network down")
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "mods", "Hubris Circlet"])
        assert result.exit_code != 0

    def test_human_output(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "mods", "Hubris Circlet"])
        assert result.exit_code == 0
        # Human output is not JSON
        with contextlib.suppress(Exception):
            json.loads(result.output)
        assert "Hubris Circlet" in result.output


# ── craft tiers ──────────────────────────────────────────────────────────────


SAMPLE_TIERS = [
    {"tier": 1, "ilvl": 82, "weight": 200, "values": [[90, 100]], "available": True},
    {"tier": 2, "ilvl": 68, "weight": 500, "values": [[60, 80]], "available": True},
    {"tier": 3, "ilvl": 36, "weight": 800, "values": [[30, 40]], "available": True},
]


class TestCraftTiers:
    def test_success(self):
        cd = _mock_repoe_data(get_mod_tiers=SAMPLE_TIERS)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "tiers", "mod_life", "Hubris Circlet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mod_id"] == "mod_life"
        assert data["base"] == "Hubris Circlet"
        assert len(data["tiers"]) == 3

    def test_no_tiers_found(self):
        cd = _mock_repoe_data(get_mod_tiers=[])
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "tiers", "mod_nope", "Hubris Circlet"])
        assert result.exit_code != 0
        assert result.exit_code != 0

    def test_exception(self):
        cd = _mock_repoe_data()
        cd.get_mod_tiers.side_effect = RuntimeError("db error")
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "tiers", "mod_life", "Hubris Circlet"])
        assert result.exit_code != 0

    def test_custom_ilvl(self):
        cd = _mock_repoe_data(get_mod_tiers=SAMPLE_TIERS[:2])
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(
                cli, ["sim", "tiers", "mod_life", "Hubris Circlet", "--ilvl", "75", "--json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ilvl"] == 75


# ── craft fossils ────────────────────────────────────────────────────────────


SAMPLE_FOSSILS = [
    {
        "name": "Pristine Fossil",
        "positive_weights": {"life": 10.0},
        "negative_weights": {"defences": 0.0},
        "blocked": ["defences"],
    },
    {
        "name": "Frigid Fossil",
        "positive_weights": {"cold": 10.0},
        "negative_weights": {"fire": 0.0},
        "blocked": ["fire"],
    },
]


class TestCraftFossils:
    def test_success(self):
        cd = _mock_repoe_data(get_fossils=SAMPLE_FOSSILS)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "fossils", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert len(data["fossils"]) == 2

    def test_with_filter(self):
        cd = _mock_repoe_data(get_fossils=SAMPLE_FOSSILS[:1])
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "fossils", "--filter", "life", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["filter"] == "life"

    def test_exception(self):
        cd = _mock_repoe_data()
        cd.get_fossils.side_effect = RuntimeError("cache corrupted")
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "fossils"])
        assert result.exit_code != 0

    def test_human_output(self):
        cd = _mock_repoe_data(get_fossils=SAMPLE_FOSSILS)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "fossils"])
        assert result.exit_code == 0
        assert "Pristine Fossil" in result.output


# ── craft essences ───────────────────────────────────────────────────────────


SAMPLE_ESSENCES = [
    {
        "id": "1",
        "name": "Essence of Greed",
        "mods": [{"slot": "Helmet", "mod": "+60 to maximum Life"}],
    },
]

SAMPLE_ESSENCES_ALL = [
    {
        "id": "1",
        "name": "Essence of Greed",
        "mods": [{"slot": "Helmet", "mod": "+60 to maximum Life"}],
        "total_slots": 1,
    },
]


class TestCraftEssences:
    def test_success_no_base(self):
        cd = _mock_repoe_data(get_essences=SAMPLE_ESSENCES_ALL)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "essences", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["base"] == "all"
        assert data["count"] == 1

    def test_success_with_base(self):
        cd = _mock_repoe_data(get_essences=SAMPLE_ESSENCES)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "essences", "Hubris Circlet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["base"] == "Hubris Circlet"

    def test_exception(self):
        cd = _mock_repoe_data()
        cd.get_essences.side_effect = RuntimeError("fail")
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "essences"])
        assert result.exit_code != 0


# ── craft bench ──────────────────────────────────────────────────────────────


SAMPLE_BENCH_CRAFTS = [
    {
        "mod_id": "IncreasedLife4",
        "name": "Increased Life",
        "affix": "prefix",
        "group": "IncreasedLife",
        "cost": "4x Chaos Orb",
        "cost_raw": {"Chaos Orb": 4},
        "values": [[90, 100]],
    },
]


class TestCraftBench:
    def test_success(self):
        cd = _mock_repoe_data(
            get_bench_crafts=SAMPLE_BENCH_CRAFTS,
            get_base_item={"name": "Hubris Circlet"},
        )
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "bench", "Hubris Circlet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["base"] == "Hubris Circlet"
        assert data["count"] == 1
        assert data["crafts"][0]["name"] == "Increased Life"

    def test_exception(self):
        cd = _mock_repoe_data()
        cd.get_bench_crafts.side_effect = RuntimeError("bench error")
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "bench", "Hubris Circlet"])
        assert result.exit_code != 0


# ── craft search ─────────────────────────────────────────────────────────────


SAMPLE_SEARCH_RESULTS = [
    {"name": "Hubris Circlet", "drop_level": 69, "properties": {}},
    {"name": "Hubris Circlet of the Lynx", "drop_level": 70, "properties": {"ar": 100}},
]


class TestCraftSearch:
    def test_success(self):
        cd = _mock_repoe_data(search_base_items=SAMPLE_SEARCH_RESULTS)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "search", "hubris", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"] == "hubris"
        assert data["count"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Hubris Circlet"
        assert data["items"][0]["drop_level"] == 69

    def test_no_results(self):
        cd = _mock_repoe_data(search_base_items=[])
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "search", "zzzznothing", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0
        assert data["items"] == []

    def test_exception(self):
        cd = _mock_repoe_data()
        cd.search_base_items.side_effect = RuntimeError("search error")
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "search", "hubris"])
        assert result.exit_code != 0

    def test_properties_already_dict(self):
        items = [{"name": "Crown", "drop_level": 10, "properties": {"es": 50}}]
        cd = _mock_repoe_data(search_base_items=items)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "search", "crown", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["items"][0]["properties"] == {"es": 50}

    def test_properties_empty_string(self):
        items = [{"name": "Crown", "drop_level": 10, "properties": {}}]
        cd = _mock_repoe_data(search_base_items=items)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "search", "crown", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["items"][0]["properties"] == {}

    def test_truncates_to_20(self):
        items = [{"name": f"Item{i}", "drop_level": i, "properties": {}} for i in range(30)]
        cd = _mock_repoe_data(search_base_items=items)
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(cli, ["sim", "search", "item", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 20
        assert len(data["items"]) == 20


# ── craft analyze ────────────────────────────────────────────────────────────


def _make_mock_item(
    base_type="Hubris Circlet",
    influences=None,
    open_prefixes=1,
    open_suffixes=1,
    name="Doom Crown",
    rarity="RARE",
):
    """Create a mock Item for analyze tests."""
    item = MagicMock()
    item.base_type = base_type
    item.influences = influences or []
    item.open_prefixes = open_prefixes
    item.open_suffixes = open_suffixes
    item.name = name
    item.rarity = rarity
    dump = {
        "id": 1,
        "text": "",
        "rarity": rarity,
        "name": name,
        "base_type": base_type,
        "influences": influences or [],
        "implicits": [],
        "explicits": [],
    }
    item.to_dict.return_value = dump
    item.model_dump.return_value = dump
    return item


def _make_mock_build(equipped_items=None):
    """Create a mock Build for analyze tests."""
    build_obj = MagicMock()
    build_obj.get_equipped_items.return_value = equipped_items or []
    return build_obj


class TestCraftAnalyze:
    def test_success_base_found(self, tmp_path):
        """Analyze succeeds: build found, item in slot, base found in CoE."""
        mock_item = _make_mock_item()
        mock_build = _make_mock_build(equipped_items=[("Helmet", mock_item)])
        cd = _mock_repoe_data(
            get_base_item={"id": "Metadata/Items/Armours/Helmets/HelmetInt10"},
            get_mod_pool=SAMPLE_MODS,
            get_bench_crafts=SAMPLE_BENCH_CRAFTS,
        )

        with (
            patch(_PATCH_RESOLVE, return_value=tmp_path / "build.xml"),
            patch(_PATCH_PARSE, return_value=mock_build),
            patch(_PATCH_CD, return_value=cd),
        ):
            result = invoke_cli(cli, ["sim", "analyze", "MyBuild", "--slot", "Helmet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slot"] == "Helmet"
        assert data["analysis"]["base_found"] is True
        assert data["analysis"]["total_rollable_prefixes"] == 1  # 1 prefix in SAMPLE_MODS
        assert data["analysis"]["total_rollable_suffixes"] == 1  # 1 suffix in SAMPLE_MODS
        assert data["analysis"]["open_prefix_slots"] == 1
        assert data["analysis"]["open_suffix_slots"] == 1

    def test_success_base_not_in_coe(self, tmp_path):
        """Analyze succeeds but base item not found in CoE data."""
        mock_item = _make_mock_item(base_type="Custom Base")
        mock_build = _make_mock_build(equipped_items=[("Helmet", mock_item)])
        cd = _mock_repoe_data(get_base_item=None)

        with (
            patch(_PATCH_RESOLVE, return_value=tmp_path / "build.xml"),
            patch(_PATCH_PARSE, return_value=mock_build),
            patch(_PATCH_CD, return_value=cd),
        ):
            result = invoke_cli(cli, ["sim", "analyze", "MyBuild", "--slot", "Helmet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["analysis"]["base_found"] is False
        # No rollable mod info when base not in CoE
        assert "total_rollable_prefixes" not in data["analysis"]

    def test_build_not_found(self):
        """Analyze fails because build file not found."""
        with patch(
            _PATCH_RESOLVE,
            side_effect=FileNotFoundError("Build 'Nope' not found"),
        ):
            result = invoke_cli(cli, ["sim", "analyze", "Nope", "--slot", "Helmet"])
        assert result.exit_code != 0
        assert result.exit_code != 0

    def test_no_item_in_slot(self, tmp_path):
        """Analyze fails because no item in the requested slot."""
        mock_build = _make_mock_build(equipped_items=[])
        with (
            patch(_PATCH_RESOLVE, return_value=tmp_path / "build.xml"),
            patch(_PATCH_PARSE, return_value=mock_build),
        ):
            result = invoke_cli(cli, ["sim", "analyze", "MyBuild", "--slot", "Boots"])
        assert result.exit_code != 0
        assert result.exit_code != 0

    def test_with_ilvl_override(self, tmp_path):
        """Analyze with --ilvl override."""
        mock_item = _make_mock_item()
        mock_build = _make_mock_build(equipped_items=[("Helmet", mock_item)])
        cd = _mock_repoe_data(
            get_base_item={"id": "Metadata/Items/Armours/Helmets/HelmetInt10"},
            get_mod_pool=[],
            get_bench_crafts=[],
        )

        with (
            patch(_PATCH_RESOLVE, return_value=tmp_path / "build.xml"),
            patch(_PATCH_PARSE, return_value=mock_build),
            patch(_PATCH_CD, return_value=cd),
        ):
            result = invoke_cli(
                cli, ["sim", "analyze", "MyBuild", "--slot", "Helmet", "--ilvl", "100", "--json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["analysis"]["ilvl_used"] == 100

    def test_bench_crafts_section(self, tmp_path):
        """Analyze includes bench_crafts_sample when bench crafts exist."""
        mock_item = _make_mock_item(open_prefixes=0, open_suffixes=0)
        mock_build = _make_mock_build(equipped_items=[("Helmet", mock_item)])
        cd = _mock_repoe_data(
            get_base_item={"id": "Metadata/Items/Armours/Helmets/HelmetInt10"},
            get_mod_pool=SAMPLE_MODS,
            get_bench_crafts=SAMPLE_BENCH_CRAFTS,
        )

        with (
            patch(_PATCH_RESOLVE, return_value=tmp_path / "build.xml"),
            patch(_PATCH_PARSE, return_value=mock_build),
            patch(_PATCH_CD, return_value=cd),
        ):
            result = invoke_cli(cli, ["sim", "analyze", "MyBuild", "--slot", "Helmet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["analysis"]["bench_craft_count"] == 1
        assert len(data["analysis"]["bench_crafts_sample"]) == 1

    def test_case_insensitive_slot_match(self, tmp_path):
        """Slot matching is case-insensitive."""
        mock_item = _make_mock_item()
        mock_build = _make_mock_build(equipped_items=[("Body Armour", mock_item)])
        cd = _mock_repoe_data(get_base_item=None)

        with (
            patch(_PATCH_RESOLVE, return_value=tmp_path / "build.xml"),
            patch(_PATCH_PARSE, return_value=mock_build),
            patch(_PATCH_CD, return_value=cd),
        ):
            result = invoke_cli(cli, ["sim", "analyze", "MyBuild", "--slot", "body", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slot"] == "Body Armour"


# ── craft simulate ───────────────────────────────────────────────────────────


def _make_sim_result(**overrides):
    """Create a mock SimResult."""
    defaults = {
        "method": "chaos",
        "iterations": 10000,
        "hits": 5000,
        "hit_rate": 0.5,
        "avg_attempts": 2.0,
        "avg_cost_chaos": 2.0,
        "cost_per_attempt": 1.0,
        "percentiles": {"p50": 1, "p75": 2, "p90": 4, "p99": 10},
    }
    defaults.update(overrides)
    sr = MagicMock()
    for k, v in defaults.items():
        setattr(sr, k, v)
    return sr


class TestCraftSimulate:
    def test_success_chaos(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result())

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["method"] == "chaos"
        assert data["hit_rate"] == "50.0%"
        assert data["avg_attempts"] == 2.0
        assert data.get("fossils") is None

    def test_success_fossil(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(
            return_value=_make_sim_result(method="fossil", cost_per_attempt=5.0),
        )

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "fossil",
                    "--target",
                    "IncreasedLife",
                    "--fossils",
                    "Pristine Fossil,Frigid Fossil",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["method"] == "fossil"
        assert data["fossils"] == ["Pristine Fossil", "Frigid Fossil"]

    def test_success_alt(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result(method="alt"))

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "alt",
                    "--target",
                    "IncreasedLife",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["method"] == "alt"

    def test_multiple_targets(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result())

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                    "--target",
                    "ColdResistance",
                    "--match",
                    "any",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["targets"] == ["IncreasedLife", "ColdResistance"]
        assert data["match_mode"] == "any"

    def test_custom_iterations(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result(iterations=500))

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                    "--iterations",
                    "500",
                ],
            )
        assert result.exit_code == 0

    def test_exception(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(side_effect=RuntimeError("sim failed"))

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                ],
            )
        assert result.exit_code != 0

    def test_with_influence(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result())

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                    "--influence",
                    "shaper",
                ],
            )
        assert result.exit_code == 0

    def test_success_essence(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result(method="essence"))

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "essence",
                    "--target",
                    "IncreasedLife",
                    "--essence",
                    "Greed",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["method"] == "essence"
        assert data["essence"] == "Greed"
        # Verify essence_name was passed to engine.simulate
        eng.simulate.assert_called_once()
        call_kwargs = eng.simulate.call_args
        assert call_kwargs[1].get("essence_name") == "Greed" or (
            len(call_kwargs[0]) > 0 and "Greed" in str(call_kwargs)
        )

    def test_essence_method_requires_essence_option(self):
        """Using --method essence without --essence should error."""
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result(method="essence"))

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "essence",
                    "--target",
                    "IncreasedLife",
                ],
            )
        assert result.exit_code != 0
        assert result.exit_code != 0


# ── craft prices ─────────────────────────────────────────────────────────────


SAMPLE_PRICES = {
    "league": "Settlers",
    "currency": {"Chaos Orb": 1, "Divine Orb": 180},
    "fossils": {"Pristine Fossil": 3},
    "essences": {},
    "resonators": {},
    "beasts": {},
    "other": {},
}


_PATCH_NINJA = "poe.services.repoe.sim_service.NinjaClient"


class TestCraftPrices:
    def test_success(self):
        cd = _mock_repoe_data(get_prices=SAMPLE_PRICES)
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_NINJA, side_effect=NetworkError("offline")),
        ):
            result = invoke_cli(cli, ["sim", "prices", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "currency" in data

    def test_with_league(self):
        cd = _mock_repoe_data(get_prices=SAMPLE_PRICES)
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_NINJA, side_effect=NetworkError("offline")),
        ):
            result = invoke_cli(cli, ["sim", "prices", "--league", "Settlers", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["league"] == "Settlers"

    def test_exception(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        cd.get_prices.side_effect = RuntimeError("no prices")
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_NINJA, side_effect=NetworkError("offline")),
        ):
            result = invoke_cli(cli, ["sim", "prices"])
        assert result.exit_code != 0

    def test_human_output(self):
        cd = _mock_repoe_data(get_prices=SAMPLE_PRICES)
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_NINJA, side_effect=NetworkError("offline")),
        ):
            result = invoke_cli(cli, ["sim", "prices"])
        assert result.exit_code == 0
        assert "Settlers" in result.output


# ── craft simulate existing_mods / max_attempts ─────────────────────────────


class TestCraftSimulateNewParams:
    def test_existing_mod_param(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result())

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                    "--existing-mod",
                    "ColdResistance",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = eng.simulate.call_args
        assert call_kwargs.kwargs.get("existing_mods") == ["ColdResistance"]

    def test_max_attempts_param(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.simulate = AsyncMock(return_value=_make_sim_result())

        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate",
                    "Hubris Circlet",
                    "--method",
                    "chaos",
                    "--target",
                    "IncreasedLife",
                    "--max-attempts",
                    "500",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = eng.simulate.call_args
        assert call_kwargs.kwargs.get("max_attempts") == 500


# ── craft simulate-multistep expanded methods ────────────────────────────────


class TestCraftSimulateMultistep:
    def test_basic_multistep(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.create_item.return_value = MagicMock(all_mods=[])
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate-multistep",
                    "Hubris Circlet",
                    "--step",
                    "chaos",
                    "--step",
                    "exalt",
                    "--target",
                    "IncreasedLife",
                    "--iterations",
                    "10",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["steps"] == ["chaos", "exalt"]
        assert data["iterations"] == 10

    def test_step_with_fossil_syntax(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.create_item.return_value = MagicMock(all_mods=[])
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate-multistep",
                    "Hubris Circlet",
                    "--step",
                    "fossil:fossils=Pristine Fossil+Dense Fossil",
                    "--target",
                    "IncreasedLife",
                    "--iterations",
                    "10",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["steps"] == ["fossil"]

    def test_new_craft_methods(self):
        cd = _mock_repoe_data(get_mod_pool=SAMPLE_MODS)
        eng = MagicMock()
        eng.create_item.return_value = MagicMock(all_mods=[])
        with (
            patch(_PATCH_CD, return_value=cd),
            patch(_PATCH_ENGINE, return_value=eng),
        ):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "simulate-multistep",
                    "Hubris Circlet",
                    "--step",
                    "transmutation",
                    "--step",
                    "augmentation",
                    "--step",
                    "regal",
                    "--target",
                    "IncreasedLife",
                    "--iterations",
                    "10",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["steps"] == ["transmutation", "augmentation", "regal"]


# ── get_tiers ilvl default ──────────────────────────────────────────────────


_PATCH_SVC = "poe.commands.sim.commands._svc"


class TestFossilOptimizer:
    def test_fossil_optimizer(self):
        mock_svc = MagicMock()
        mock_svc.fossil_optimizer.return_value = [
            {"fossil": "Jagged Fossil", "tag": "physical", "multiplier": 10.0, "effect": "boost"},
        ]
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(cli, ["sim", "fossil-optimizer", "physical", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["fossil"] == "Jagged Fossil"


class TestCompareCommand:
    def test_compare(self):
        mock_svc = MagicMock()
        mock_svc.compare_methods = AsyncMock(return_value={"chaos": 10, "fossil": 5})
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "compare",
                    "Hubris Circlet",
                    "--target",
                    "IncreasedLife",
                    "--fossils",
                    "Pristine Fossil,Dense Fossil",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["chaos"] == 10

    def test_compare_no_fossils(self):
        mock_svc = MagicMock()
        mock_svc.compare_methods = AsyncMock(return_value={"chaos": 10})
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                cli,
                [
                    "sim",
                    "compare",
                    "Hubris Circlet",
                    "--target",
                    "IncreasedLife",
                    "--json",
                ],
            )
        assert result.exit_code == 0


class TestSuggestCommand:
    def test_suggest(self):
        mock_svc = MagicMock()
        mock_svc.suggest_craft.return_value = [{"mod": "Life", "method": "fossil"}]
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(cli, ["sim", "suggest", "--mod", "Life", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestWeightsCommand:
    def test_weights(self):
        mock_svc = MagicMock()
        mock_svc.mod_weights.return_value = {"mods": []}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                cli,
                ["sim", "weights", "Hubris Circlet", "--json"],
            )
        assert result.exit_code == 0


class TestGetTiersDefault:
    def test_default_ilvl_is_84(self):
        cd = _mock_repoe_data(get_mod_tiers=[{"tier": 1, "ilvl": 82, "weight": 200}])
        with patch(_PATCH_CD, return_value=cd):
            result = invoke_cli(
                cli,
                ["sim", "tiers", "IncreasedLife1", "Hubris Circlet"],
            )
        assert result.exit_code == 0
        cd.get_mod_tiers.assert_called_once()
        call_kwargs = cd.get_mod_tiers.call_args
        assert call_kwargs.kwargs.get("ilvl") == 84

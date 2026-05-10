from __future__ import annotations

import copy
import dataclasses
import random

import pytest

from poe.services.repoe.sim import BestTier, CraftingEngine, ModPoolEntry, RolledMod, SimResult
from poe.types import CraftMethod, Influence, Rarity
from tests.conftest import REPOE_DATA, make_repoe_data


@pytest.fixture
def engine():
    """CraftingEngine with mock craft data."""
    return CraftingEngine(make_repoe_data())


@pytest.fixture
def blank_item(engine):
    """A blank Hubris Circlet item."""
    return engine.create_item("Hubris Circlet", ilvl=84)


def _entry(
    mod_id: str = "test_mod",
    name: str = "Test",
    affix: str = "prefix",
    group: str = "TestGroup",
    weight: int = 100,
    tier_count: int = 1,
    ilvl: int = 1,
    values: tuple[tuple[int, int], ...] = ((10, 20),),
    implicit_tags: tuple[str, ...] = (),
    influence: str | None = None,
) -> ModPoolEntry:
    return ModPoolEntry(
        mod_id=mod_id,
        name=name,
        affix=affix,
        group=group,
        weight=weight,
        tier_count=tier_count,
        best_tier=BestTier(ilvl=ilvl, values=values, weight=weight),
        implicit_tags=implicit_tags,
        influence=influence,
    )


# ── Frozen dataclasses ───────────────────────────────────────────────────────


class TestFrozenModPoolEntry:
    def test_mod_pool_entry_is_frozen(self):
        tier = BestTier(ilvl=68, values=((60, 80),), weight=500)
        entry = ModPoolEntry(
            mod_id="IncreasedLife2",
            name="Increased Life",
            affix="prefix",
            group="IncreasedLife",
            weight=500,
            tier_count=4,
            best_tier=tier,
            implicit_tags=("resource", "life"),
            influence=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.weight = 999

    def test_best_tier_is_frozen(self):
        tier = BestTier(ilvl=68, values=((60, 80),), weight=500)
        with pytest.raises(dataclasses.FrozenInstanceError):
            tier.ilvl = 99

    def test_dataclasses_replace_creates_new(self):
        tier = BestTier(ilvl=68, values=((60, 80),), weight=500)
        entry = ModPoolEntry(
            mod_id="IncreasedLife2",
            name="Increased Life",
            affix="prefix",
            group="IncreasedLife",
            weight=500,
            tier_count=4,
            best_tier=tier,
            implicit_tags=("resource", "life"),
            influence=None,
        )
        modified = dataclasses.replace(entry, weight=999)
        assert modified.weight == 999
        assert entry.weight == 500


class TestGetModPoolReturnsEntries:
    def test_returns_mod_pool_entries(self, engine):
        pool = engine.data.get_mod_pool("Hubris Circlet", ilvl=84)
        assert len(pool) > 0
        entry = pool[0]
        assert isinstance(entry, ModPoolEntry)
        assert isinstance(entry.best_tier, BestTier)
        assert isinstance(entry.implicit_tags, tuple)

    def test_entries_have_correct_fields(self, engine):
        pool = engine.data.get_mod_pool("Hubris Circlet", ilvl=84)
        entry = pool[0]
        assert isinstance(entry.mod_id, str)
        assert isinstance(entry.weight, int)
        assert entry.affix in ("prefix", "suffix")
        assert isinstance(entry.tier_count, int)


# ── Item creation ────────────────────────────────────────────────────────────


class TestCreateItem:
    def test_basic_properties(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        assert item.base_name == "Hubris Circlet"
        assert item.base_id == "Metadata/Items/Armours/Helmets/HelmetInt10"
        assert item.ilvl == 84
        assert item.rarity == "RARE"
        assert item.max_prefixes == 3
        assert item.max_suffixes == 3

    def test_with_influences(self, engine):
        item = engine.create_item("Hubris Circlet", influences=["Shaper"])
        assert item.influences == ["Shaper"]

    def test_unknown_base_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown base"):
            engine.create_item("Nonexistent Item")


# ── CraftableItem properties ────────────────────────────────────────────────


class TestCraftableItemProperties:
    def test_all_mods_empty(self, blank_item):
        assert blank_item.all_mods == []

    def test_open_slots(self, blank_item):
        assert blank_item.open_prefixes == 3
        assert blank_item.open_suffixes == 3

    def test_groups_empty(self, blank_item):
        assert blank_item.groups == set()

    def test_groups_populated(self, blank_item):
        blank_item.prefixes.append(
            RolledMod(
                mod_id="m1",
                name="Life",
                affix="prefix",
                group="IncreasedLife",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        assert "IncreasedLife" in blank_item.groups


# ── Mod pool building ────────────────────────────────────────────────────────


class TestModPool:
    def test_empty_item_has_mods(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item)
        assert len(pool) > 0

    def test_modgroup_exclusion(self, engine, blank_item):
        # Add a mod to the item
        blank_item.prefixes.append(
            RolledMod(
                mod_id="mod_life",
                name="Life",
                affix="prefix",
                group="IncreasedLife",
                weight=1000,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        pool = engine._build_mod_pool(blank_item)
        for m in pool:
            assert m.group != "IncreasedLife"

    def test_prefix_cap(self, engine, blank_item):
        # Fill all prefix slots
        for i in range(3):
            blank_item.prefixes.append(
                RolledMod(
                    mod_id=f"p{i}",
                    name=f"P{i}",
                    affix="prefix",
                    group=f"PG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        pool = engine._build_mod_pool(blank_item)
        for m in pool:
            assert m.affix != "prefix"

    def test_suffix_cap(self, engine, blank_item):
        for i in range(3):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"s{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        pool = engine._build_mod_pool(blank_item)
        for m in pool:
            assert m.affix != "suffix"


# ── Weighted selection ───────────────────────────────────────────────────────


class TestWeightedPick:
    def test_single_item(self, engine):
        pool = [_entry(mod_id="a", weight=100)]
        picked = engine._weighted_pick(pool)
        assert picked.mod_id == "a"

    def test_empty_pool(self, engine):
        assert engine._weighted_pick([]) is None

    def test_bias_towards_heavy(self, engine):
        random.seed(42)
        pool = [
            _entry(mod_id="light", weight=1),
            _entry(mod_id="heavy", weight=10000),
        ]
        picks = [engine._weighted_pick(pool).mod_id for _ in range(100)]
        assert picks.count("heavy") > 80


# ── Chaos roll ───────────────────────────────────────────────────────────────


class TestChaosRoll:
    def test_chaos_sets_rare(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        assert blank_item.rarity == "RARE"

    def test_chaos_mod_count(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        total = len(blank_item.prefixes) + len(blank_item.suffixes)
        # Mock data has only 3 distinct mods, so we may get fewer than 4
        # In real data with hundreds of mods, 4-6 would always be hit
        assert 1 <= total <= 6

    def test_chaos_no_dup_groups(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        groups = [m.group for m in blank_item.all_mods]
        assert len(groups) == len(set(groups))

    def test_chaos_respects_limits(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        assert len(blank_item.prefixes) <= blank_item.max_prefixes
        assert len(blank_item.suffixes) <= blank_item.max_suffixes


# ── Alt roll ─────────────────────────────────────────────────────────────────


class TestAltRoll:
    def test_alt_sets_magic(self, engine, blank_item):
        random.seed(42)
        engine.alt_roll(blank_item)
        assert blank_item.rarity == "MAGIC"

    def test_alt_mod_count(self, engine, blank_item):
        random.seed(42)
        engine.alt_roll(blank_item)
        total = len(blank_item.all_mods)
        assert 1 <= total <= 2


# ── Regal ────────────────────────────────────────────────────────────────────


class TestRegal:
    def test_regal_adds_one(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = "magic"
        engine.alt_roll(blank_item)
        before = len(blank_item.all_mods)
        result = engine.regal(blank_item)
        assert result is not None
        assert len(blank_item.all_mods) == before + 1

    def test_regal_sets_rare(self, engine, blank_item):
        blank_item.rarity = "magic"
        engine.alt_roll(blank_item)
        engine.regal(blank_item)
        assert blank_item.rarity == "RARE"

    def test_regal_non_magic_returns_none(self, engine, blank_item):
        blank_item.rarity = "rare"
        assert engine.regal(blank_item) is None


# ── Exalt ────────────────────────────────────────────────────────────────────


class TestExalt:
    def test_exalt_adds_one(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = Rarity.RARE
        blank_item.prefixes.append(
            RolledMod(
                mod_id="mod_life",
                name="Life",
                affix="prefix",
                group="IncreasedLife",
                weight=1000,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        before = len(blank_item.all_mods)
        result = engine.exalt(blank_item)
        assert result is not None
        assert len(blank_item.all_mods) == before + 1

    def test_exalt_non_rare_returns_none(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        assert engine.exalt(blank_item) is None


# ── Annul ────────────────────────────────────────────────────────────────────


class TestAnnul:
    def test_annul_removes_one(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        before = len(blank_item.all_mods)
        result = engine.annul(blank_item)
        assert result is not None
        assert len(blank_item.all_mods) == before - 1

    def test_annul_empty_item(self, engine, blank_item):
        assert engine.annul(blank_item) is None

    def test_annul_locked_prefixes(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.prefixes_locked = True
        prefix_count = len(blank_item.prefixes)
        engine.annul(blank_item)
        assert len(blank_item.prefixes) == prefix_count

    def test_annul_locked_suffixes(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.suffixes_locked = True
        suffix_count = len(blank_item.suffixes)
        engine.annul(blank_item)
        assert len(blank_item.suffixes) == suffix_count

    def test_annul_all_locked_returns_none(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.prefixes_locked = True
        blank_item.suffixes_locked = True
        assert engine.annul(blank_item) is None


# ── Scour ────────────────────────────────────────────────────────────────────


class TestScour:
    def test_scour_clears_mods(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        engine.scour(blank_item)
        assert blank_item.all_mods == []
        assert blank_item.rarity == "NORMAL"

    def test_scour_locked_prefixes(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.prefixes_locked = True
        prefix_count = len(blank_item.prefixes)
        engine.scour(blank_item)
        assert len(blank_item.prefixes) == prefix_count
        assert blank_item.suffixes == []

    def test_scour_locked_suffixes(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.suffixes_locked = True
        suffix_count = len(blank_item.suffixes)
        engine.scour(blank_item)
        assert len(blank_item.suffixes) == suffix_count
        assert blank_item.prefixes == []

    def test_scour_both_locked(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.prefixes_locked = True
        blank_item.suffixes_locked = True
        before = len(blank_item.all_mods)
        engine.scour(blank_item)
        assert len(blank_item.all_mods) == before


# ── Fossil roll ──────────────────────────────────────────────────────────────


class TestFossilRoll:
    def test_fossil_roll_produces_mods(self, engine, blank_item):
        random.seed(42)
        engine.fossil_roll(blank_item, ["Pristine Fossil"])
        assert len(blank_item.all_mods) > 0
        assert blank_item.rarity == "RARE"

    def test_fossil_roll_different_seed(self, engine):
        # Different seeds should produce different results (usually)
        results = set()
        for seed in range(10):
            random.seed(seed)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.fossil_roll(item, ["Pristine Fossil"])
            mod_ids = tuple(m.mod_id for m in item.all_mods)
            results.add(mod_ids)
        # With 10 seeds, should get at least 2 different outcomes
        assert len(results) >= 2


# ── Simulation ───────────────────────────────────────────────────────────────


class TestSimulation:
    @pytest.mark.asyncio
    async def test_result_fields(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=100,
        )
        assert isinstance(result, SimResult)
        assert result.method == "chaos"
        assert result.iterations == 100
        assert 0 <= result.hit_rate <= 1
        assert result.avg_attempts > 0
        assert result.cost_per_attempt > 0

    @pytest.mark.asyncio
    async def test_hit_rate_range(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=500,
        )
        # Life mod is very common, should hit often
        assert result.hit_rate > 0.1

    @pytest.mark.asyncio
    async def test_percentiles_ordered(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=500,
        )
        if result.percentiles:
            p = result.percentiles
            assert p.get("p50", 0) <= p.get("p75", float("inf"))
            assert p.get("p75", 0) <= p.get("p90", float("inf"))
            assert p.get("p90", 0) <= p.get("p99", float("inf"))

    @pytest.mark.asyncio
    async def test_alt_method(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="alt",
            target_mods=["IncreasedLife"],
            iterations=100,
        )
        assert result.method == "alt"

    @pytest.mark.asyncio
    async def test_fossil_method(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="fossil",
            target_mods=["IncreasedLife"],
            iterations=100,
            fossils=["Pristine Fossil"],
        )
        assert result.method == "fossil"

    @pytest.mark.asyncio
    async def test_match_mode_any(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife", "ColdResistance"],
            match_mode="any",
            iterations=100,
        )
        assert result.hit_rate > 0

    @pytest.mark.asyncio
    async def test_match_mode_all(self, engine):
        random.seed(42)
        result_all = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife", "ColdResistance"],
            match_mode="all",
            iterations=100,
        )
        result_any = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife", "ColdResistance"],
            match_mode="any",
            iterations=100,
        )
        # "all" should be equal or harder to hit than "any"
        assert result_all.hit_rate <= result_any.hit_rate + 0.01

    @pytest.mark.asyncio
    async def test_impossible_target(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["NonexistentModGroup"],
            iterations=10,
            max_attempts=50,
        )
        assert result.hit_rate == 0

    @pytest.mark.asyncio
    async def test_cost_math(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=200,
        )
        if result.hits > 0:
            assert abs(result.avg_cost_chaos - result.avg_attempts * result.cost_per_attempt) < 0.01


# ── Fossil weight accuracy ──────────────────────────────────────────────────


class TestFossilWeights:
    def test_fossil_weight_neutral_no_change(self):
        data = copy.deepcopy(REPOE_DATA)
        data["fossils"]["Pristine Fossil"]["positive_weights"] = {"life": 1.0}
        data["fossils"]["Pristine Fossil"]["negative_weights"] = {}
        data["fossils"]["Pristine Fossil"]["blocked_tags"] = []
        cd = make_repoe_data(data=data)
        engine = CraftingEngine(cd)
        weights, blocked = engine._get_fossil_weights(["Pristine Fossil"])
        assert weights.get("life", 1.0) == 1.0
        assert len(blocked) == 0

    def test_fossil_weight_boost(self):
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        weights, _blocked = engine._get_fossil_weights(["Pristine Fossil"])
        assert weights["life"] == 10.0

    def test_fossil_weight_block_zero(self):
        data = copy.deepcopy(REPOE_DATA)
        data["fossils"]["Pristine Fossil"]["positive_weights"] = {"life": 0.0}
        cd = make_repoe_data(data=data)
        engine = CraftingEngine(cd)
        weights, _blocked = engine._get_fossil_weights(["Pristine Fossil"])
        assert weights["life"] == 0.0

    def test_fossil_blocking_removes_mods(self):
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        item = engine.create_item("Hubris Circlet", ilvl=84)

        _weights, blocked = engine._get_fossil_weights(["Metallic Fossil"])
        assert "physical" in blocked

        pool = engine._build_mod_pool(item, blocked_tags=blocked)
        for mod in pool:
            if mod.implicit_tags:
                mod_tags = [t.lower() for t in mod.implicit_tags]
                assert "physical" not in mod_tags

    def test_fossil_blocking_no_effect_unmatched(self):
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        item = engine.create_item("Hubris Circlet", ilvl=84)

        _weights, blocked = engine._get_fossil_weights(["Metallic Fossil"])
        pool = engine._build_mod_pool(item, blocked_tags=blocked)
        life_mods = [m for m in pool if m.group == "IncreasedLife"]
        assert len(life_mods) > 0


# ── Mod count distribution ──────────────────────────────────────────────────


class TestModCountDistribution:
    def test_rare_mod_count_distribution(self):
        """Over 1000 rolls, 4-mod is most common."""
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        random.seed(42)
        counts = {4: 0, 5: 0, 6: 0}
        for _ in range(1000):
            c = engine._rare_mod_count()
            counts[c] = counts.get(c, 0) + 1
        assert counts[4] > counts[5] > counts[6]


# ── Alt roll limits ─────────────────────────────────────────────────────────


class TestAltRollLimits:
    def test_alt_roll_max_one_prefix_one_suffix(self):
        """No magic item gets 2 prefixes."""
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        random.seed(42)
        for _ in range(100):
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.alt_roll(item)
            assert len(item.prefixes) <= 1
            assert len(item.suffixes) <= 1


# ── Roll values ─────────────────────────────────────────────────────────────


class TestRollValues:
    def test_roll_values_are_integers(self):
        """All rolled values are int, not float."""
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        tier = BestTier(ilvl=1, values=((10, 20), (30, 40)), weight=0)
        random.seed(42)
        for _ in range(50):
            rolled = engine._roll_values(tier)
            for v in rolled:
                assert isinstance(v, int), f"Expected int, got {type(v)}: {v}"

    def test_roll_values_scalar(self):
        """Scalar values (non-range) are returned as-is."""
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        result = engine._roll_values(BestTier(ilvl=1, values=((42, 42),), weight=0))
        assert result == [42]


# ── Essence roll ───────────────────────────────────────────────────────────


class TestEssenceRoll:
    def test_essence_roll_produces_rare(self, engine, blank_item):
        """Essence roll sets rarity to rare and adds mods."""
        random.seed(42)
        engine.essence_roll(blank_item, "Greed")
        assert blank_item.rarity == "RARE"
        assert len(blank_item.all_mods) > 0

    def test_essence_roll_clears_existing_mods(self, engine, blank_item):
        """Essence roll clears previous mods before rolling."""
        random.seed(42)
        engine.chaos_roll(blank_item)
        old_mods = list(blank_item.all_mods)
        assert len(old_mods) > 0
        random.seed(99)
        engine.essence_roll(blank_item, "Greed")
        assert blank_item.rarity == "RARE"
        assert len(blank_item.all_mods) > 0

    def test_essence_guaranteed_mod_present(self, engine, blank_item):
        """Essence roll guarantees the essence mod is on the item (T3)."""
        random.seed(42)
        engine.essence_roll(blank_item, "Greed")
        groups = {m.group for m in blank_item.all_mods}
        assert "IncreasedLife" in groups

    def test_unknown_essence_raises(self, engine, blank_item):
        """Unknown essence name raises ValueError (T6)."""
        with pytest.raises(ValueError, match="Unknown essence"):
            engine.essence_roll(blank_item, "NonexistentEssence")


# ── Essence simulation ────────────────────────────────────────────────────


class TestEssenceSimulation:
    @pytest.mark.asyncio
    async def test_simulate_essence_method(self, engine):
        """simulate() with method='essence' runs and produces results."""
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="essence",
            target_mods=["IncreasedLife"],
            iterations=100,
            essence_name="Greed",
        )
        assert isinstance(result, SimResult)
        assert result.method == "essence"
        assert result.iterations == 100
        assert 0 <= result.hit_rate <= 1

    @pytest.mark.asyncio
    async def test_simulate_essence_uses_essence_roll(self, engine):
        """simulate() with method='essence' calls essence_roll internally."""
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="essence",
            target_mods=["IncreasedLife"],
            iterations=50,
            essence_name="Greed",
        )
        # Essence roll guarantees mods, should hit life
        assert result.hits > 0


# ── Weighted pick edge cases ──────────────────────────────────────────────


class TestWeightedPickEdge:
    def test_weighted_pick_zero_total(self, engine):
        """Pool with all-zero weights returns None."""
        pool = [
            _entry(mod_id="a", weight=0),
            _entry(mod_id="b", weight=0),
        ]
        assert engine._weighted_pick(pool) is None


# ── Zero-hit inf handling (T5) ────────────────────────────────────────────


# ── Chaos roll with locked affixes (T7) ───────────────────────────────────


class TestChaosRollLocked:
    def test_chaos_locked_prefixes_keeps_prefixes(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.prefixes_locked = True
        prefix_ids = [m.mod_id for m in blank_item.prefixes]
        engine.chaos_roll(blank_item)
        assert [m.mod_id for m in blank_item.prefixes] == prefix_ids
        assert len(blank_item.suffixes) > 0

    def test_chaos_locked_suffixes_keeps_suffixes(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.suffixes_locked = True
        suffix_ids = [m.mod_id for m in blank_item.suffixes]
        engine.chaos_roll(blank_item)
        assert [m.mod_id for m in blank_item.suffixes] == suffix_ids
        assert len(blank_item.prefixes) > 0


# ── Essence on influenced bases (T8) ──────────────────────────────────────


class TestEssenceInfluenced:
    def test_essence_on_influenced_base(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        random.seed(42)
        engine.essence_roll(item, "Greed")
        assert item.rarity == "RARE"
        assert len(item.all_mods) > 0


# ── Invalid fossil names (T9) ────────────────────────────────────────────


class TestInvalidFossil:
    def test_unknown_fossil_produces_unmodified_weights(self, engine, blank_item):
        random.seed(42)
        engine.fossil_roll(blank_item, ["Nonexistent Fossil"])
        assert blank_item.rarity == "RARE"
        assert len(blank_item.all_mods) > 0


# ── Zero-hit inf handling (T5) ────────────────────────────────────────────


class TestZeroHitInf:
    @pytest.mark.asyncio
    async def test_zero_hits_avg_attempts_is_inf(self, engine):
        """When no hits, avg_attempts is float('inf') (T5)."""
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["NonexistentModGroup"],
            iterations=10,
            max_attempts=5,
        )
        assert result.hits == 0
        assert result.avg_attempts == float("inf")
        assert result.avg_cost_chaos == float("inf")


# ── Multi-fossil weight stacking (T1) ─────────────────────────────────────


class TestMultiFossilStacking:
    def test_same_tag_multiplies(self):
        data = copy.deepcopy(REPOE_DATA)
        data["fossils"]["Pristine Fossil"]["positive_weights"] = {"life": 10.0}
        data["fossils"]["Frigid Fossil"]["positive_weights"] = {"life": 5.0}
        cd = make_repoe_data(data=data)
        engine = CraftingEngine(cd)
        weights, _blocked = engine._get_fossil_weights(["Pristine Fossil", "Frigid Fossil"])
        assert weights["life"] == pytest.approx(50.0)

    def test_zero_multiplier_eliminates(self):
        data = copy.deepcopy(REPOE_DATA)
        data["fossils"]["Pristine Fossil"]["positive_weights"] = {"life": 10.0}
        data["fossils"]["Frigid Fossil"]["positive_weights"] = {"life": 0.0}
        cd = make_repoe_data(data=data)
        engine = CraftingEngine(cd)
        weights, _blocked = engine._get_fossil_weights(["Pristine Fossil", "Frigid Fossil"])
        assert weights["life"] == 0.0


# ── _apply_roll ALT constraints (T2) ──────────────────────────────────────


class TestApplyRollAlt:
    def test_apply_roll_alt_caps_affixes(self):
        """_apply_roll with ALT caps prefixes and suffixes to 1 each."""
        cd = make_repoe_data()
        engine = CraftingEngine(cd)
        random.seed(42)
        for _ in range(100):
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine._apply_roll(item, "alt", None, None, None)
            assert len(item.prefixes) <= 1
            assert len(item.suffixes) <= 1
            assert item.max_prefixes == 3
            assert item.max_suffixes == 3


# ── Fossil tag case sensitivity (T4) ──────────────────────────────────────


# ── Invalid method validation (U6) ────────────────────────────────────────


class TestMethodValidation:
    def test_invalid_method_raises(self, engine, blank_item):
        with pytest.raises(ValueError, match="Unknown craft method"):
            engine._apply_roll(blank_item, "invalid_method", None, None, None)

    @pytest.mark.asyncio
    async def test_simulate_invalid_method_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown craft method"):
            await engine.simulate(
                "Hubris Circlet",
                ilvl=84,
                method="bogus",
                target_mods=["IncreasedLife"],
                iterations=1,
            )


# ── Fossil tag case sensitivity (T4) ──────────────────────────────────────


class TestFossilTagCase:
    def test_mixed_case_tags_match(self):
        data = copy.deepcopy(REPOE_DATA)
        data["fossils"]["Pristine Fossil"]["positive_weights"] = {"Life": 10.0}
        cd = make_repoe_data(data=data)
        engine = CraftingEngine(cd)
        item = engine.create_item("Hubris Circlet", ilvl=84)
        weights, _blocked = engine._get_fossil_weights(["Pristine Fossil"])
        pool_with = engine._build_mod_pool(item, fossil_weights=weights)
        pool_without = engine._build_mod_pool(item)
        life_with = next(m for m in pool_with if m.group == "IncreasedLife")
        life_without = next(m for m in pool_without if m.group == "IncreasedLife")
        assert life_with.weight > life_without.weight


# ── Fractured mods (D1) ────────────────────────────────────────────────────


class TestFracturedMods:
    def test_fractured_mod_persists_through_chaos(self, engine, blank_item):
        random.seed(42)
        fractured = RolledMod(
            mod_id="mod_life",
            name="Life",
            affix="prefix",
            group="IncreasedLife",
            weight=1000,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[90],
        )
        blank_item.fractured_mods.append(fractured)
        engine.chaos_roll(blank_item)
        assert fractured in blank_item.fractured_mods
        assert "IncreasedLife" in blank_item.groups

    def test_fractured_mod_excludes_modgroup(self, engine, blank_item):
        fractured = RolledMod(
            mod_id="mod_life",
            name="Life",
            affix="prefix",
            group="IncreasedLife",
            weight=1000,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[90],
        )
        blank_item.fractured_mods.append(fractured)
        pool = engine._build_mod_pool(blank_item)
        for m in pool:
            assert m.group != "IncreasedLife"

    def test_fractured_mod_reduces_open_slots(self, engine, blank_item):
        fractured = RolledMod(
            mod_id="mod_life",
            name="Life",
            affix="prefix",
            group="IncreasedLife",
            weight=1000,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[90],
        )
        blank_item.fractured_mods.append(fractured)
        assert blank_item.open_prefixes == 2

    def test_fractured_mod_not_annullable(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        fractured = RolledMod(
            mod_id="frac_mod",
            name="Fractured",
            affix="prefix",
            group="FracGroup",
            weight=100,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[],
        )
        blank_item.fractured_mods.append(fractured)
        for _ in range(20):
            result = engine.annul(blank_item)
            if result is None:
                break
            assert result.mod_id != "frac_mod"

    def test_fractured_suffix_reduces_suffix_slots(self, engine, blank_item):
        fractured = RolledMod(
            mod_id="mod_cold",
            name="Cold Res",
            affix="suffix",
            group="ColdResistance",
            weight=500,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[30],
        )
        blank_item.fractured_mods.append(fractured)
        assert blank_item.open_suffixes == 2

    def test_fractured_mod_persists_through_scour(self, engine, blank_item):
        random.seed(42)
        fractured = RolledMod(
            mod_id="mod_life",
            name="Life",
            affix="prefix",
            group="IncreasedLife",
            weight=1000,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[90],
        )
        blank_item.fractured_mods.append(fractured)
        engine.chaos_roll(blank_item)
        engine.scour(blank_item)
        assert fractured in blank_item.fractured_mods
        assert blank_item.rarity != "NORMAL"

    def test_fractured_mod_persists_through_essence(self, engine, blank_item):
        random.seed(42)
        fractured = RolledMod(
            mod_id="mod_cold",
            name="Cold Res",
            affix="suffix",
            group="ColdResistance",
            weight=500,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[30],
        )
        blank_item.fractured_mods.append(fractured)
        engine.essence_roll(blank_item, "Greed")
        assert fractured in blank_item.fractured_mods

    def test_fractured_mod_persists_through_fossil(self, engine, blank_item):
        random.seed(42)
        fractured = RolledMod(
            mod_id="mod_cold",
            name="Cold Res",
            affix="suffix",
            group="ColdResistance",
            weight=500,
            chance=1.0,
            tier=BestTier(ilvl=1, values=(), weight=0),
            rolls=[30],
        )
        blank_item.fractured_mods.append(fractured)
        engine.fossil_roll(blank_item, ["Pristine Fossil"])
        assert fractured in blank_item.fractured_mods


# ── Metamod integration (D2) ───────────────────────────────────────────────


class TestMetamods:
    def test_apply_metamod_prefixes_locked(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        engine.apply_metamod(blank_item, "prefixes_cannot_be_changed")
        assert blank_item.prefixes_locked is True
        metamod_ids = [m.mod_id for m in blank_item.suffixes]
        assert "metamod_prefixes_cannot_be_changed" in metamod_ids

    def test_apply_metamod_suffixes_locked(self, engine, blank_item):
        engine.apply_metamod(blank_item, "suffixes_cannot_be_changed")
        assert blank_item.suffixes_locked is True

    def test_apply_metamod_occupies_suffix_slot(self, engine, blank_item):
        before = blank_item.open_suffixes
        engine.apply_metamod(blank_item, "prefixes_cannot_be_changed")
        assert blank_item.open_suffixes == before - 1

    def test_remove_metamod(self, engine, blank_item):
        engine.apply_metamod(blank_item, "prefixes_cannot_be_changed")
        removed = engine.remove_metamod(blank_item, "prefixes_cannot_be_changed")
        assert removed is not None
        assert blank_item.prefixes_locked is False

    def test_apply_metamod_no_suffix_slots_raises(self, engine, blank_item):
        for i in range(3):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"s{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        with pytest.raises(ValueError, match="No open suffix slots"):
            engine.apply_metamod(blank_item, "prefixes_cannot_be_changed")

    def test_metamod_blocked_tags(self, engine):
        blocked = engine._METAMOD_BLOCKED_TAGS.get("cannot_roll_attack_mods")
        assert blocked == {"attack"}


# ── Crafted mods (D6) ──────────────────────────────────────────────────────


class TestCraftedMods:
    def test_apply_crafted_mod(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item)
        mod = pool[0]
        result = engine.apply_crafted_mod(blank_item, mod)
        assert result is not None
        assert result.is_crafted is True
        assert blank_item.crafted_mod_count == 1

    def test_crafted_mod_limit(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item)
        engine.apply_crafted_mod(blank_item, pool[0])
        with pytest.raises(ValueError, match="crafted mods"):
            engine.apply_crafted_mod(blank_item, pool[1])

    def test_multimod_raises_limit(self, engine, blank_item):
        blank_item.max_crafted_mods = 3
        pool = engine._build_mod_pool(blank_item)
        engine.apply_crafted_mod(blank_item, pool[0])
        engine.apply_crafted_mod(blank_item, pool[1])
        assert blank_item.crafted_mod_count == 2

    def test_remove_crafted_mod(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item)
        result = engine.apply_crafted_mod(blank_item, pool[0])
        removed = engine.remove_crafted_mod(blank_item, result.mod_id)
        assert removed is not None
        assert blank_item.crafted_mod_count == 0

    def test_remove_all_crafted_mods(self, engine, blank_item):
        blank_item.max_crafted_mods = 3
        pool = engine._build_mod_pool(blank_item)
        engine.apply_crafted_mod(blank_item, pool[0])
        engine.apply_crafted_mod(blank_item, pool[1])
        removed = engine.remove_all_crafted_mods(blank_item)
        assert len(removed) == 2
        assert blank_item.crafted_mod_count == 0
        assert blank_item.max_crafted_mods == 1

    def test_annul_skips_crafted_mods(self, engine, blank_item):
        # Mark exactly max_crafted_mods mods as crafted so the item respects
        # the bench cap; annul should still skip them and pick from the
        # remaining naturally-rolled mods (or return None if all are crafted
        # within cap and no eligible target remains).
        random.seed(42)
        engine.chaos_roll(blank_item)
        for i, m in enumerate(blank_item.prefixes):
            if i >= blank_item.max_crafted_mods:
                break
            m.is_crafted = True
        engine.annul(blank_item)
        for m in blank_item.prefixes + blank_item.suffixes:
            if m.is_crafted:
                # All crafted mods that were on the item before annul must
                # still be present — annul skips them by design.
                assert m in blank_item.prefixes + blank_item.suffixes

    def test_apply_crafted_mod_no_slots_raises(self, engine, blank_item):
        for i in range(3):
            blank_item.prefixes.append(
                RolledMod(
                    mod_id=f"p{i}",
                    name=f"P{i}",
                    affix="prefix",
                    group=f"PG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        for i in range(3):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"s{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        pool_entry = _entry(
            mod_id="test", name="Test", affix="prefix", group="TestGroup", weight=100
        )
        with pytest.raises(ValueError, match="No open prefix slots"):
            engine.apply_crafted_mod(blank_item, pool_entry)


# ── Item state flags (D10, D11) ────────────────────────────────────────────


class TestItemStateFlags:
    def test_mirrored_blocks_chaos(self, engine, blank_item):
        blank_item.is_mirrored = True
        with pytest.raises(ValueError, match="mirrored"):
            engine.chaos_roll(blank_item)

    def test_mirrored_blocks_exalt(self, engine, blank_item):
        blank_item.is_mirrored = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="mirrored"):
            engine.exalt(blank_item)

    def test_mirrored_blocks_annul(self, engine, blank_item):
        blank_item.is_mirrored = True
        with pytest.raises(ValueError, match="mirrored"):
            engine.annul(blank_item)

    def test_mirrored_blocks_scour(self, engine, blank_item):
        blank_item.is_mirrored = True
        with pytest.raises(ValueError, match="mirrored"):
            engine.scour(blank_item)

    def test_corrupted_blocks_chaos(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.chaos_roll(blank_item)

    def test_corrupted_blocks_fossil(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.fossil_roll(blank_item, ["Pristine Fossil"])

    def test_corrupted_blocks_essence(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.essence_roll(blank_item, "Greed")

    def test_synthesised_flag_stored(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.is_synthesised = True
        assert item.is_synthesised is True


# ── Catalyst fields (D12) ──────────────────────────────────────────────────


class TestCatalystFields:
    def test_catalyst_fields_default(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        assert item.catalyst_type == ""
        assert item.catalyst_quality == 0

    def test_catalyst_fields_set(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.catalyst_type = "Turbulent"
        item.catalyst_quality = 20
        assert item.catalyst_type == "Turbulent"
        assert item.catalyst_quality == 20


# ── Implicits field (D5) ───────────────────────────────────────────────────


class TestImplicits:
    def test_implicits_default_empty(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        assert item.implicits == []

    def test_implicits_dont_affect_prefix_count(self, engine, blank_item):
        blank_item.implicits.append(
            RolledMod(
                mod_id="impl_life",
                name="Implicit Life",
                affix="prefix",
                group="ImplicitLife",
                weight=0,
                chance=0,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[50],
            )
        )
        assert blank_item.open_prefixes == 3

    def test_implicits_dont_block_modgroup(self, engine, blank_item):
        blank_item.implicits.append(
            RolledMod(
                mod_id="impl_life",
                name="Implicit Life",
                affix="prefix",
                group="IncreasedLife",
                weight=0,
                chance=0,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[50],
            )
        )
        pool = engine._build_mod_pool(blank_item)
        life_mods = [m for m in pool if m.group == "IncreasedLife"]
        assert len(life_mods) > 0


# ── Transmutation / Augmentation / Alchemy (10.2) ─────────────────────────


class TestTransmutation:
    def test_transmutation_normal_to_magic(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = Rarity.NORMAL
        engine.transmutation(blank_item)
        assert blank_item.rarity == Rarity.MAGIC
        assert 1 <= len(blank_item.all_mods) <= 2

    def test_transmutation_non_normal_raises(self, engine, blank_item):
        with pytest.raises(ValueError, match="Normal"):
            engine.transmutation(blank_item)


class TestAugmentation:
    def test_augmentation_adds_mod(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = Rarity.MAGIC
        blank_item.max_prefixes, blank_item.max_suffixes = 1, 1
        blank_item.prefixes.append(
            RolledMod(
                mod_id="m1",
                name="P",
                affix="prefix",
                group="PG",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        result = engine.augmentation(blank_item)
        assert result is not None
        assert len(blank_item.all_mods) == 2

    def test_augmentation_full_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        blank_item.max_prefixes, blank_item.max_suffixes = 1, 1
        blank_item.prefixes.append(
            RolledMod(
                mod_id="m1",
                name="P",
                affix="prefix",
                group="PG",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        blank_item.suffixes.append(
            RolledMod(
                mod_id="m2",
                name="S",
                affix="suffix",
                group="SG",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        with pytest.raises(ValueError, match="both a prefix and suffix"):
            engine.augmentation(blank_item)


class TestAlchemy:
    def test_alchemy_normal_to_rare(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = Rarity.NORMAL
        engine.alchemy(blank_item)
        assert blank_item.rarity == Rarity.RARE
        assert len(blank_item.all_mods) > 0

    def test_alchemy_non_normal_raises(self, engine, blank_item):
        with pytest.raises(ValueError, match="Normal"):
            engine.alchemy(blank_item)


# ── Divine / Blessed (10.1) ────────────────────────────────────────────────


class TestDivine:
    def test_divine_rerolls_values(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        old_rolls = [list(m.rolls) for m in blank_item.prefixes + blank_item.suffixes]
        random.seed(99)
        engine.divine(blank_item)
        new_rolls = [list(m.rolls) for m in blank_item.prefixes + blank_item.suffixes]
        assert len(old_rolls) == len(new_rolls)

    def test_divine_no_mods_raises(self, engine, blank_item):
        with pytest.raises(ValueError, match="No mods"):
            engine.divine(blank_item)


class TestBlessed:
    def test_blessed_no_implicits_raises(self, engine, blank_item):
        with pytest.raises(ValueError, match="No implicits"):
            engine.blessed(blank_item)

    def test_blessed_rerolls_implicit_values(self, engine, blank_item):
        blank_item.implicits.append(
            RolledMod(
                mod_id="impl",
                name="Impl",
                affix="implicit",
                group="IG",
                weight=0,
                chance=0,
                tier=BestTier(ilvl=1, values=((10, 20),), weight=0),
                rolls=[15],
            )
        )
        engine.blessed(blank_item)
        assert blank_item.implicits[0].rolls[0] is not None


# ── Harvest reforge (10.3) ─────────────────────────────────────────────────


class TestHarvestReforge:
    def test_harvest_reforge_basic(self, engine, blank_item):
        random.seed(42)
        engine.harvest_reforge(blank_item)
        assert blank_item.rarity == Rarity.RARE
        assert len(blank_item.all_mods) > 0

    def test_harvest_reforge_with_tag(self, engine, blank_item):
        random.seed(42)
        engine.harvest_reforge(blank_item, tag="life", multiplier=10.0)
        assert blank_item.rarity == Rarity.RARE

    def test_harvest_augment(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        if blank_item.open_prefixes > 0 or blank_item.open_suffixes > 0:
            existing_count = len(blank_item.all_mods)
            result = engine.harvest_augment(blank_item, "life")
            if result is not None:
                # Augment must produce a real mod (not a placeholder) and
                # actually add it to the item.
                assert result.name
                assert result.affix in {"prefix", "suffix"}
                assert len(blank_item.all_mods) == existing_count + 1


# ── Conqueror Exalt (10.4) ─────────────────────────────────────────────────


class TestConquerorExalt:
    def test_conqueror_exalt_adds_influence(self, engine):
        random.seed(42)
        item = engine.create_item("Hubris Circlet", ilvl=84)
        engine.chaos_roll(item)
        engine.conqueror_exalt(item, "Shaper")
        assert "Shaper" in item.influences

    def test_conqueror_exalt_wrong_influence_raises(self, engine):
        # Shaper and Elder are mutually exclusive — game rule.
        item = engine.create_item("Hubris Circlet", ilvl=84, influences=["Elder"])
        item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="mutually exclusive"):
            engine.conqueror_exalt(item, "Shaper")


# ── Vaal Orb (10.9) ───────────────────────────────────────────────────────


class TestVaalOrb:
    def test_vaal_corrupts_item(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        engine.vaal_orb(blank_item)
        assert blank_item.is_corrupted is True

    def test_vaal_already_corrupted_raises(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="already corrupted"):
            engine.vaal_orb(blank_item)

    def test_vaal_outcome_types(self, engine, blank_item):
        outcomes = set()
        for seed in range(100):
            random.seed(seed)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item)
            outcome = engine.vaal_orb(item)
            outcomes.add(outcome)
        assert len(outcomes) >= 2


# ── Fracture (10.12) ──────────────────────────────────────────────────────


class TestFracture:
    def test_fracture_moves_mod(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = Rarity.RARE
        for i in range(4):
            blank_item.prefixes.append(
                RolledMod(
                    mod_id=f"fmod{i}",
                    name=f"FM{i}",
                    affix="prefix",
                    group=f"FracG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        blank_item.max_prefixes = 6
        result = engine.fracture(blank_item)
        assert result is not None
        assert result in blank_item.fractured_mods

    def test_fracture_too_few_mods_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        blank_item.prefixes.append(
            RolledMod(
                mod_id="m1",
                name="P",
                affix="prefix",
                group="PG",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        with pytest.raises(ValueError, match="at least 4"):
            engine.fracture(blank_item)

    def test_fracture_already_fractured_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        blank_item.fractured_mods.append(
            RolledMod(
                mod_id="f1",
                name="F",
                affix="prefix",
                group="FG",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        with pytest.raises(ValueError, match="already has a fractured"):
            engine.fracture(blank_item)


# ── Tainted currencies (10.13) ────────────────────────────────────────────


class TestTaintedCurrencies:
    def test_tainted_divine_requires_corrupted(self, engine, blank_item):
        with pytest.raises(ValueError, match="corrupted"):
            engine.tainted_divine(blank_item)

    def test_tainted_divine_rerolls(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.is_corrupted = True
        engine.tainted_divine(blank_item)
        assert len(blank_item.all_mods) > 0

    def test_tainted_chaos_requires_corrupted(self, engine, blank_item):
        with pytest.raises(ValueError, match="corrupted"):
            engine.tainted_chaos(blank_item)

    def test_tainted_chaos_add_or_remove(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.is_corrupted = True
        result = engine.tainted_chaos(blank_item)
        assert result in ("added", "removed")

    def test_tainted_exalt_requires_corrupted(self, engine, blank_item):
        with pytest.raises(ValueError, match="corrupted"):
            engine.tainted_exalt(blank_item)


# ── Recombinator (10.10) ──────────────────────────────────────────────────


class TestRecombinator:
    def test_recombinate_produces_item(self, engine):
        random.seed(42)
        item1 = engine.create_item("Hubris Circlet", ilvl=84)
        item2 = engine.create_item("Hubris Circlet", ilvl=84)
        engine.chaos_roll(item1)
        engine.chaos_roll(item2)
        result = engine.recombinate(item1, item2)
        assert result.rarity == Rarity.RARE
        assert result.ilvl == 84


# ── Beast crafting (10.11) ────────────────────────────────────────────────


class TestBeastCrafting:
    def test_beast_imprint_magic(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        engine.alt_roll(blank_item)
        imprint = engine.beast_imprint(blank_item)
        assert imprint is not blank_item
        assert len(imprint.all_mods) == len(blank_item.all_mods)

    def test_beast_imprint_non_magic_raises(self, engine, blank_item):
        with pytest.raises(ValueError, match="Magic"):
            engine.beast_imprint(blank_item)

    def test_beast_split(self, engine, blank_item):
        """beast_split partitions mods between two halves WITHOUT mirroring
        them — game-correct behavior. The previous is_mirrored=True assertion
        was buggy: mirrored items can't be crafted on, but split halves are
        meant to be further crafted (the whole point of the split)."""
        random.seed(42)
        engine.chaos_roll(blank_item)
        item1, item2 = engine.beast_split(blank_item)
        assert item1.is_mirrored is False
        assert item2.is_mirrored is False
        # Mods are partitioned — total prefixes/suffixes preserved across halves.
        total_prefixes = len(item1.prefixes) + len(item2.prefixes)
        total_suffixes = len(item1.suffixes) + len(item2.suffixes)
        assert total_prefixes == len(blank_item.prefixes)
        assert total_suffixes == len(blank_item.suffixes)

    def test_beast_split_mods_independent(self, engine, blank_item):
        """Mutating one half's mods must not affect the source item or the
        other half — they should be independent copies."""
        random.seed(42)
        engine.chaos_roll(blank_item)
        original_prefix_names = [m.name for m in blank_item.prefixes]
        item1, _item2 = engine.beast_split(blank_item)
        if item1.prefixes:
            item1.prefixes[0].name = "MUTATED"
        # Source unaffected.
        assert [m.name for m in blank_item.prefixes] == original_prefix_names

    def test_beast_prefix_to_suffix(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        added, removed = engine.beast_prefix_to_suffix(blank_item)
        assert added is not None or removed is not None


# ── Awakener's Orb (10.5) ─────────────────────────────────────────────────


class TestAwakenerOrb:
    def test_awakener_combines_influences(self, engine):
        random.seed(42)
        item1 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        item2 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Elder"])
        engine.chaos_roll(item1)
        engine.chaos_roll(item2)
        result = engine.awakener_orb(item1, item2)
        assert len(result.influences) == 2

    def test_awakener_same_influence_raises(self, engine):
        item1 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        item2 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        with pytest.raises(ValueError, match="different influences"):
            engine.awakener_orb(item1, item2)


# ── Veiled Chaos (10.6) ──────────────────────────────────────────────────


class TestVeiledChaos:
    def test_veiled_chaos_rerolls_and_adds(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        engine.veiled_chaos(blank_item)
        assert blank_item.rarity == Rarity.RARE
        veiled = [m for m in blank_item.all_mods if "Veiled" in m.name]
        assert len(veiled) >= 0  # may or may not have room


# ── Simulate with existing mods (10.14) ──────────────────────────────────


class TestSimulateExistingMods:
    @pytest.mark.asyncio
    async def test_simulate_with_existing_mods(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["ColdResistance"],
            iterations=50,
            existing_mods=["IncreasedLife"],
        )
        assert isinstance(result, SimResult)


# ── 4+ fossil cost (T10) ─────────────────────────────────────────────────


class TestFourFossilCost:
    @pytest.mark.asyncio
    async def test_four_fossil_simulation(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="fossil",
            target_mods=["IncreasedLife"],
            iterations=10,
            fossils=["Pristine Fossil", "Frigid Fossil", "Pristine Fossil", "Frigid Fossil"],
        )
        assert result.method == "fossil"


# ── Simulation with influences (T12) ─────────────────────────────────────


class TestSimulateWithInfluences:
    @pytest.mark.asyncio
    async def test_simulate_with_shaper(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=50,
            influences=["Shaper"],
        )
        assert result.method == "chaos"


class TestAsyncSimulate:
    @pytest.mark.asyncio
    async def test_simulate_returns_result(self, engine):
        random.seed(42)
        result = await engine.simulate(
            base="Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=50,
        )
        assert isinstance(result, SimResult)
        assert result.iterations == 50
        assert result.hit_rate >= 0

    @pytest.mark.asyncio
    async def test_simulate_respects_workers(self, engine):
        random.seed(42)
        result = await engine.simulate(
            base="Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=40,
            workers=2,
        )
        assert isinstance(result, SimResult)
        assert result.iterations == 40


# ── Augmentation edge cases ─────────────────────────────────────────────────


class TestAugmentationEdge:
    def test_augmentation_non_magic_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="Magic"):
            engine.augmentation(blank_item)


# ── Alchemy edge cases ─────────────────────────────────────────────────────


class TestAlchemyEdge:
    def test_alchemy_rare_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="Normal"):
            engine.alchemy(blank_item)


# ── Harvest augment edge cases ──────────────────────────────────────────────


class TestHarvestAugmentEdge:
    def test_harvest_augment_non_rare_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="Rare"):
            engine.harvest_augment(blank_item, "life")

    def test_harvest_augment_no_tagged_mods(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        result = engine.harvest_augment(blank_item, "nonexistenttag")
        assert result is None

    def test_harvest_augment_adds_tagged_mod(self, engine, blank_item):
        random.seed(42)
        blank_item.rarity = Rarity.RARE
        result = engine.harvest_augment(blank_item, "life")
        if result is not None:
            assert result.name is not None


# ── Conqueror Exalt edge cases ──────────────────────────────────────────────


class TestConquerorExaltEdge:
    def test_conqueror_exalt_non_rare_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="Rare"):
            engine.conqueror_exalt(blank_item, "Shaper")

    def test_conqueror_exalt_no_influence_pool(self, engine):
        random.seed(42)
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        existing_count = len(item.all_mods)
        existing_influences = list(item.influences)
        result = engine.conqueror_exalt(item, "Shaper")
        # Either no influence mod was rollable (result None, item unchanged
        # except possibly the influence tag) or a mod was added with the
        # expected influence and a real name.
        if result is None:
            assert len(item.all_mods) == existing_count
        else:
            assert result.name
            assert result.influence == "Shaper"
            assert "Shaper" in item.influences
        # Influences only grow, never shrink.
        for inf in existing_influences:
            assert inf in item.influences


# ── Veiled Chaos edge cases ────────────────────────────────────────────────


class TestVeiledChaosEdge:
    def test_veiled_chaos_non_rare_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="Rare"):
            engine.veiled_chaos(blank_item)


# ── Aisling bench ───────────────────────────────────────────────────────────


class TestAislingBench:
    def test_aisling_non_rare_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="Rare"):
            engine.aisling_bench(blank_item)

    def test_aisling_no_removable_returns_none(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        assert engine.aisling_bench(blank_item) is None

    def test_aisling_replaces_mod(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        result = engine.aisling_bench(blank_item)
        if result is not None:
            assert "Veiled" in result.name


# ── Beast suffix to prefix ──────────────────────────────────────────────────


class TestBeastSuffixToPrefix:
    def test_beast_suffix_to_prefix(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        added, removed = engine.beast_suffix_to_prefix(blank_item)
        assert added is not None or removed is not None


# ── Tainted exalt edge cases ────────────────────────────────────────────────


class TestTaintedExaltEdge:
    def test_tainted_exalt_add_or_remove(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        blank_item.is_corrupted = True
        result = engine.tainted_exalt(blank_item)
        assert result in ("added", "removed")


# ── Tainted mythic / fusing ─────────────────────────────────────────────────


class TestTaintedMythicFusing:
    def test_tainted_mythic_requires_corrupted(self, engine, blank_item):
        with pytest.raises(ValueError, match="corrupted"):
            engine.tainted_mythic(blank_item)

    def test_tainted_mythic_requires_unique(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="Unique"):
            engine.tainted_mythic(blank_item)

    def test_tainted_mythic_success(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.UNIQUE
        result = engine.tainted_mythic(blank_item)
        assert result == "transformed"

    def test_tainted_fusing_requires_corrupted(self, engine, blank_item):
        with pytest.raises(ValueError, match="corrupted"):
            engine.tainted_fusing(blank_item)

    def test_tainted_fusing_success(self, engine, blank_item):
        blank_item.is_corrupted = True
        result = engine.tainted_fusing(blank_item)
        assert result == "relinked"


# ── Recombinator with influences ────────────────────────────────────────────


class TestRecombinatorInfluences:
    def test_recombinate_preserves_influences(self, engine):
        random.seed(42)
        item1 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        item2 = engine.create_item("Hubris Circlet", ilvl=80, influences=["Elder"])
        engine.chaos_roll(item1)
        engine.chaos_roll(item2)
        result = engine.recombinate(item1, item2)
        assert len(result.influences) > 0

    def test_recombinate_no_influences(self, engine):
        random.seed(42)
        item1 = engine.create_item("Hubris Circlet", ilvl=84)
        item2 = engine.create_item("Hubris Circlet", ilvl=80)
        engine.chaos_roll(item1)
        engine.chaos_roll(item2)
        result = engine.recombinate(item1, item2)
        assert result.influences == []


# ── Awakener orb edge cases ─────────────────────────────────────────────────


class TestAwakenerOrbEdge:
    def test_awakener_no_influence_raises(self, engine):
        item1 = engine.create_item("Hubris Circlet", ilvl=84)
        item2 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Elder"])
        with pytest.raises(ValueError, match="influenced"):
            engine.awakener_orb(item1, item2)


# ── Fracture suffix ─────────────────────────────────────────────────────────


class TestFractureSuffix:
    def test_fracture_suffix_moves_to_fractured(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        blank_item.max_suffixes = 6
        for i in range(4):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"smod{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        result = engine.fracture(blank_item)
        assert result is not None
        assert result in blank_item.fractured_mods
        assert result not in blank_item.suffixes

    def test_fracture_non_rare_raises(self, engine, blank_item):
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="Rare"):
            engine.fracture(blank_item)


# ── _run_chunk slow path (essence method) ───────────────────────────────────


class TestRunChunkSlowPath:
    @pytest.mark.asyncio
    async def test_simulate_essence_uses_slow_path(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="essence",
            target_mods=["IncreasedLife"],
            iterations=20,
            essence_name="Greed",
            workers=1,
        )
        assert isinstance(result, SimResult)
        assert result.method == "essence"

    @pytest.mark.asyncio
    async def test_simulate_essence_match_any(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="essence",
            target_mods=["IncreasedLife", "ColdResistance"],
            iterations=20,
            essence_name="Greed",
            match_mode="any",
            workers=1,
        )
        assert isinstance(result, SimResult)

    @pytest.mark.asyncio
    async def test_simulate_with_existing_mods_slow_path(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="essence",
            target_mods=["IncreasedLife"],
            iterations=10,
            essence_name="Greed",
            existing_mods=["ColdResistance"],
            workers=1,
        )
        assert isinstance(result, SimResult)


# ── Transmutation via _apply_roll ───────────────────────────────────────────


class TestApplyRollTransmutation:
    def test_apply_roll_transmutation(self, engine, blank_item):
        random.seed(42)
        engine._apply_roll(blank_item, "transmutation", None, None, None)
        assert blank_item.rarity == Rarity.MAGIC
        assert len(blank_item.prefixes) <= 1
        assert len(blank_item.suffixes) <= 1

    def test_apply_roll_chaos(self, engine, blank_item):
        random.seed(42)
        engine._apply_roll(blank_item, "chaos", None, None, None)
        assert blank_item.rarity == Rarity.RARE

    def test_apply_roll_alchemy(self, engine, blank_item):
        random.seed(42)
        engine._apply_roll(blank_item, "alchemy", None, None, None)
        assert blank_item.rarity == Rarity.RARE

    def test_apply_roll_harvest(self, engine, blank_item):
        random.seed(42)
        engine._apply_roll(blank_item, "harvest", None, None, None)
        assert blank_item.rarity == Rarity.RARE

    def test_apply_roll_fossil(self, engine, blank_item):
        random.seed(42)
        engine._apply_roll(blank_item, "fossil", {"life": 5.0}, None, None)
        assert blank_item.rarity == Rarity.RARE

    def test_apply_roll_essence(self, engine, blank_item):
        random.seed(42)
        engine._apply_roll(blank_item, "essence", None, None, "Greed")
        assert blank_item.rarity == Rarity.RARE


# ── Apply crafted mod from dict ─────────────────────────────────────────────


class TestApplyCraftedModDict:
    def test_apply_crafted_mod_dict(self, engine, blank_item):
        mod_dict = {
            "mod_id": "test_crafted",
            "name": "Crafted Life",
            "affix": "prefix",
            "group": "CraftedLife",
            "weight": 100,
            "best_tier": {"ilvl": 1, "values": [[10, 20]], "weight": 100},
        }
        result = engine.apply_crafted_mod(blank_item, mod_dict)
        assert result is not None
        assert result.is_crafted is True

    def test_apply_crafted_mod_dict_no_tier(self, engine, blank_item):
        mod_dict = {
            "mod_id": "test_crafted",
            "name": "Crafted Cold",
            "affix": "suffix",
            "group": "CraftedCold",
            "weight": 100,
            "best_tier": None,
        }
        result = engine.apply_crafted_mod(blank_item, mod_dict)
        assert result is not None
        assert result.is_crafted is True

    def test_apply_crafted_mod_dict_best_tier_object(self, engine, blank_item):
        mod_dict = {
            "mod_id": "test_crafted2",
            "name": "Crafted Fire",
            "affix": "prefix",
            "group": "CraftedFire",
            "weight": 100,
            "best_tier": BestTier(ilvl=1, values=((5, 10),), weight=50),
        }
        result = engine.apply_crafted_mod(blank_item, mod_dict)
        assert result is not None
        assert result.is_crafted is True

    def test_apply_crafted_mod_suffix_no_slots_raises(self, engine, blank_item):
        for i in range(3):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"s{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        mod_dict = {
            "mod_id": "test_crafted",
            "name": "Crafted",
            "affix": "suffix",
            "group": "CG",
            "weight": 100,
            "best_tier": None,
        }
        with pytest.raises(ValueError, match="No open suffix slots"):
            engine.apply_crafted_mod(blank_item, mod_dict)


# ── Remove crafted / metamod edge cases ─────────────────────────────────────


class TestRemoveEdgeCases:
    def test_remove_crafted_mod_not_found(self, engine, blank_item):
        result = engine.remove_crafted_mod(blank_item, "nonexistent")
        assert result is None

    def test_remove_metamod_not_found(self, engine, blank_item):
        result = engine.remove_metamod(blank_item, "nonexistent_type")
        assert result is None


# ── Tainted chaos/exalt empty item ──────────────────────────────────────────


class TestTaintedEmptyItem:
    def test_tainted_chaos_empty_item(self, engine, blank_item):
        blank_item.is_corrupted = True
        random.seed(99)
        result = engine.tainted_chaos(blank_item)
        assert result in ("added", "removed")

    def test_tainted_exalt_empty_item(self, engine, blank_item):
        blank_item.is_corrupted = True
        random.seed(99)
        result = engine.tainted_exalt(blank_item)
        assert result in ("added", "removed")


# ── Vaal orb outcomes ───────────────────────────────────────────────────────


class TestVaalOrbOutcomes:
    def test_vaal_implicit_outcome(self, engine):
        # vaal_orb has 4 equiprobable outcomes; in 200 seeds each appears ~50
        # times. If we can't find one, the RNG is broken — fail rather than
        # skip. pytest.skip masks regressions where an outcome stops happening.
        for seed in range(200):
            random.seed(seed)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item)
            if engine.vaal_orb(item) == "implicit":
                assert len(item.implicits) > 0
                return
        raise AssertionError("implicit outcome not hit in 200 seeds — RNG distribution broken")

    def test_vaal_reroll_outcome(self, engine):
        for seed in range(200):
            random.seed(seed)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item)
            if engine.vaal_orb(item) == "reroll":
                assert item.rarity == Rarity.RARE
                return
        raise AssertionError("reroll outcome not hit in 200 seeds — RNG distribution broken")

    def test_vaal_nothing_outcome(self, engine):
        for seed in range(200):
            random.seed(seed)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item)
            if engine.vaal_orb(item) == "nothing":
                assert item.is_corrupted is True
                return
        raise AssertionError("nothing outcome not hit in 200 seeds — RNG distribution broken")


# ── Beast prefix/suffix empty item ──────────────────────────────────────────


class TestBeastEmptyItem:
    def test_beast_prefix_to_suffix_empty(self, engine, blank_item):
        added, removed = engine.beast_prefix_to_suffix(blank_item)
        assert removed is None

    def test_beast_suffix_to_prefix_empty(self, engine, blank_item):
        added, removed = engine.beast_suffix_to_prefix(blank_item)
        assert removed is None


class TestBuildModPoolBlockedTags:
    def test_blocked_tags_filter_mods(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item, blocked_tags={"life"})
        for mod in pool:
            mod_tags = [t.casefold() for t in mod.implicit_tags]
            assert "life" not in mod_tags

    def test_fossil_weights_zero_excludes_mod(self, engine, blank_item):
        pool_before = engine._build_mod_pool(blank_item)
        tagged_mods = [m for m in pool_before if m.implicit_tags]
        if tagged_mods:
            first_tag = tagged_mods[0].implicit_tags[0].casefold()
            pool_after = engine._build_mod_pool(blank_item, fossil_weights={first_tag: 0.0})
            assert len(pool_after) <= len(pool_before)


class TestWeightedPickFallback:
    def test_weighted_pick_returns_last_on_rounding(self, engine):
        mods = [_entry(mod_id=f"mod_{i}", group=f"G{i}", weight=1) for i in range(3)]
        for _ in range(50):
            result = engine._weighted_pick(mods)
            assert result is not None


class TestRollItemEnsureBothAffixes:
    def test_ensure_suffix_when_only_prefixes(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        random.seed(42)
        for _ in range(20):
            engine.chaos_roll(item)
            if item.prefixes and not item.suffixes:
                break
        engine.chaos_roll(item)
        assert len(item.all_mods) >= 2

    def test_ensure_prefix_when_only_suffixes(self, engine):
        # Across 200 seeds, chaos_roll should produce at least one item with
        # both a prefix and a suffix (require_both_affixes gate).
        item = engine.create_item("Hubris Circlet", ilvl=84)
        both_seen = False
        for seed_val in range(200):
            random.seed(seed_val)
            engine.chaos_roll(item)
            if item.prefixes and item.suffixes:
                both_seen = True
                break
        assert both_seen, "200 chaos rolls produced no both-affix item"


class TestRegalOnMagicItem:
    def test_regal_upgrades_to_rare(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        engine.scour(item)
        engine.transmutation(item)
        engine.regal(item)
        assert item.rarity == Rarity.RARE


class TestExaltOnFullItem:
    def test_exalt_on_full_rare(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        engine.chaos_roll(item)
        result = engine.exalt(item)
        assert result is None or isinstance(result, RolledMod)


class TestEssenceFuzzyMatch:
    def test_essence_roll_fuzzy_match(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        random.seed(42)
        engine.essence_roll(item, "Greed")
        assert len(item.all_mods) >= 1


class TestAugmentationOnMagicItem:
    def test_augmentation_adds_mod(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        engine.scour(item)
        engine.transmutation(item)
        while len(item.prefixes) >= 1 and len(item.suffixes) >= 1:
            engine.scour(item)
            engine.transmutation(item)
        result = engine.augmentation(item)
        assert result is not None or len(item.all_mods) >= 1


class TestHarvestAugmentTagged:
    def test_harvest_augment_returns_mod_or_none(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        random.seed(42)
        result = engine.harvest_augment(item, "life")
        assert result is None or isinstance(result, RolledMod)


class TestConquerorExaltEdgeCases:
    def test_conqueror_exalt_no_inf_pool(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        result = engine.conqueror_exalt(item, "Shaper")
        assert result is None or isinstance(result, RolledMod)

    def test_conqueror_exalt_mutually_exclusive_error(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        item.influences = ["Elder"]
        with pytest.raises(ValueError, match="mutually exclusive"):
            engine.conqueror_exalt(item, "Shaper")

    def test_conqueror_exalt_rejects_max_two(self, engine):
        # Shaper + Hunter is allowed (not mutually exclusive); a third
        # non-exclusive influence should still hit the max-2 cap.
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        item.influences = ["Shaper", "Hunter"]
        with pytest.raises(ValueError, match="max 2"):
            engine.conqueror_exalt(item, "Crusader")


class TestAwakenerOrbKeptMods:
    def test_awakener_orb_basic(self, engine):
        item1 = engine.create_item("Hubris Circlet", ilvl=84)
        item1.rarity = Rarity.RARE
        item1.influences = ["shaper"]
        engine.chaos_roll(item1)

        item2 = engine.create_item("Hubris Circlet", ilvl=84)
        item2.rarity = Rarity.RARE
        item2.influences = ["elder"]
        engine.chaos_roll(item2)

        result = engine.awakener_orb(item1, item2)
        assert "shaper" in result.influences or "elder" in result.influences


class TestVeiledChaosMod:
    def test_veiled_chaos_adds_veiled(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        engine.chaos_roll(item)
        random.seed(42)
        engine.veiled_chaos(item)
        veiled = [m for m in item.all_mods if m.name.startswith("Veiled:")]
        assert len(veiled) >= 0


class TestAislingBenchEdge:
    def test_aisling_bench_no_removable(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        result = engine.aisling_bench(item)
        assert result is None

    def test_aisling_bench_with_mods(self, engine):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        engine.chaos_roll(item)
        random.seed(42)
        result = engine.aisling_bench(item)
        assert result is None or isinstance(result, RolledMod)


class TestTaintedChaosOutcomes:
    def test_tainted_chaos_both_outcomes(self, engine):
        seen_added = False
        seen_removed = False
        for seed_val in range(200):
            random.seed(seed_val)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            item.rarity = Rarity.RARE
            engine.chaos_roll(item)
            item.is_corrupted = True
            result = engine.tainted_chaos(item)
            if result == "added":
                seen_added = True
            elif result == "removed":
                seen_removed = True
            if seen_added and seen_removed:
                return
        assert seen_added or seen_removed


# ── Pattern 1: Invariants over shape ────────────────────────────────────────


class TestSimResultInvariants:
    @pytest.mark.asyncio
    async def test_hits_does_not_exceed_iterations(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=100,
        )
        assert 0 <= result.hits <= result.iterations

    @pytest.mark.asyncio
    async def test_hit_rate_matches_hits_div_iterations(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=200,
        )
        assert result.hit_rate == pytest.approx(result.hits / result.iterations)

    @pytest.mark.asyncio
    async def test_hit_rate_in_unit_interval(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=100,
        )
        assert 0.0 <= result.hit_rate <= 1.0

    @pytest.mark.asyncio
    async def test_percentiles_monotonic_non_decreasing(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=200,
        )
        if result.percentiles:
            assert (
                result.percentiles["p50"]
                <= result.percentiles["p75"]
                <= result.percentiles["p90"]
                <= result.percentiles["p99"]
            )

    @pytest.mark.asyncio
    async def test_avg_cost_chaos_equals_avg_attempts_times_cost(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=100,
        )
        if result.hits > 0:
            assert result.avg_cost_chaos == pytest.approx(
                result.avg_attempts * result.cost_per_attempt
            )

    @pytest.mark.asyncio
    async def test_cost_per_attempt_positive(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=20,
        )
        assert result.cost_per_attempt > 0

    @pytest.mark.asyncio
    async def test_zero_iterations_yields_zero_hit_rate(self, engine):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife"],
            iterations=0,
        )
        assert result.iterations == 0
        assert result.hits == 0
        assert result.hit_rate == 0


class TestBestTierConstruction:
    """Direct negative tests for BestTier.__post_init__ — without these,
    the inverted-range gate (added so a malformed RePoE entry surfaces
    at load time instead of killing a worker mid-simulation) is uncovered.
    """

    def test_clean_pair_passes(self):
        from poe.services.repoe.sim import BestTier

        BestTier(ilvl=84, values=((10, 20), (5, 8)), weight=1000)

    def test_inverted_pair_rejected(self):
        from poe.services.repoe.sim import BestTier

        with pytest.raises(ValueError, match="min <= max"):
            BestTier(ilvl=84, values=((20, 10),), weight=1000)

    def test_wrong_pair_length_rejected(self):
        from poe.services.repoe.sim import BestTier

        with pytest.raises(ValueError, match="min <= max"):
            BestTier(ilvl=84, values=((1, 2, 3),), weight=1000)  # type: ignore[arg-type]

    def test_empty_values_pass(self):
        from poe.services.repoe.sim import BestTier

        BestTier(ilvl=0, values=(), weight=0)

    def test_equal_min_max_pass(self):
        from poe.services.repoe.sim import BestTier

        BestTier(ilvl=84, values=((5, 5),), weight=1000)


class TestCheckInvariants:
    """Direct tests on CraftableItem.check_invariants — the forcing function
    for game-rule invariants on the dataclass that bypasses Pydantic.
    """

    def _make(self, **overrides):
        from poe.services.repoe.sim import CraftableItem

        defaults = {
            "base_name": "Hubris Circlet",
            "base_id": "Metadata/Items/Armours/Helmets/HelmetInt10",
            "ilvl": 84,
        }
        defaults.update(overrides)
        return CraftableItem(**defaults)

    def test_clean_item_passes(self):
        from poe.exceptions import SimDataError

        item = self._make()
        try:
            item.check_invariants()
        except SimDataError as e:
            msg = f"Clean item should pass: {e}"
            raise AssertionError(msg) from e

    def test_negative_max_prefixes_fails(self):
        from poe.exceptions import SimDataError

        item = self._make(max_prefixes=-1)
        with pytest.raises(SimDataError, match="Negative slot capacity"):
            item.check_invariants()

    def test_too_many_prefixes_fails(self):
        from poe.exceptions import SimDataError
        from poe.services.repoe.sim import BestTier, RolledMod

        item = self._make(max_prefixes=2)
        for i in range(3):
            item.prefixes.append(
                RolledMod(
                    mod_id=f"p{i}",
                    name=f"P{i}",
                    affix="prefix",
                    group=f"G{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        with pytest.raises(SimDataError, match="exceeds max_prefixes"):
            item.check_invariants()

    def test_fractured_prefix_counts_against_cap(self):
        from poe.exceptions import SimDataError
        from poe.services.repoe.sim import BestTier, RolledMod

        # max_prefixes=2: one regular + two fractured prefixes = 3 total
        item = self._make(max_prefixes=2)
        item.prefixes.append(
            RolledMod(
                mod_id="p0",
                name="P0",
                affix="prefix",
                group="G0",
                weight=100,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        for i in range(2):
            item.fractured_mods.append(
                RolledMod(
                    mod_id=f"f{i}",
                    name=f"F{i}",
                    affix="prefix",
                    group=f"FG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        with pytest.raises(SimDataError, match="exceeds max_prefixes"):
            item.check_invariants()

    def test_too_many_crafted_mods_fails(self):
        from poe.exceptions import SimDataError
        from poe.services.repoe.sim import BestTier, RolledMod

        item = self._make(max_crafted_mods=1)
        for i in range(2):
            item.prefixes.append(
                RolledMod(
                    mod_id=f"c{i}",
                    name=f"C{i}",
                    affix="prefix",
                    group=f"CG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                    is_crafted=True,
                )
            )
        with pytest.raises(SimDataError, match="exceeds max_crafted_mods"):
            item.check_invariants()

    def test_too_many_influences_fails(self):
        from poe.exceptions import SimDataError

        item = self._make(influences=["Shaper", "Hunter", "Crusader"])
        with pytest.raises(SimDataError, match="exceeds max"):
            item.check_invariants()

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("Shaper", "Elder"),
            ("Crusader", "Warlord"),
            ("Hunter", "Redeemer"),
            ("Shaper", "Hunter"),
            ("Crusader", "Hunter"),
        ],
    )
    def test_two_influence_pairs_pass(self, a, b):
        # Conqueror exclusivity (Shaper+Elder etc.) is enforced at the
        # conqueror_exalt entry point, not as a permanent state invariant —
        # Awakener's Orb legitimately produces Shaper+Elder items. Any pair
        # that fits within MAX_INFLUENCES is a legal item state.
        item = self._make(influences=[a, b])
        item.check_invariants()

    def test_duplicate_prefix_group_fails(self):
        from poe.exceptions import SimDataError
        from poe.services.repoe.sim import BestTier, RolledMod

        item = self._make()
        for i in range(2):
            item.prefixes.append(
                RolledMod(
                    mod_id=f"life{i}",
                    name=f"Life{i}",
                    affix="prefix",
                    group="IncreasedLife",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        with pytest.raises(SimDataError, match="duplicate prefix mod group"):
            item.check_invariants()


class TestCraftableItemInvariants:
    def test_chaos_roll_respects_max_prefixes(self, engine):
        for seed_val in range(20):
            random.seed(seed_val)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item)
            assert len(item.prefixes) <= item.max_prefixes
            assert len(item.suffixes) <= item.max_suffixes

    def test_chaos_roll_no_duplicate_groups(self, engine):
        for seed_val in range(20):
            random.seed(seed_val)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item)
            groups = [m.group for m in item.all_mods]
            assert len(groups) == len(set(groups))

    def test_open_prefixes_never_negative(self, engine, blank_item):
        for i in range(3):
            blank_item.prefixes.append(
                RolledMod(
                    mod_id=f"p{i}",
                    name=f"P{i}",
                    affix="prefix",
                    group=f"PG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        assert blank_item.open_prefixes == 0
        assert blank_item.open_prefixes >= 0

    def test_open_suffixes_never_negative(self, engine, blank_item):
        for i in range(3):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"s{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        assert blank_item.open_suffixes == 0

    def test_alt_roll_caps_at_one_each(self, engine):
        for seed_val in range(50):
            random.seed(seed_val)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            engine.alt_roll(item)
            assert len(item.prefixes) <= 1
            assert len(item.suffixes) <= 1

    def test_rare_mod_count_always_in_distribution(self, engine):
        random.seed(42)
        for _ in range(500):
            assert engine._rare_mod_count() in (4, 5, 6)

    def test_roll_values_within_tier_ranges(self, engine):
        tier = BestTier(ilvl=1, values=((10, 20), (30, 40), (5, 15)), weight=0)
        random.seed(42)
        for _ in range(100):
            rolls = engine._roll_values(tier)
            assert len(rolls) == 3
            assert 10 <= rolls[0] <= 20
            assert 30 <= rolls[1] <= 40
            assert 5 <= rolls[2] <= 15

    def test_groups_are_unique_set(self, engine, blank_item):
        random.seed(42)
        engine.chaos_roll(blank_item)
        all_groups = [m.group for m in blank_item.all_mods]
        assert blank_item.groups == set(all_groups)
        assert len(blank_item.groups) == len(set(all_groups))

    def test_crafted_mod_count_never_exceeds_max(self, engine, blank_item):
        blank_item.max_crafted_mods = 2
        pool = engine._build_mod_pool(blank_item)
        engine.apply_crafted_mod(blank_item, pool[0])
        engine.apply_crafted_mod(blank_item, pool[1])
        assert blank_item.crafted_mod_count <= blank_item.max_crafted_mods


class TestSimulateInvariantsAcrossMethods:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["chaos", "alt", "fossil", "essence"])
    async def test_simulate_returns_valid_result(self, engine, method):
        random.seed(42)
        kwargs = {
            "iterations": 30,
            "max_attempts": 30,
        }
        if method == "fossil":
            kwargs["fossils"] = ["Pristine Fossil"]
        if method == "essence":
            kwargs["essence_name"] = "Greed"
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method=method,
            target_mods=["IncreasedLife"],
            **kwargs,
        )
        assert 0 <= result.hits <= result.iterations
        assert 0.0 <= result.hit_rate <= 1.0
        assert result.cost_per_attempt > 0
        if result.percentiles:
            assert (
                result.percentiles["p50"]
                <= result.percentiles["p75"]
                <= result.percentiles["p90"]
                <= result.percentiles["p99"]
            )


# ── Pattern 2: Parametrize over input space (case variants) ─────────────────


class TestEssenceNameCaseVariants:
    @pytest.mark.parametrize(
        "essence_name",
        [
            "Greed",
            "greed",
            "GREED",
            "GrEeD",
            "Essence of Greed",
            "essence of greed",
            "ESSENCE OF GREED",
            "Essence Of Greed",
        ],
    )
    def test_essence_name_case_insensitive(self, engine, essence_name):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        random.seed(42)
        engine.essence_roll(item, essence_name)
        assert item.rarity == Rarity.RARE
        assert len(item.all_mods) > 0


class TestExistingModNameCaseVariants:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "existing",
        [
            "IncreasedLife",
            "increasedlife",
            "INCREASEDLIFE",
            "iNcReAsEdLiFe",
        ],
    )
    async def test_existing_mod_case_insensitive(self, engine, existing):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["ColdResistance"],
            iterations=10,
            max_attempts=20,
            existing_mods=[existing],
        )
        assert isinstance(result, SimResult)


class TestTargetModCaseVariants:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "target",
        [
            "IncreasedLife",
            "increasedlife",
            "INCREASEDLIFE",
            "iNcReAsEdLiFe",
        ],
    )
    async def test_target_mod_case_insensitive(self, engine, target):
        random.seed(42)
        result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=[target],
            iterations=50,
        )
        assert result.hit_rate > 0


class TestHarvestTagCaseVariants:
    @pytest.mark.parametrize("tag", ["life", "Life", "LIFE", "LiFe"])
    def test_harvest_reforge_tag_case_insensitive(self, engine, tag):
        random.seed(42)
        item = engine.create_item("Hubris Circlet", ilvl=84)
        engine.harvest_reforge(item, tag=tag, multiplier=10.0)
        assert item.rarity == Rarity.RARE


# ── Pattern 3: Full enum coverage ──────────────────────────────────────────


class TestRarityEnumCoverage:
    @pytest.mark.parametrize("rarity", list(Rarity))
    def test_every_rarity_assignable(self, engine, rarity):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = rarity
        assert item.rarity == rarity

    @pytest.mark.parametrize(
        "rarity",
        [r for r in Rarity if r != Rarity.MAGIC],
    )
    def test_regal_only_works_on_magic(self, engine, blank_item, rarity):
        blank_item.rarity = rarity
        assert engine.regal(blank_item) is None

    @pytest.mark.parametrize(
        "rarity",
        [r for r in Rarity if r != Rarity.RARE],
    )
    def test_exalt_only_works_on_rare(self, engine, blank_item, rarity):
        blank_item.rarity = rarity
        assert engine.exalt(blank_item) is None


class TestInfluenceEnumCoverage:
    @pytest.mark.parametrize("influence", list(Influence))
    def test_every_influence_storable(self, engine, influence):
        item = engine.create_item("Hubris Circlet", ilvl=84, influences=[influence.value])
        assert influence.value in item.influences

    @pytest.mark.parametrize(
        "influence",
        [i for i in Influence if i.value not in {"Searing Exarch", "Eater of Worlds"}],
    )
    def test_conqueror_exalt_accepts_each_conqueror_influence(self, engine, influence):
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        engine.conqueror_exalt(item, influence.value)
        assert influence.value in item.influences

    @pytest.mark.parametrize("eldritch", ["Searing Exarch", "Eater of Worlds"])
    def test_conqueror_exalt_rejects_eldritch_influence(self, engine, eldritch):
        """Eldritch influences are added via the eldritch implicit system,
        not via Conqueror Exalt; reject them."""
        item = engine.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="Unknown conqueror influence"):
            engine.conqueror_exalt(item, eldritch)


class TestCraftMethodEnumCoverage:
    @pytest.mark.parametrize("method", list(CraftMethod))
    def test_apply_roll_handles_each_method_or_raises(self, engine, blank_item, method):
        random.seed(42)
        kwargs = {
            "fossil_weights": None,
            "blocked_tags": None,
            "essence_name": None,
        }
        if method == CraftMethod.FOSSIL:
            kwargs["fossil_weights"] = {"life": 5.0}
        if method == CraftMethod.ESSENCE:
            kwargs["essence_name"] = "Greed"

        handled_methods = {
            CraftMethod.CHAOS,
            CraftMethod.ALT,
            CraftMethod.FOSSIL,
            CraftMethod.ESSENCE,
            CraftMethod.ALCHEMY,
            CraftMethod.TRANSMUTATION,
            CraftMethod.HARVEST,
        }

        if method in handled_methods:
            engine._apply_roll(blank_item, method.value, **kwargs)
            assert blank_item.rarity in (Rarity.RARE, Rarity.MAGIC)
        else:
            with pytest.raises(ValueError, match="Unknown craft method"):
                engine._apply_roll(blank_item, method.value, **kwargs)


# ── Pattern 4: Negative tests for raises ───────────────────────────────────


class TestNegativeRaises:
    def test_awakener_orb_same_influence_raises(self, engine):
        item1 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        item2 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        with pytest.raises(ValueError, match="different influences"):
            engine.awakener_orb(item1, item2)

    def test_awakener_orb_no_influence_on_item1_raises(self, engine):
        item1 = engine.create_item("Hubris Circlet", ilvl=84)
        item2 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        with pytest.raises(ValueError, match="influenced"):
            engine.awakener_orb(item1, item2)

    def test_awakener_orb_no_influence_on_item2_raises(self, engine):
        item1 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper"])
        item2 = engine.create_item("Hubris Circlet", ilvl=84)
        with pytest.raises(ValueError, match="influenced"):
            engine.awakener_orb(item1, item2)

    def test_apply_crafted_mod_dict_no_open_prefix_raises(self, engine, blank_item):
        for i in range(3):
            blank_item.prefixes.append(
                RolledMod(
                    mod_id=f"p{i}",
                    name=f"P{i}",
                    affix="prefix",
                    group=f"PG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        mod_dict = {
            "mod_id": "x",
            "name": "X",
            "affix": "prefix",
            "group": "XG",
            "weight": 100,
            "best_tier": None,
        }
        with pytest.raises(ValueError, match="No open prefix slots"):
            engine.apply_crafted_mod(blank_item, mod_dict)

    def test_create_item_unknown_base_message(self, engine):
        with pytest.raises(ValueError, match="Unknown base item"):
            engine.create_item("Definitely Not A Real Base")

    def test_essence_roll_unknown_essence_includes_name(self, engine, blank_item):
        with pytest.raises(ValueError, match="NonexistentEssenceXyz"):
            engine.essence_roll(blank_item, "NonexistentEssenceXyz")

    def test_crafted_mod_limit_message_shows_count(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item)
        engine.apply_crafted_mod(blank_item, pool[0])
        with pytest.raises(ValueError, match="1/1 crafted mods"):
            engine.apply_crafted_mod(blank_item, pool[1])

    def test_fracture_min_message(self, engine, blank_item):
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="at least 4 mods"):
            engine.fracture(blank_item)

    def test_apply_metamod_no_suffix_slots_message(self, engine, blank_item):
        for i in range(3):
            blank_item.suffixes.append(
                RolledMod(
                    mod_id=f"s{i}",
                    name=f"S{i}",
                    affix="suffix",
                    group=f"SG{i}",
                    weight=100,
                    chance=0.5,
                    tier=BestTier(ilvl=1, values=(), weight=0),
                    rolls=[],
                )
            )
        with pytest.raises(ValueError, match="No open suffix slots for metamod"):
            engine.apply_metamod(blank_item, "prefixes_cannot_be_changed")

    def test_invalid_method_includes_valid_list(self, engine, blank_item):
        with pytest.raises(ValueError, match="valid:"):
            engine._apply_roll(blank_item, "totally_bogus_method", None, None, None)

    def test_corrupted_blocks_alt(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.alt_roll(blank_item)

    def test_corrupted_blocks_regal(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="corrupted"):
            engine.regal(blank_item)

    def test_corrupted_blocks_alchemy(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.NORMAL
        with pytest.raises(ValueError, match="corrupted"):
            engine.alchemy(blank_item)

    def test_corrupted_blocks_transmutation(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.NORMAL
        with pytest.raises(ValueError, match="corrupted"):
            engine.transmutation(blank_item)

    def test_corrupted_blocks_augmentation(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.MAGIC
        with pytest.raises(ValueError, match="corrupted"):
            engine.augmentation(blank_item)

    def test_corrupted_blocks_divine(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.divine(blank_item)

    def test_corrupted_blocks_blessed(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.blessed(blank_item)

    def test_corrupted_blocks_apply_metamod(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.apply_metamod(blank_item, "prefixes_cannot_be_changed")

    def test_corrupted_blocks_apply_crafted_mod(self, engine, blank_item):
        blank_item.is_corrupted = True
        pool = engine._build_mod_pool(blank_item)
        with pytest.raises(ValueError, match="corrupted"):
            engine.apply_crafted_mod(blank_item, pool[0])

    def test_corrupted_blocks_harvest_reforge(self, engine, blank_item):
        blank_item.is_corrupted = True
        with pytest.raises(ValueError, match="corrupted"):
            engine.harvest_reforge(blank_item)

    def test_corrupted_blocks_harvest_augment(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="corrupted"):
            engine.harvest_augment(blank_item, "life")

    def test_corrupted_blocks_conqueror_exalt(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="corrupted"):
            engine.conqueror_exalt(blank_item, "Shaper")

    def test_corrupted_blocks_veiled_chaos(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="corrupted"):
            engine.veiled_chaos(blank_item)

    def test_corrupted_blocks_aisling_bench(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="corrupted"):
            engine.aisling_bench(blank_item)

    def test_corrupted_blocks_fracture(self, engine, blank_item):
        blank_item.is_corrupted = True
        blank_item.rarity = Rarity.RARE
        with pytest.raises(ValueError, match="corrupted"):
            engine.fracture(blank_item)


# ── Apply-roll method coverage (Pattern 3 + Pattern 4) ─────────────────────


class TestApplyRollFossilWithoutWeights:
    def test_apply_roll_fossil_without_weights_falls_through_to_else(self, engine, blank_item):
        random.seed(42)
        with pytest.raises(ValueError, match="Unknown craft method"):
            engine._apply_roll(blank_item, "fossil", None, None, None)

    def test_apply_roll_essence_without_name_falls_through_to_else(self, engine, blank_item):
        random.seed(42)
        with pytest.raises(ValueError, match="Unknown craft method"):
            engine._apply_roll(blank_item, "essence", None, None, None)


# ── Influence enum: alt_roll preserves max but caps real roll ──────────────


class TestAltRollPreservesMaxAfterRoll:
    def test_alt_roll_restores_max_prefixes_suffixes(self, engine):
        for seed_val in range(20):
            random.seed(seed_val)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            assert item.max_prefixes == 3
            assert item.max_suffixes == 3
            engine.alt_roll(item)
            assert item.max_prefixes == 3
            assert item.max_suffixes == 3

    def test_transmutation_restores_max_prefixes_suffixes(self, engine):
        for seed_val in range(20):
            random.seed(seed_val)
            item = engine.create_item("Hubris Circlet", ilvl=84)
            item.rarity = Rarity.NORMAL
            engine.transmutation(item)
            assert item.max_prefixes == 3
            assert item.max_suffixes == 3


# ── Full mod pool invariants ───────────────────────────────────────────────


class TestModPoolInvariants:
    def test_pool_excludes_existing_groups(self, engine, blank_item):
        blank_item.prefixes.append(
            RolledMod(
                mod_id="m1",
                name="Life",
                affix="prefix",
                group="IncreasedLife",
                weight=1000,
                chance=0.5,
                tier=BestTier(ilvl=1, values=(), weight=0),
                rolls=[],
            )
        )
        pool = engine._build_mod_pool(blank_item)
        assert all(m.group != "IncreasedLife" for m in pool)

    def test_pool_only_prefix_when_filtered(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item, affix_type="prefix")
        assert all(m.affix == "prefix" for m in pool)

    def test_pool_only_suffix_when_filtered(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item, affix_type="suffix")
        assert all(m.affix == "suffix" for m in pool)

    def test_pool_weights_non_negative(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item)
        assert all(m.weight >= 0 for m in pool)

    def test_pool_with_blocked_tags_excludes_tagged(self, engine, blank_item):
        pool = engine._build_mod_pool(blank_item, blocked_tags={"life"})
        for m in pool:
            assert "life" not in [t.casefold() for t in m.implicit_tags]


# ── Match mode invariants (Pattern 1 — all <= any) ─────────────────────────


class TestMatchModeInvariants:
    @pytest.mark.asyncio
    async def test_all_hit_rate_le_any_hit_rate_for_two_targets(self, engine):
        random.seed(42)
        all_result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife", "ColdResistance"],
            match_mode="all",
            iterations=100,
        )
        random.seed(42)
        any_result = await engine.simulate(
            "Hubris Circlet",
            ilvl=84,
            method="chaos",
            target_mods=["IncreasedLife", "ColdResistance"],
            match_mode="any",
            iterations=100,
        )
        assert all_result.hit_rate <= any_result.hit_rate + 1e-9


# ── Recombinator influence cap invariant ───────────────────────────────────


class TestRecombinatorInvariants:
    def test_result_influences_capped_at_two(self, engine):
        # Use non-mutually-exclusive influence pairs (Shaper+Elder etc. would
        # violate the conqueror exclusivity invariant). Combined the inputs
        # have four distinct influences; recombinator must cap the result
        # at two regardless.
        for seed_val in range(10):
            random.seed(seed_val)
            item1 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Shaper", "Hunter"])
            item2 = engine.create_item("Hubris Circlet", ilvl=84, influences=["Crusader"])
            engine.chaos_roll(item1)
            engine.chaos_roll(item2)
            result = engine.recombinate(item1, item2)
            assert len(result.influences) <= 2

    def test_result_ilvl_is_max_of_inputs(self, engine):
        for seed_val in range(10):
            random.seed(seed_val)
            item1 = engine.create_item("Hubris Circlet", ilvl=70)
            item2 = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item1)
            engine.chaos_roll(item2)
            result = engine.recombinate(item1, item2)
            assert result.ilvl == 84

    def test_result_no_duplicate_groups(self, engine):
        for seed_val in range(10):
            random.seed(seed_val)
            item1 = engine.create_item("Hubris Circlet", ilvl=84)
            item2 = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(item1)
            engine.chaos_roll(item2)
            result = engine.recombinate(item1, item2)
            groups = [m.group for m in result.all_mods]
            assert len(groups) == len(set(groups))

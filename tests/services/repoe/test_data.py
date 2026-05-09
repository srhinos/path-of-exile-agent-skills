from __future__ import annotations

import copy

import pytest

from poe.exceptions import SimDataError
from poe.services.repoe.constants import (
    ESSENCE_TIER_PREFIXES,
    INFLUENCE_TAG_MAP,
)
from poe.services.repoe.data import RepoEData
from poe.types import Influence
from tests.conftest import REPOE_DATA, make_repoe_data


def _multi_influence_fixture() -> dict:
    data = copy.deepcopy(REPOE_DATA)
    base_id = data["base_items"]["Hubris Circlet"]["id"]
    influence_mod_pairs = [
        ("Shaper", "shaper"),
        ("Elder", "elder"),
        ("Crusader", "crusader"),
        ("Warlord", "adjudicator"),
        ("Hunter", "basilisk"),
        ("Redeemer", "eyrie"),
    ]
    for display, codename in influence_mod_pairs:
        mod_id = f"{display}TestLife1"
        data["mods"][mod_id] = {
            "name": f"{display} Life",
            "group": f"{display}Life",
            "affix": "prefix",
            "required_level": 68,
            "implicit_tags": ["resource", "life"],
            "stats": [{"id": "base_maximum_life", "min": 5, "max": 10}],
            "spawn_weights": [
                {"tag": f"helmet_{codename}", "weight": 300},
                {"tag": "default", "weight": 0},
            ],
            "influence": display,
            "is_essence_only": False,
        }
        data["mod_pool"][base_id].append(mod_id)
    return data


class TestBaseItemQueries:
    def test_get_base_item_exact(self, repoe_data):
        item = repoe_data.get_base_item("Hubris Circlet")
        assert item is not None
        assert item["item_class"] == "Helmet"

    def test_get_base_item_case_insensitive(self, repoe_data):
        item = repoe_data.get_base_item("hubris circlet")
        assert item is not None

    def test_get_base_item_not_found(self, repoe_data):
        assert repoe_data.get_base_item("Nonexistent Item") is None

    def test_search_base_items(self, repoe_data):
        results = repoe_data.search_base_items("Circlet")
        assert len(results) == 1
        assert results[0]["name"] == "Hubris Circlet"

    def test_search_base_items_no_match(self, repoe_data):
        results = repoe_data.search_base_items("zzzzz")
        assert results == []


class TestModPool:
    def test_returns_mods(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        assert len(mods) > 0

    def test_ilvl_filter(self, repoe_data):
        mods_low = repoe_data.get_mod_pool("Hubris Circlet", ilvl=1)
        mods_high = repoe_data.get_mod_pool("Hubris Circlet", ilvl=100)
        assert len(mods_low) > 0
        assert len(mods_high) > 0

    def test_prefix_filter(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet", affix_type="prefix")
        for m in mods:
            assert m.affix == "prefix"

    def test_suffix_filter(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet", affix_type="suffix")
        for m in mods:
            assert m.affix == "suffix"

    def test_influence_mods(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet", influences=["Shaper"])
        mod_names = [m.name for m in mods]
        assert "Shaper Life" in mod_names

    def test_influence_case_insensitive(self, repoe_data):
        mods_upper = repoe_data.get_mod_pool("Hubris Circlet", influences=["Shaper"])
        mods_lower = repoe_data.get_mod_pool("Hubris Circlet", influences=["shaper"])
        shaper_ids_upper = {m.mod_id for m in mods_upper if m.influence}
        shaper_ids_lower = {m.mod_id for m in mods_lower if m.influence}
        assert shaper_ids_upper == shaper_ids_lower
        assert len(shaper_ids_lower) > 0

    def test_no_influence_excludes_influence_mods(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        mod_names = [m.name for m in mods]
        assert "Shaper Life" not in mod_names

    def test_mod_structure(self, repoe_data):
        from poe.services.repoe.sim import BestTier, ModPoolEntry

        mods = repoe_data.get_mod_pool("Hubris Circlet")
        for m in mods:
            assert isinstance(m, ModPoolEntry)
            assert isinstance(m.mod_id, str)
            assert isinstance(m.name, str)
            assert m.affix in ("prefix", "suffix")
            assert isinstance(m.group, str)
            assert isinstance(m.weight, int)
            assert isinstance(m.best_tier, BestTier)

    def test_implicit_tags_parsed_as_tuple(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        life_mods = [m for m in mods if m.group == "IncreasedLife"]
        assert len(life_mods) > 0
        assert isinstance(life_mods[0].implicit_tags, tuple)
        assert "life" in life_mods[0].implicit_tags

    def test_unknown_base_returns_empty(self, repoe_data):
        mods = repoe_data.get_mod_pool("Nonexistent Base")
        assert mods == []


class TestModTiers:
    def test_basic_tiers(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Hubris Circlet")
        assert len(tiers) == 4

    def test_tiers_sorted_by_ilvl_desc(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Hubris Circlet")
        ilvls = [t["ilvl"] for t in tiers]
        assert ilvls == sorted(ilvls, reverse=True)

    def test_tiers_not_found(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("nonexistent_mod", "Hubris Circlet")
        assert tiers == []

    def test_tiers_base_not_found(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Nonexistent Base")
        assert tiers == []

    def test_tier_structure(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Hubris Circlet")
        for t in tiers:
            assert "tier" in t
            assert "ilvl" in t
            assert "weight" in t
            assert "values" in t
            assert "available" in t


class TestFossils:
    def test_list_fossils(self, repoe_data):
        fossils = repoe_data.get_fossils()
        assert len(fossils) == 3
        names = [f["name"] for f in fossils]
        assert "Pristine Fossil" in names
        assert "Frigid Fossil" in names
        assert "Metallic Fossil" in names

    def test_filter_fossils(self, repoe_data):
        fossils = repoe_data.get_fossils(filter_tag="life")
        names = [f["name"] for f in fossils]
        assert "Pristine Fossil" in names

    def test_fossil_structure(self, repoe_data):
        fossils = repoe_data.get_fossils()
        for f in fossils:
            assert "name" in f
            assert "positive_weights" in f
            assert "negative_weights" in f
            assert "blocked" in f


class TestEssences:
    def test_list_essences(self, repoe_data):
        essences = repoe_data.get_essences()
        assert len(essences) >= 1

    def test_filtered_essences(self, repoe_data):
        essences = repoe_data.get_essences(base_name="Hubris Circlet")
        assert len(essences) >= 1

    def test_invalid_base_name_raises(self, repoe_data):
        with pytest.raises(SimDataError, match="not found"):
            repoe_data.get_essences("NonexistentBase999")


class TestBenchCrafts:
    def test_bench_crafts_for_base(self, repoe_data):
        crafts = repoe_data.get_bench_crafts("Hubris Circlet")
        assert len(crafts) > 0

    def test_bench_craft_structure(self, repoe_data):
        crafts = repoe_data.get_bench_crafts("Hubris Circlet")
        for c in crafts:
            assert "mod_id" in c
            assert "name" in c
            assert "cost" in c
            assert "cost_raw" in c

    def test_cost_display_has_no_metadata_paths(self, repoe_data):
        crafts = repoe_data.get_bench_crafts("Hubris Circlet")
        for craft in crafts:
            assert "Metadata/" not in craft["cost"], f"Raw path in cost: {craft['cost']}"

    def test_bench_crafts_unknown_base(self, repoe_data):
        crafts = repoe_data.get_bench_crafts("Nonexistent Base")
        assert crafts == []


class TestPrices:
    def test_get_prices_structure(self, repoe_data):
        prices = repoe_data.get_prices()
        assert "league" in prices
        assert "currency" in prices
        assert "fossils" in prices
        assert "essences" in prices

    def test_chaos_cost(self, repoe_data):
        cost = repoe_data.get_craft_cost("chaos")
        assert cost == 1.0

    def test_fallback_cost(self, repoe_data):
        cost = repoe_data.get_craft_cost("unknown_method")
        assert cost == 1.0

    def test_fossil_cost(self, repoe_data):
        prices = repoe_data.get_prices()
        cost = repoe_data.get_craft_cost("fossil", prices=prices, fossils=["Pristine Fossil"])
        assert cost > 0

    def test_essence_cost(self, repoe_data):
        prices = repoe_data.get_prices()
        cost = repoe_data.get_craft_cost("essence", prices=prices, essence="Some Essence")
        assert cost == 5.0


class TestEssenceTiers:
    def test_essence_tier_populated(self, repoe_data):
        essences = repoe_data.get_essences()
        for ess in essences:
            assert "tier" in ess
            assert "tier_num" in ess

    def test_essence_tier_name_mapping(self):
        assert RepoEData._extract_essence_tier("Screaming") == ("Screaming", 5)
        assert RepoEData._extract_essence_tier("Deafening") == ("Deafening", 7)
        assert RepoEData._extract_essence_tier("Whispering") == ("Whispering", 1)
        assert RepoEData._extract_essence_tier("Unknown") == ("", 0)


class TestDataCaching:
    def test_load_caches_results(self, repoe_data):
        result1 = repoe_data._load("mods")
        result2 = repoe_data._load("mods")
        assert result1 is result2


class TestInfluenceLookupCoverage:
    @pytest.mark.parametrize(
        "input_value",
        [
            "Shaper",
            "shaper",
            "SHAPER",
            "ShApEr",
        ],
    )
    def test_shaper_case_variants_resolve_same(self, input_value):
        data = make_repoe_data(data=_multi_influence_fixture())
        canonical = data.get_mod_pool("Hubris Circlet", influences=["Shaper"])
        canonical_ids = {m.mod_id for m in canonical if m.influence}
        result = data.get_mod_pool("Hubris Circlet", influences=[input_value])
        result_ids = {m.mod_id for m in result if m.influence}
        assert result_ids == canonical_ids
        assert len(result_ids) > 0

    @pytest.mark.parametrize(
        ("input_value", "expected_display"),
        [
            ("shaper", "Shaper"),
            ("SHAPER", "Shaper"),
            ("elder", "Elder"),
            ("Elder", "Elder"),
            ("crusader", "Crusader"),
            ("CRUSADER", "Crusader"),
            ("adjudicator", "Warlord"),
            ("Warlord", "Warlord"),
            ("WARLORD", "Warlord"),
            ("basilisk", "Hunter"),
            ("Hunter", "Hunter"),
            ("HUNTER", "Hunter"),
            ("eyrie", "Redeemer"),
            ("Redeemer", "Redeemer"),
            ("REDEEMER", "Redeemer"),
        ],
    )
    def test_codename_and_display_variants_resolve_to_correct_mod(
        self, input_value, expected_display
    ):
        data = make_repoe_data(data=_multi_influence_fixture())
        result = data.get_mod_pool("Hubris Circlet", influences=[input_value])
        influence_mods = [m for m in result if m.influence == expected_display]
        assert len(influence_mods) > 0, (
            f"Expected at least one {expected_display}-influenced mod for input "
            f"{input_value!r}, got influences: {[m.influence for m in result]}"
        )

    @pytest.mark.parametrize(
        ("codename", "display"),
        sorted(INFLUENCE_TAG_MAP.items()),
    )
    def test_every_influence_in_tag_map_resolves(self, codename, display):
        data = make_repoe_data(data=_multi_influence_fixture())
        result = data.get_mod_pool("Hubris Circlet", influences=[codename])
        matching = [m for m in result if m.influence == display]
        assert len(matching) > 0, f"codename {codename!r} did not surface {display} mods"


class TestModPoolNoInfluenceExcludesAll:
    @pytest.mark.parametrize("influence", [i.value for i in Influence])
    def test_unselected_influence_mods_excluded(self, influence):
        data = make_repoe_data(data=_multi_influence_fixture())
        no_inf = data.get_mod_pool("Hubris Circlet")
        for mod in no_inf:
            assert mod.influence is None


class TestEssencesNonexistentBaseRaises:
    def test_raises_with_descriptive_message(self, repoe_data):
        with pytest.raises(SimDataError, match=r"Nonexistent.*not found"):
            repoe_data.get_essences("Nonexistent Base")


class TestEssenceTierFullCoverage:
    @pytest.mark.parametrize(
        ("prefix", "expected_num"),
        sorted(ESSENCE_TIER_PREFIXES.items()),
    )
    def test_every_tier_prefix_resolves(self, prefix, expected_num):
        name = prefix.title() + " Essence of Greed"
        tier_name, tier_num = RepoEData._extract_essence_tier(name)
        assert tier_num == expected_num
        assert tier_name == prefix.title()

    @pytest.mark.parametrize(
        "case_variant",
        ["DEAFENING", "deafening", "DeAfEnInG"],
    )
    def test_case_insensitive_tier_extraction(self, case_variant):
        _, tier_num = RepoEData._extract_essence_tier(case_variant)
        assert tier_num == ESSENCE_TIER_PREFIXES["deafening"]


class TestModPoolEntryInvariants:
    def test_weights_are_positive(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        assert len(mods) > 0
        for m in mods:
            assert m.weight > 0

    def test_results_sorted_by_weight_desc(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        weights = [m.weight for m in mods]
        assert weights == sorted(weights, reverse=True)

    def test_best_tier_values_are_pairs(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        for m in mods:
            for pair in m.best_tier.values:
                assert len(pair) == 2
                lo, hi = pair
                assert lo <= hi

    def test_tier_count_matches_pool(self, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet")
        life_mods = [m for m in mods if m.group == "IncreasedLife"]
        assert len(life_mods) > 0
        for m in life_mods:
            assert m.tier_count == 4


class TestModTiersInvariants:
    def test_tier_numbers_are_contiguous(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Hubris Circlet")
        tier_nums = [t["tier"] for t in tiers]
        assert tier_nums == list(range(1, len(tiers) + 1))

    def test_value_ranges_are_pairs(self, repoe_data):
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Hubris Circlet")
        for t in tiers:
            for pair in t["values"]:
                assert len(pair) == 2

    def test_ilvl_filter_matches_available(self, repoe_data):
        ilvl = 50
        tiers = repoe_data.get_mod_tiers("IncreasedLife4", "Hubris Circlet", ilvl=ilvl)
        for t in tiers:
            assert t["available"] == (t["ilvl"] <= ilvl)


class TestSearchBasesInvariants:
    @pytest.mark.parametrize(
        "query",
        ["circlet", "CIRCLET", "Circlet", "CiRcLeT"],
    )
    def test_search_case_insensitive(self, repoe_data, query):
        results = repoe_data.search_base_items(query)
        names = {r["name"] for r in results}
        assert "Hubris Circlet" in names

    def test_search_returns_each_match_once(self, repoe_data):
        results = repoe_data.search_base_items("")
        names = [r["name"] for r in results]
        assert len(names) == len(set(names))


class TestGetCraftCostFullKeyCoverage:
    @pytest.mark.parametrize(
        "method",
        ["chaos", "alt", "regal", "exalt", "annul", "divine", "scour"],
    )
    def test_every_simple_method_returns_finite_cost(self, repoe_data, method):
        cost = repoe_data.get_craft_cost(method)
        assert isinstance(cost, float)
        assert cost > 0

    def test_fossil_cost_includes_resonator(self, repoe_data):
        prices = {
            "currency": {},
            "fossils": {"Pristine Fossil": 3.0},
            "resonators": {"Primitive Alchemical Resonator": 2.0},
            "essences": {},
        }
        cost = repoe_data.get_craft_cost(
            "fossil",
            prices=prices,
            fossils=["Pristine Fossil"],
        )
        assert cost == 5.0

    def test_unknown_method_returns_default(self, repoe_data):
        cost = repoe_data.get_craft_cost("zzz_not_a_method")
        assert cost == 1.0

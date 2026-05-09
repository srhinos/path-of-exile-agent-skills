from __future__ import annotations

import json

import pytest

from poe.services.repoe.constants import (
    BASE_ITEM_DOMAINS,
    CURRENCY_PATH_NAMES,
    DEFAULT_MAX_PREFIXES,
    DEFAULT_MAX_SUFFIXES,
    FOSSIL_WEIGHT_DIVISOR,
    INFLUENCE_TAG_MAP,
    MAX_PREFIXES_BY_CLASS,
    MAX_SUFFIXES_BY_CLASS,
    MOD_DOMAIN_FOR_BASE_DOMAIN,
    PLAYER_ITEM_DOMAINS,
)
from poe.services.repoe.pipeline.pipeline import (
    RepoEPipeline,
    _build_mod_pool,
    _detect_influence,
    _process_base_items,
    _process_bench_crafts,
    _process_essences,
    _process_fossils,
    _process_mods,
    _process_stat_translations,
)


class TestProcessBaseItems:
    def test_filters_by_domain(self):
        raw = {
            "Meta/A": {
                "domain": "item",
                "release_state": "released",
                "name": "Test Item",
                "item_class": "Helmet",
                "drop_level": 10,
                "tags": ["helmet", "default"],
                "properties": {},
            },
            "Meta/B": {
                "domain": "monster",
                "release_state": "released",
                "name": "Monster Thing",
                "item_class": "MonsterItem",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert "Test Item" in result
        assert "Monster Thing" not in result

    def test_filters_unreleased(self):
        raw = {
            "Meta/A": {
                "domain": "item",
                "release_state": "unique_only",
                "name": "Unique Base",
                "item_class": "Helmet",
                "drop_level": 10,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert len(result) == 0

    def test_max_affixes_for_jewel(self):
        raw = {
            "Meta/J": {
                "domain": "item",
                "release_state": "released",
                "name": "Cobalt Jewel",
                "item_class": "Jewel",
                "drop_level": 1,
                "tags": ["jewel", "default"],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result["Cobalt Jewel"]["max_prefixes"] == 2
        assert result["Cobalt Jewel"]["max_suffixes"] == 2


class TestProcessMods:
    def test_filters_domain_and_gen_type(self):
        raw = {
            "TestPrefix1": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["TestGroup"],
                "spawn_weights": [{"tag": "default", "weight": 1000}],
                "implicit_tags": ["life"],
                "stats": [{"id": "life", "min": 10, "max": 20}],
                "required_level": 1,
                "name": "Test",
                "is_essence_only": False,
            },
            "UniqueOnly1": {
                "domain": "item",
                "generation_type": "unique",
                "groups": ["UniqueGroup"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "Unique",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert "TestPrefix1" in result
        assert "UniqueOnly1" not in result

    def test_includes_crafted_domain(self):
        raw = {
            "HelenaMasterLife1": {
                "domain": "crafted",
                "generation_type": "prefix",
                "groups": ["IncreasedLife"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [{"id": "base_maximum_life", "min": 50, "max": 60}],
                "required_level": 30,
                "name": "Crafted Life",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert "HelenaMasterLife1" in result
        assert result["HelenaMasterLife1"]["name"] == "Crafted Life"

    def test_extracts_group(self):
        raw = {
            "Mod1": {
                "domain": "item",
                "generation_type": "suffix",
                "groups": ["ColdResistance"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "Cold Res",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert result["Mod1"]["group"] == "ColdResistance"


class TestDetectInfluence:
    def test_detects_shaper(self):
        weights = [{"tag": "helmet_shaper", "weight": 300}, {"tag": "default", "weight": 0}]
        assert _detect_influence(weights) == "Shaper"

    def test_detects_hunter(self):
        weights = [{"tag": "ring_basilisk", "weight": 500}, {"tag": "default", "weight": 0}]
        assert _detect_influence(weights) == "Hunter"

    def test_no_influence(self):
        weights = [{"tag": "helmet", "weight": 1000}, {"tag": "default", "weight": 0}]
        assert _detect_influence(weights) is None


class TestBuildModPool:
    def test_basic_pool(self):
        base_items = {
            "Test Helm": {
                "id": "Meta/Helm",
                "tags": ["helmet", "default"],
            },
        }
        mods = {
            "Mod1": {
                "spawn_weights": [{"tag": "helmet", "weight": 1000}],
                "is_essence_only": False,
            },
            "Mod2": {
                "spawn_weights": [{"tag": "weapon", "weight": 1000}],
                "is_essence_only": False,
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "Mod1" in pool["Meta/Helm"]
        assert "Mod2" not in pool["Meta/Helm"]

    def test_excludes_essence_only(self):
        base_items = {"Helm": {"id": "Meta/H", "tags": ["helmet", "default"]}}
        mods = {
            "EssOnly": {
                "spawn_weights": [{"tag": "helmet", "weight": 1000}],
                "is_essence_only": True,
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert pool["Meta/H"] == []

    def test_includes_influence_mods(self):
        base_items = {
            "BodyArmour1": {
                "id": "BodyArmour1",
                "tags": ["body_armour", "armour", "default"],
            },
        }
        mods = {
            "ShaperMod1": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "body_armour_shaper", "weight": 500}],
            },
            "ElderMod1": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "body_armour_elder", "weight": 500}],
            },
            "HunterMod1": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "body_armour_basilisk", "weight": 500}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "ShaperMod1" in pool["BodyArmour1"]
        assert "ElderMod1" in pool["BodyArmour1"]
        assert "HunterMod1" in pool["BodyArmour1"]

    def test_excludes_zero_weight_influence(self):
        base_items = {
            "BodyArmour1": {
                "id": "BodyArmour1",
                "tags": ["body_armour", "armour", "default"],
            },
        }
        mods = {
            "ZeroWeightMod": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "body_armour_shaper", "weight": 0}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "ZeroWeightMod" not in pool["BodyArmour1"]

    def test_domain_scoping_flask(self):
        base_items = {
            "FlaskBase": {
                "id": "Meta/Flask",
                "domain": "flask",
                "tags": ["flask", "default"],
            },
        }
        mods = {
            "FlaskMod": {
                "is_essence_only": False,
                "domain": "flask",
                "spawn_weights": [{"tag": "flask", "weight": 500}],
            },
            "ItemMod": {
                "is_essence_only": False,
                "domain": "item",
                "spawn_weights": [{"tag": "flask", "weight": 500}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "FlaskMod" in pool["Meta/Flask"]
        assert "ItemMod" not in pool["Meta/Flask"]

    def test_domain_scoping_default_domains(self):
        base_items = {
            "Helm": {
                "id": "Meta/Helm",
                "domain": "item",
                "tags": ["helmet", "default"],
            },
        }
        mods = {
            "ItemMod": {
                "is_essence_only": False,
                "domain": "item",
                "spawn_weights": [{"tag": "helmet", "weight": 500}],
            },
            "CraftedMod": {
                "is_essence_only": False,
                "domain": "crafted",
                "spawn_weights": [{"tag": "helmet", "weight": 500}],
            },
            "FlaskMod": {
                "is_essence_only": False,
                "domain": "flask",
                "spawn_weights": [{"tag": "helmet", "weight": 500}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "ItemMod" in pool["Meta/Helm"]
        assert "CraftedMod" in pool["Meta/Helm"]
        assert "FlaskMod" not in pool["Meta/Helm"]

    def test_zero_weight_base_tag_excluded(self):
        base_items = {
            "Helm": {
                "id": "Meta/Helm",
                "tags": ["helmet", "default"],
            },
        }
        mods = {
            "ZeroMod": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "helmet", "weight": 0}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "ZeroMod" not in pool["Meta/Helm"]


class TestProcessFossils:
    def test_basic_fossil(self):
        raw = {
            "Meta/Pristine": {
                "name": "Pristine Fossil",
                "positive_mod_weights": [{"tag": "life", "weight": 1000}],
                "negative_mod_weights": [{"tag": "defences", "weight": 0}],
                "forced_mods": [],
                "added_mods": [],
            },
        }
        result = _process_fossils(raw)
        assert "Pristine Fossil" in result
        assert result["Pristine Fossil"]["positive_weights"]["life"] == 10.0
        assert result["Pristine Fossil"]["blocked_tags"] == ["defences"]

    def test_skips_unnamed(self):
        raw = {"Meta/X": {"name": "", "positive_mod_weights": [], "negative_mod_weights": []}}
        result = _process_fossils(raw)
        assert len(result) == 0


class TestProcessEssences:
    def test_basic_essence(self):
        raw = {
            "Meta/Anger1": {
                "name": "Muttering Essence of Anger",
                "type": {"tier": 2, "is_corruption_only": False},
                "item_level_restriction": 45,
                "mods": {"Helmet": "FireDamage2"},
            },
        }
        result = _process_essences(raw)
        assert "Muttering Essence of Anger" in result
        assert result["Muttering Essence of Anger"]["tier"] == 2
        assert result["Muttering Essence of Anger"]["mods"]["Helmet"] == "FireDamage2"

    def test_skips_unnamed(self):
        raw = {
            "Meta/NoName": {
                "name": "",
                "type": {"tier": 1, "is_corruption_only": False},
                "mods": {},
            },
        }
        result = _process_essences(raw)
        assert len(result) == 0


class TestProcessBaseItemsMiscDomain:
    def test_misc_domain_jewel_included(self):
        raw = {
            "Meta/Jewel": {
                "domain": "misc",
                "release_state": "released",
                "name": "Cobalt Jewel",
                "item_class": "Jewel",
                "drop_level": 1,
                "tags": ["jewel", "default"],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert "Cobalt Jewel" in result

    def test_misc_domain_non_jewel_excluded(self):
        raw = {
            "Meta/Misc": {
                "domain": "misc",
                "release_state": "released",
                "name": "Some Misc Item",
                "item_class": "Currency",
                "drop_level": 1,
                "tags": ["currency"],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert "Some Misc Item" not in result

    def test_skips_empty_name(self):
        raw = {
            "Meta/NoName": {
                "domain": "item",
                "release_state": "released",
                "name": "",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert len(result) == 0


class TestProcessModsDomainFiltering:
    def test_excludes_non_player_domain(self):
        raw = {
            "MonsterMod": {
                "domain": "monster",
                "generation_type": "prefix",
                "groups": ["MG"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "Monster",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert "MonsterMod" not in result

    def test_excludes_non_prefix_suffix(self):
        raw = {
            "ImplicitMod": {
                "domain": "item",
                "generation_type": "implicit",
                "groups": ["IG"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "Implicit",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert "ImplicitMod" not in result

    def test_empty_groups_uses_empty_string(self):
        raw = {
            "NoGroupMod": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": [],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "NoGroup",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert result["NoGroupMod"]["group"] == ""


class TestProcessStatTranslations:
    def test_basic_translation(self):
        raw = [
            {
                "ids": ["base_maximum_life"],
                "English": [{"string": "+{0} to Maximum Life"}],
            },
        ]
        result = _process_stat_translations(raw)
        assert result["base_maximum_life"] == "+{0} to Maximum Life"

    def test_skips_empty_english(self):
        raw = [
            {
                "ids": ["some_stat"],
                "English": [],
            },
        ]
        result = _process_stat_translations(raw)
        assert "some_stat" not in result

    def test_first_entry_wins(self):
        raw = [
            {
                "ids": ["stat_a"],
                "English": [{"string": "First"}],
            },
            {
                "ids": ["stat_a"],
                "English": [{"string": "Second"}],
            },
        ]
        result = _process_stat_translations(raw)
        assert result["stat_a"] == "First"

    def test_skips_empty_stat_id(self):
        raw = [
            {
                "ids": ["", "valid_stat"],
                "English": [{"string": "Template"}],
            },
        ]
        result = _process_stat_translations(raw)
        assert "" not in result
        assert result["valid_stat"] == "Template"

    def test_multiple_ids_same_template(self):
        raw = [
            {
                "ids": ["stat_x", "stat_y"],
                "English": [{"string": "Shared template"}],
            },
        ]
        result = _process_stat_translations(raw)
        assert result["stat_x"] == "Shared template"
        assert result["stat_y"] == "Shared template"


class TestProcessBenchCrafts:
    def test_filters_add_explicit_mod(self):
        raw = [
            {
                "actions": {"add_explicit_mod": "TestMod1"},
                "cost": {"Metadata/Items/Currency/CurrencyRerollRare": 4},
                "item_classes": ["Helmet"],
                "bench_tier": 1,
            },
            {
                "actions": {"link_sockets": 5},
                "cost": {"Metadata/Items/Currency/CurrencyRerollSocketLinks": 100},
                "item_classes": ["Body Armour"],
                "bench_tier": 3,
            },
        ]
        result = _process_bench_crafts(raw)
        assert len(result) == 1
        assert result[0]["mod_id"] == "TestMod1"
        assert result[0]["cost"]["Chaos Orb"] == 4

    def test_unknown_currency_path_uses_raw(self):
        raw = [
            {
                "actions": {"add_explicit_mod": "Mod1"},
                "cost": {"Metadata/Items/Currency/UnknownCurrency": 10},
                "item_classes": ["Helmet"],
                "bench_tier": 1,
            },
        ]
        result = _process_bench_crafts(raw)
        assert result[0]["cost"]["Metadata/Items/Currency/UnknownCurrency"] == 10


class TestRepoEPipelineBuild:
    def test_build_produces_all_output_files(self, tmp_path):
        import json

        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()

        base_items_raw = {
            "Meta/Helm": {
                "domain": "item",
                "release_state": "released",
                "name": "Iron Hat",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": ["helmet", "default"],
                "properties": {},
                "implicits": [],
            },
        }
        mods_raw = {
            "LifeMod1": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["IncreasedLife"],
                "spawn_weights": [{"tag": "helmet", "weight": 1000}],
                "implicit_tags": ["life"],
                "stats": [{"id": "life", "min": 10, "max": 20}],
                "required_level": 1,
                "name": "Increased Life",
                "is_essence_only": False,
            },
        }
        fossils_raw = {
            "Meta/Pristine": {
                "name": "Pristine Fossil",
                "positive_mod_weights": [{"tag": "life", "weight": 500}],
                "negative_mod_weights": [],
                "forced_mods": [],
                "added_mods": [],
            },
        }
        essences_raw = {
            "Meta/Greed1": {
                "name": "Essence of Greed",
                "type": {"tier": 5, "is_corruption_only": False},
                "item_level_restriction": None,
                "mods": {},
            },
        }
        bench_raw = [
            {
                "actions": {"add_explicit_mod": "BenchLife1"},
                "cost": {"Metadata/Items/Currency/CurrencyRerollRare": 2},
                "item_classes": ["Helmet"],
                "bench_tier": 1,
            },
        ]
        stat_trans_raw = [
            {
                "ids": ["base_maximum_life"],
                "English": [{"string": "+{0} to Maximum Life"}],
            },
        ]

        (vendor_dir / "base_items.json").write_text(json.dumps(base_items_raw))
        (vendor_dir / "mods.json").write_text(json.dumps(mods_raw))
        (vendor_dir / "fossils.json").write_text(json.dumps(fossils_raw))
        (vendor_dir / "essences.json").write_text(json.dumps(essences_raw))
        (vendor_dir / "crafting_bench_options.json").write_text(json.dumps(bench_raw))
        (vendor_dir / "stat_translations.json").write_text(json.dumps(stat_trans_raw))

        output_dir = tmp_path / "output"
        pipeline = RepoEPipeline(vendor_dir)
        results = pipeline.build(output_dir)

        assert "base_items" in results
        assert "mods" in results
        assert "fossils" in results
        assert "essences" in results
        assert "bench_crafts" in results
        assert "stat_translations" in results
        assert "mod_pool" in results

        expected = (
            "base_items",
            "mods",
            "fossils",
            "essences",
            "bench_crafts",
            "stat_translations",
            "mod_pool",
        )
        for name in expected:
            assert (output_dir / f"{name}.json").exists()
            assert results[name] > 0


@pytest.mark.parametrize("domain", sorted(BASE_ITEM_DOMAINS))
class TestProcessBaseItemsDomainEnum:
    def test_each_base_item_domain_accepted_for_non_misc(self, domain):
        if domain == "misc":
            return
        raw = {
            "Meta/X": {
                "domain": domain,
                "release_state": "released",
                "name": "Some Base",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert "Some Base" in result
        assert result["Some Base"]["domain"] == domain


class TestProcessBaseItemsParametrized:
    @pytest.mark.parametrize(
        ("item_class", "expected_prefixes", "expected_suffixes"),
        [
            ("Jewel", 2, 2),
            ("AbyssJewel", 2, 2),
            ("Flask", 1, 1),
            ("Helmet", DEFAULT_MAX_PREFIXES, DEFAULT_MAX_SUFFIXES),
            ("Body Armour", DEFAULT_MAX_PREFIXES, DEFAULT_MAX_SUFFIXES),
            ("Two Hand Sword", DEFAULT_MAX_PREFIXES, DEFAULT_MAX_SUFFIXES),
            ("", DEFAULT_MAX_PREFIXES, DEFAULT_MAX_SUFFIXES),
        ],
    )
    def test_max_affixes_by_class(self, item_class, expected_prefixes, expected_suffixes):
        domain = "misc" if item_class == "Jewel" else "item"
        raw = {
            "Meta/X": {
                "domain": domain,
                "release_state": "released",
                "name": "TestItem",
                "item_class": item_class,
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result["TestItem"]["max_prefixes"] == expected_prefixes
        assert result["TestItem"]["max_suffixes"] == expected_suffixes

    @pytest.mark.parametrize(
        "release_state",
        ["unreleased", "unique_only", "legacy", "", "UNKNOWN"],
    )
    def test_non_released_state_excluded(self, release_state):
        raw = {
            "Meta/X": {
                "domain": "item",
                "release_state": release_state,
                "name": "Excluded",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result == {}

    @pytest.mark.parametrize(
        "domain",
        ["monster", "atlas", "leaguestone", "unknown_domain"],
    )
    def test_non_base_item_domains_excluded(self, domain):
        raw = {
            "Meta/X": {
                "domain": domain,
                "release_state": "released",
                "name": "Foo",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result == {}


class TestProcessBaseItemsInvariants:
    def test_drop_level_non_negative(self):
        raw = {
            "Meta/X": {
                "domain": "item",
                "release_state": "released",
                "name": "Item",
                "item_class": "Helmet",
                "drop_level": 0,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result["Item"]["drop_level"] >= 0

    def test_max_affixes_positive_and_bounded(self):
        raw = {
            "Meta/A": {
                "domain": "item",
                "release_state": "released",
                "name": "A",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
            "Meta/B": {
                "domain": "item",
                "release_state": "released",
                "name": "B",
                "item_class": "Flask",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        for entry in result.values():
            assert entry["max_prefixes"] >= 1
            assert entry["max_suffixes"] >= 1
            assert entry["max_prefixes"] <= DEFAULT_MAX_PREFIXES
            assert entry["max_suffixes"] <= DEFAULT_MAX_SUFFIXES

    def test_id_matches_meta_path(self):
        raw = {
            "Metadata/Items/Armours/Helmets/HelmetStr1": {
                "domain": "item",
                "release_state": "released",
                "name": "Iron Hat",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result["Iron Hat"]["id"] == "Metadata/Items/Armours/Helmets/HelmetStr1"

    def test_default_drop_level_when_missing(self):
        raw = {
            "Meta/X": {
                "domain": "item",
                "release_state": "released",
                "name": "Item",
                "item_class": "Helmet",
                "tags": [],
                "properties": {},
            },
        }
        result = _process_base_items(raw)
        assert result["Item"]["drop_level"] == 0

    def test_missing_optional_lists_default_to_empty(self):
        raw = {
            "Meta/X": {
                "domain": "item",
                "release_state": "released",
                "name": "Item",
                "item_class": "Helmet",
                "drop_level": 1,
            },
        }
        result = _process_base_items(raw)
        assert result["Item"]["tags"] == []
        assert result["Item"]["properties"] == {}
        assert result["Item"]["implicits"] == []


class TestDetectInfluenceFullEnum:
    @pytest.mark.parametrize(
        ("inf_tag", "inf_name"),
        sorted(INFLUENCE_TAG_MAP.items()),
    )
    def test_each_influence_detected(self, inf_tag, inf_name):
        weights = [{"tag": f"helmet_{inf_tag}", "weight": 100}]
        assert _detect_influence(weights) == inf_name

    @pytest.mark.parametrize(
        ("inf_tag", "inf_name"),
        sorted(INFLUENCE_TAG_MAP.items()),
    )
    def test_zero_weight_not_detected(self, inf_tag, inf_name):
        weights = [{"tag": f"helmet_{inf_tag}", "weight": 0}]
        assert _detect_influence(weights) is None

    def test_empty_weights_returns_none(self):
        assert _detect_influence([]) is None

    def test_first_match_wins_when_multiple(self):
        weights = [
            {"tag": "helmet_shaper", "weight": 100},
            {"tag": "helmet_elder", "weight": 100},
        ]
        assert _detect_influence(weights) == "Shaper"

    def test_substring_does_not_falsely_match(self):
        weights = [{"tag": "shaperhelmet", "weight": 100}]
        assert _detect_influence(weights) is None


class TestProcessModsFullEnumDomains:
    @pytest.mark.parametrize("domain", sorted(PLAYER_ITEM_DOMAINS))
    def test_every_player_item_domain_accepted(self, domain):
        raw = {
            "M1": {
                "domain": domain,
                "generation_type": "prefix",
                "groups": ["G"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "X",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert "M1" in result
        assert result["M1"]["domain"] == domain

    @pytest.mark.parametrize("gen_type", ["prefix", "suffix"])
    def test_both_affix_types_accepted(self, gen_type):
        raw = {
            "M1": {
                "domain": "item",
                "generation_type": gen_type,
                "groups": ["G"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "X",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert result["M1"]["affix"] == gen_type

    @pytest.mark.parametrize(
        "gen_type",
        ["implicit", "corrupted", "tempest", "enchantment", "unique", "", "UNKNOWN"],
    )
    def test_non_affix_gen_types_excluded(self, gen_type):
        raw = {
            "M1": {
                "domain": "item",
                "generation_type": gen_type,
                "groups": ["G"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "X",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert result == {}


class TestProcessModsInvariants:
    def test_affix_field_only_prefix_or_suffix(self):
        raw = {
            "P": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["G1"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "P",
                "is_essence_only": False,
            },
            "S": {
                "domain": "item",
                "generation_type": "suffix",
                "groups": ["G2"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "S",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        for entry in result.values():
            assert entry["affix"] in {"prefix", "suffix"}

    def test_required_level_non_negative(self):
        raw = {
            "M": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["G"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 30,
                "name": "M",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert result["M"]["required_level"] >= 0

    def test_default_required_level_zero(self):
        raw = {
            "M": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["G"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "name": "M",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        assert result["M"]["required_level"] == 0

    def test_mod_group_does_not_span_prefix_and_suffix(self):
        raw = {
            "P1": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["LifeGroup"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "Life Pre",
                "is_essence_only": False,
            },
            "P2": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["LifeGroup"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 5,
                "name": "Life Pre 2",
                "is_essence_only": False,
            },
            "S1": {
                "domain": "item",
                "generation_type": "suffix",
                "groups": ["ResGroup"],
                "spawn_weights": [],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "Res Suf",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        group_affixes: dict[str, set[str]] = {}
        for entry in result.values():
            group_affixes.setdefault(entry["group"], set()).add(entry["affix"])
        for group, affixes in group_affixes.items():
            if group:
                assert len(affixes) == 1, f"group {group!r} appears as both {affixes}"

    def test_influence_field_in_known_set_or_none(self):
        raw = {
            "M": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["G"],
                "spawn_weights": [{"tag": "helmet_shaper", "weight": 500}],
                "implicit_tags": [],
                "stats": [],
                "required_level": 1,
                "name": "M",
                "is_essence_only": False,
            },
        }
        result = _process_mods(raw)
        valid = set(INFLUENCE_TAG_MAP.values()) | {None}
        assert result["M"]["influence"] in valid


class TestBuildModPoolFullEnumDomains:
    @pytest.mark.parametrize(
        "base_domain",
        sorted(MOD_DOMAIN_FOR_BASE_DOMAIN.keys()),
    )
    def test_each_base_domain_resolves_allowed_mods(self, base_domain):
        allowed = MOD_DOMAIN_FOR_BASE_DOMAIN[base_domain]
        chosen_mod_domain = next(iter(allowed))
        base_items = {
            "B": {"id": "Meta/B", "domain": base_domain, "tags": ["test_tag"]},
        }
        mods = {
            "AllowedMod": {
                "is_essence_only": False,
                "domain": chosen_mod_domain,
                "spawn_weights": [{"tag": "test_tag", "weight": 100}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "AllowedMod" in pool["Meta/B"]

    def test_unknown_base_domain_uses_default_item_crafted(self):
        base_items = {
            "B": {"id": "Meta/B", "domain": "totally_unknown", "tags": ["helmet"]},
        }
        mods = {
            "ItemMod": {
                "is_essence_only": False,
                "domain": "item",
                "spawn_weights": [{"tag": "helmet", "weight": 100}],
            },
            "CraftedMod": {
                "is_essence_only": False,
                "domain": "crafted",
                "spawn_weights": [{"tag": "helmet", "weight": 100}],
            },
            "FlaskMod": {
                "is_essence_only": False,
                "domain": "flask",
                "spawn_weights": [{"tag": "helmet", "weight": 100}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "ItemMod" in pool["Meta/B"]
        assert "CraftedMod" in pool["Meta/B"]
        assert "FlaskMod" not in pool["Meta/B"]


class TestBuildModPoolInvariants:
    def test_pool_keys_are_base_ids(self):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet"]},
            "Boots": {"id": "Meta/Boots", "tags": ["boots"]},
        }
        mods: dict[str, dict] = {}
        pool = _build_mod_pool(base_items, mods)
        assert set(pool.keys()) == {"Meta/Helm", "Meta/Boots"}

    def test_pool_values_subset_of_mod_ids(self):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet"]},
        }
        mods = {
            "M1": {"is_essence_only": False, "spawn_weights": [{"tag": "helmet", "weight": 100}]},
            "M2": {"is_essence_only": False, "spawn_weights": [{"tag": "weapon", "weight": 100}]},
        }
        pool = _build_mod_pool(base_items, mods)
        assert set(pool["Meta/Helm"]).issubset(set(mods.keys()))

    def test_pool_does_not_contain_essence_only_mods(self):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet"]},
        }
        mods = {
            "M1": {"is_essence_only": True, "spawn_weights": [{"tag": "helmet", "weight": 100}]},
            "M2": {"is_essence_only": False, "spawn_weights": [{"tag": "helmet", "weight": 100}]},
        }
        pool = _build_mod_pool(base_items, mods)
        for mod_id in pool["Meta/Helm"]:
            assert not mods[mod_id]["is_essence_only"]

    def test_pool_no_duplicate_entries_per_base(self):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet", "armour"]},
        }
        mods = {
            "MultiTagMod": {
                "is_essence_only": False,
                "spawn_weights": [
                    {"tag": "helmet", "weight": 100},
                    {"tag": "armour", "weight": 100},
                ],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert pool["Meta/Helm"].count("MultiTagMod") == 1

    def test_no_zero_weight_mod_in_pool(self):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet"]},
        }
        mods = {
            "ZeroWeight": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "helmet", "weight": 0}],
            },
            "PosWeight": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": "helmet", "weight": 100}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "ZeroWeight" not in pool["Meta/Helm"]
        assert "PosWeight" in pool["Meta/Helm"]


class TestBuildModPoolInfluenceEnum:
    @pytest.mark.parametrize("inf_tag", sorted(INFLUENCE_TAG_MAP))
    def test_each_influence_tag_matched_via_suffix(self, inf_tag):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet"]},
        }
        mods = {
            "InfluencedMod": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": f"helmet_{inf_tag}", "weight": 500}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert "InfluencedMod" in pool["Meta/Helm"]

    @pytest.mark.parametrize("inf_tag", sorted(INFLUENCE_TAG_MAP))
    def test_each_influence_tag_zero_weight_excluded(self, inf_tag):
        base_items = {
            "Helm": {"id": "Meta/Helm", "tags": ["helmet"]},
        }
        mods = {
            "ZeroInfluenced": {
                "is_essence_only": False,
                "spawn_weights": [{"tag": f"helmet_{inf_tag}", "weight": 0}],
            },
        }
        pool = _build_mod_pool(base_items, mods)
        assert pool["Meta/Helm"] == []


class TestProcessFossilsInvariants:
    def test_positive_weights_non_negative(self):
        raw = {
            "F": {
                "name": "F",
                "positive_mod_weights": [
                    {"tag": "life", "weight": 1000},
                    {"tag": "defences", "weight": 0},
                ],
                "negative_mod_weights": [],
            },
        }
        result = _process_fossils(raw)
        for weight in result["F"]["positive_weights"].values():
            assert weight >= 0

    def test_blocked_tags_correspond_to_zero_negative_weights(self):
        raw = {
            "F": {
                "name": "F",
                "positive_mod_weights": [],
                "negative_mod_weights": [
                    {"tag": "fire", "weight": 0},
                    {"tag": "cold", "weight": 50},
                    {"tag": "lightning", "weight": 0},
                ],
            },
        }
        result = _process_fossils(raw)
        assert set(result["F"]["blocked_tags"]) == {"fire", "lightning"}
        for tag in result["F"]["blocked_tags"]:
            assert result["F"]["negative_weights"][tag] == 0

    def test_weight_divided_by_constant(self):
        raw = {
            "F": {
                "name": "F",
                "positive_mod_weights": [{"tag": "life", "weight": 500}],
                "negative_mod_weights": [],
            },
        }
        result = _process_fossils(raw)
        assert result["F"]["positive_weights"]["life"] == 500 / FOSSIL_WEIGHT_DIVISOR

    def test_default_forced_and_added_lists(self):
        raw = {
            "F": {
                "name": "F",
                "positive_mod_weights": [],
                "negative_mod_weights": [],
            },
        }
        result = _process_fossils(raw)
        assert result["F"]["forced_mods"] == []
        assert result["F"]["added_mods"] == []


class TestProcessEssencesInvariants:
    @pytest.mark.parametrize("tier", [1, 2, 3, 4, 5, 6, 7])
    def test_tier_preserved(self, tier):
        raw = {
            "E": {
                "name": f"Essence {tier}",
                "type": {"tier": tier, "is_corruption_only": False},
                "item_level_restriction": 1,
                "mods": {},
            },
        }
        result = _process_essences(raw)
        assert result[f"Essence {tier}"]["tier"] == tier

    def test_corruption_only_flag_preserved(self):
        raw = {
            "E": {
                "name": "Corrupt Essence",
                "type": {"tier": 7, "is_corruption_only": True},
                "item_level_restriction": 82,
                "mods": {},
            },
        }
        result = _process_essences(raw)
        assert result["Corrupt Essence"]["is_corruption_only"] is True

    def test_default_tier_zero_when_type_missing(self):
        raw = {
            "E": {"name": "NoType", "mods": {}},
        }
        result = _process_essences(raw)
        assert result["NoType"]["tier"] == 0
        assert result["NoType"]["is_corruption_only"] is False

    def test_level_restriction_preserved_when_none(self):
        raw = {
            "E": {
                "name": "E",
                "type": {"tier": 1, "is_corruption_only": False},
                "item_level_restriction": None,
                "mods": {},
            },
        }
        result = _process_essences(raw)
        assert result["E"]["level_restriction"] is None


class TestProcessBenchCraftsInvariants:
    @pytest.mark.parametrize(
        ("path", "name"),
        sorted(CURRENCY_PATH_NAMES.items()),
    )
    def test_every_currency_path_normalized(self, path, name):
        raw = [
            {
                "actions": {"add_explicit_mod": "M"},
                "cost": {path: 5},
                "item_classes": ["Helmet"],
                "bench_tier": 1,
            },
        ]
        result = _process_bench_crafts(raw)
        assert result[0]["cost"][name] == 5

    def test_costs_are_positive_amounts(self):
        raw = [
            {
                "actions": {"add_explicit_mod": "M"},
                "cost": {"Metadata/Items/Currency/CurrencyRerollRare": 4},
                "item_classes": ["Helmet"],
                "bench_tier": 1,
            },
        ]
        result = _process_bench_crafts(raw)
        for amount in result[0]["cost"].values():
            assert amount > 0

    def test_skips_entries_without_add_explicit_mod(self):
        raw = [
            {"actions": {}, "cost": {}, "item_classes": ["X"], "bench_tier": 1},
            {"actions": {"link_sockets": 5}, "cost": {}, "item_classes": ["X"], "bench_tier": 1},
            {
                "actions": {"add_explicit_mod": ""},
                "cost": {},
                "item_classes": ["X"],
                "bench_tier": 1,
            },
        ]
        result = _process_bench_crafts(raw)
        assert result == []

    def test_default_bench_tier_zero(self):
        raw = [
            {
                "actions": {"add_explicit_mod": "M"},
                "cost": {},
                "item_classes": [],
            },
        ]
        result = _process_bench_crafts(raw)
        assert result[0]["bench_tier"] == 0

    def test_empty_input_returns_empty_list(self):
        assert _process_bench_crafts([]) == []


class TestProcessStatTranslationsInvariants:
    def test_returned_dict_values_are_strings(self):
        raw = [
            {"ids": ["a"], "English": [{"string": "Template A"}]},
            {"ids": ["b"], "English": [{"string": ""}]},
        ]
        result = _process_stat_translations(raw)
        for v in result.values():
            assert isinstance(v, str)

    def test_missing_string_key_defaults_empty(self):
        raw = [
            {"ids": ["x"], "English": [{}]},
        ]
        result = _process_stat_translations(raw)
        assert result["x"] == ""

    def test_empty_input_returns_empty_dict(self):
        assert _process_stat_translations([]) == {}

    def test_first_wins_across_separate_entries(self):
        raw = [
            {"ids": ["s"], "English": [{"string": "first"}]},
            {"ids": ["s"], "English": [{"string": "second"}]},
            {"ids": ["s"], "English": [{"string": "third"}]},
        ]
        result = _process_stat_translations(raw)
        assert result["s"] == "first"


class TestRepoEPipelineNegative:
    def test_missing_vendor_file_raises(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        output_dir = tmp_path / "out"
        pipeline = RepoEPipeline(vendor_dir)
        with pytest.raises(FileNotFoundError):
            pipeline.build(output_dir)

    def test_invalid_json_raises(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        for fname in (
            "base_items.json",
            "mods.json",
            "fossils.json",
            "essences.json",
            "crafting_bench_options.json",
            "stat_translations.json",
        ):
            (vendor_dir / fname).write_text("not valid json {{{", encoding="utf-8")
        output_dir = tmp_path / "out"
        pipeline = RepoEPipeline(vendor_dir)
        with pytest.raises(json.JSONDecodeError):
            pipeline.build(output_dir)


class TestRepoEPipelineBuildInvariants:
    def _write_minimal_vendor(self, vendor_dir):
        base_items_raw = {
            "Meta/Helm": {
                "domain": "item",
                "release_state": "released",
                "name": "Iron Hat",
                "item_class": "Helmet",
                "drop_level": 1,
                "tags": ["helmet", "default"],
                "properties": {},
                "implicits": [],
            },
        }
        mods_raw = {
            "LifeMod1": {
                "domain": "item",
                "generation_type": "prefix",
                "groups": ["IncreasedLife"],
                "spawn_weights": [{"tag": "helmet", "weight": 1000}],
                "implicit_tags": ["life"],
                "stats": [{"id": "life", "min": 10, "max": 20}],
                "required_level": 1,
                "name": "Increased Life",
                "is_essence_only": False,
            },
        }
        (vendor_dir / "base_items.json").write_text(json.dumps(base_items_raw))
        (vendor_dir / "mods.json").write_text(json.dumps(mods_raw))
        (vendor_dir / "fossils.json").write_text(json.dumps({}))
        (vendor_dir / "essences.json").write_text(json.dumps({}))
        (vendor_dir / "crafting_bench_options.json").write_text(json.dumps([]))
        (vendor_dir / "stat_translations.json").write_text(json.dumps([]))

    def test_output_dir_created_when_missing(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        self._write_minimal_vendor(vendor_dir)
        output_dir = tmp_path / "nested" / "deeper" / "out"
        assert not output_dir.exists()
        pipeline = RepoEPipeline(vendor_dir)
        pipeline.build(output_dir)
        assert output_dir.is_dir()

    def test_all_outputs_are_valid_json(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        self._write_minimal_vendor(vendor_dir)
        output_dir = tmp_path / "out"
        pipeline = RepoEPipeline(vendor_dir)
        pipeline.build(output_dir)
        for name in (
            "base_items",
            "mods",
            "fossils",
            "essences",
            "bench_crafts",
            "stat_translations",
            "mod_pool",
        ):
            data = json.loads((output_dir / f"{name}.json").read_text(encoding="utf-8"))
            assert data is not None

    def test_mod_pool_keys_are_base_item_ids(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        self._write_minimal_vendor(vendor_dir)
        output_dir = tmp_path / "out"
        pipeline = RepoEPipeline(vendor_dir)
        pipeline.build(output_dir)
        base_items = json.loads((output_dir / "base_items.json").read_text(encoding="utf-8"))
        mod_pool = json.loads((output_dir / "mod_pool.json").read_text(encoding="utf-8"))
        base_ids = {entry["id"] for entry in base_items.values()}
        assert set(mod_pool.keys()) == base_ids

    def test_results_sizes_positive_bytes(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        self._write_minimal_vendor(vendor_dir)
        output_dir = tmp_path / "out"
        pipeline = RepoEPipeline(vendor_dir)
        results = pipeline.build(output_dir)
        for size in results.values():
            assert size > 0

    def test_idempotent_rebuild_produces_same_outputs(self, tmp_path):
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        self._write_minimal_vendor(vendor_dir)
        output_dir = tmp_path / "out"
        pipeline = RepoEPipeline(vendor_dir)
        pipeline.build(output_dir)
        first = {
            name: (output_dir / f"{name}.json").read_text(encoding="utf-8")
            for name in (
                "base_items",
                "mods",
                "fossils",
                "essences",
                "bench_crafts",
                "stat_translations",
                "mod_pool",
            )
        }
        pipeline.build(output_dir)
        for name, content in first.items():
            assert (output_dir / f"{name}.json").read_text(encoding="utf-8") == content


class TestProcessBaseItemsConsistency:
    def test_jewel_max_affixes_consistent_across_classes(self):
        raw = {
            f"Meta/{cls}": {
                "domain": "item",
                "release_state": "released",
                "name": cls,
                "item_class": cls,
                "drop_level": 1,
                "tags": [],
                "properties": {},
            }
            for cls in MAX_PREFIXES_BY_CLASS
        }
        result = _process_base_items(raw)
        for cls in MAX_PREFIXES_BY_CLASS:
            assert result[cls]["max_prefixes"] == MAX_PREFIXES_BY_CLASS[cls]
            assert result[cls]["max_suffixes"] == MAX_SUFFIXES_BY_CLASS[cls]

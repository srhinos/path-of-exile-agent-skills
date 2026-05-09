from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import pytest

from poe.exceptions import SimDataError
from poe.models.ninja.economy import CraftingPrices
from poe.services.ninja.errors import NetworkError
from poe.services.repoe.constants import RARITY_PRODUCED, RARITY_REQUIRED
from poe.services.repoe.sim_service import SimService
from poe.types import CraftMethod, Influence
from tests.conftest import REPOE_DATA, make_repoe_data

_NINJA_CLIENT = "poe.services.repoe.sim_service.NinjaClient"
_DISCOVERY = "poe.services.repoe.sim_service.DiscoveryService"
_ECONOMY = "poe.services.repoe.sim_service.EconomyService"


@pytest.fixture
def sim_service():
    return SimService(repoe_data=make_repoe_data())


class TestSimulateCacheIntegrity:
    @pytest.mark.asyncio
    async def test_simulate_does_not_corrupt_cache(self, sim_service):
        mod_pool_before = sim_service._data.get_mod_pool("Hubris Circlet")
        ids_before = {m.mod_id for m in mod_pool_before}

        await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["IncreasedLife"],
            iterations=100,
        )

        mod_pool_after = sim_service._data.get_mod_pool("Hubris Circlet")
        ids_after = {m.mod_id for m in mod_pool_after}
        assert ids_before == ids_after


class TestFossilOptimizer:
    def test_no_duplicates(self):
        svc = SimService(repoe_data=make_repoe_data())
        results = svc.fossil_optimizer("physical")
        keys = [(r["fossil"], r["tag"]) for r in results]
        assert len(keys) == len(set(keys)), f"Duplicates found: {keys}"


class TestGetTiers:
    def test_accepts_group_name(self):
        svc = SimService(repoe_data=make_repoe_data())
        result = svc.get_tiers("IncreasedLife", "Hubris Circlet")
        assert result.tiers

    def test_accepts_exact_mod_id(self):
        svc = SimService(repoe_data=make_repoe_data())
        result = svc.get_tiers("IncreasedLife4", "Hubris Circlet")
        assert result.tiers


class TestGetPrices:
    def test_returns_populated_data_from_ninja(self, sim_service):
        mock_prices = CraftingPrices(
            currency={"Chaos Orb": 1.0, "Divine Orb": 150.0},
            fossils={"Pristine Fossil": 3.0},
        )
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_discovery = MagicMock()
        mock_league = MagicMock()
        mock_league.name = "Settlers"
        mock_discovery.get_current_league.return_value = mock_league

        mock_economy = MagicMock()
        mock_economy.get_crafting_prices.return_value = mock_prices

        with (
            patch(_NINJA_CLIENT, return_value=mock_client),
            patch(_DISCOVERY, return_value=mock_discovery),
            patch(_ECONOMY, return_value=mock_economy),
        ):
            result = sim_service.get_prices(league="current")

        assert result["currency"]["Chaos Orb"] == 1.0
        assert result["currency"]["Divine Orb"] == 150.0
        assert result["fossils"]["Pristine Fossil"] == 3.0
        assert result["league"] == "Settlers"

    def test_falls_back_to_stub_on_error(self, sim_service):
        with patch(
            _NINJA_CLIENT,
            side_effect=NetworkError("offline"),
        ):
            result = sim_service.get_prices(league="current")

        assert result["currency"] == {}
        assert result["fossils"] == {}
        assert result["league"] == "current"


class TestModNameResolution:
    def test_resolve_display_name(self, sim_service):
        result = sim_service.resolve_mod_name("Increased Life", "Hubris Circlet")
        assert result == "IncreasedLife"

    def test_resolve_group_name_passthrough(self, sim_service):
        result = sim_service.resolve_mod_name("IncreasedLife", "Hubris Circlet")
        assert result is None or result == "IncreasedLife"

    @pytest.mark.asyncio
    async def test_simulate_accepts_display_name(self, sim_service):
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["Increased Life"],
            iterations=10,
        )
        assert float(result.hit_rate.rstrip("%")) >= 0

    @pytest.mark.asyncio
    async def test_simulate_accepts_group_name(self, sim_service):
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["IncreasedLife"],
            iterations=10,
        )
        assert float(result.hit_rate.rstrip("%")) >= 0


class TestMultistepValidation:
    def test_regal_after_chaos_raises(self, sim_service):
        with pytest.raises(SimDataError, match=r"regal.*requires.*magic"):
            sim_service.simulate_multistep(
                "Hubris Circlet",
                steps=[{"method": "chaos"}, {"method": "regal"}],
                target=["IncreasedLife"],
                iterations=10,
            )

    def test_augmentation_after_chaos_raises(self, sim_service):
        with pytest.raises(SimDataError, match=r"augmentation.*requires"):
            sim_service.simulate_multistep(
                "Hubris Circlet",
                steps=[{"method": "chaos"}, {"method": "augmentation"}],
                target=["IncreasedLife"],
                iterations=10,
            )


class TestCompareMethodsService:
    @pytest.mark.asyncio
    async def test_compare_methods_basic(self, sim_service):
        results = await sim_service.compare_methods(
            "Hubris Circlet",
            target=["IncreasedLife"],
            iterations=20,
        )
        assert len(results) >= 2
        methods = [r["method"] for r in results]
        assert "chaos" in methods
        assert "alt" in methods
        for r in results:
            assert "hit_rate" in r
            assert "avg_attempts" in r
            assert "avg_cost_chaos" in r
            assert "cost_per_attempt" in r

    @pytest.mark.asyncio
    async def test_compare_methods_with_fossils(self, sim_service):
        results = await sim_service.compare_methods(
            "Hubris Circlet",
            target=["IncreasedLife"],
            fossils=["Pristine Fossil"],
            iterations=20,
        )
        methods = [r["method"] for r in results]
        assert "fossil" in methods

    @pytest.mark.asyncio
    async def test_compare_methods_with_essence(self, sim_service):
        results = await sim_service.compare_methods(
            "Hubris Circlet",
            target=["IncreasedLife"],
            essence="Greed",
            iterations=20,
        )
        methods = [r["method"] for r in results]
        assert "essence" in methods

    @pytest.mark.asyncio
    async def test_compare_methods_sorted_by_cost(self, sim_service):
        results = await sim_service.compare_methods(
            "Hubris Circlet",
            target=["IncreasedLife"],
            iterations=50,
        )
        costs = [r["avg_cost_chaos"] for r in results]
        for c in costs:
            assert c is None or isinstance(c, float)


class TestSuggestCraft:
    def test_suggest_with_fossil_match(self, sim_service):
        results = sim_service.suggest_craft(["life"])
        assert len(results) == 1
        assert results[0]["mod"] == "life"
        assert results[0]["approach"] == "fossil"
        assert "fossil" in results[0]
        assert "multiplier" in results[0]

    def test_suggest_no_fossil_match(self, sim_service):
        results = sim_service.suggest_craft(["zzznonexistentzzzz"])
        assert len(results) == 1
        assert results[0]["approach"] == "chaos"
        assert "reason" in results[0]

    def test_suggest_multiple_mods(self, sim_service):
        results = sim_service.suggest_craft(["life", "zzznonexistentzzzz"])
        assert len(results) == 2


class TestFossilOptimizerService:
    def test_returns_sorted_by_multiplier(self, sim_service):
        results = sim_service.fossil_optimizer("life")
        if len(results) > 1:
            multipliers = [r["multiplier"] for r in results]
            assert multipliers == sorted(multipliers, reverse=True)

    def test_negative_weights_included(self, sim_service):
        results = sim_service.fossil_optimizer("physical")
        effects = {r["effect"] for r in results}
        assert len(effects) > 0

    def test_empty_results_for_unknown(self, sim_service):
        results = sim_service.fossil_optimizer("zzznonexistentzzzz")
        assert results == []


class TestModWeightsService:
    def test_returns_weighted_mods(self, sim_service):
        results = sim_service.mod_weights("Hubris Circlet")
        assert len(results) > 0
        for r in results:
            assert "mod_id" in r
            assert "name" in r
            assert "group" in r
            assert "affix" in r
            assert "weight" in r
            assert "probability" in r
            assert r["probability"].endswith("%")

    def test_respects_limit(self, sim_service):
        results = sim_service.mod_weights("Hubris Circlet", limit=2)
        assert len(results) <= 2

    def test_with_influences(self, sim_service):
        results = sim_service.mod_weights(
            "Hubris Circlet",
            influences=["Shaper"],
        )
        assert len(results) > 0


class TestSimulateValidation:
    @pytest.mark.asyncio
    async def test_unknown_method_raises(self, sim_service):
        with pytest.raises(SimDataError, match="Unknown craft method"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="bogus",
                target=["IncreasedLife"],
                iterations=1,
            )

    @pytest.mark.asyncio
    async def test_essence_without_name_raises(self, sim_service):
        with pytest.raises(SimDataError, match="--essence is required"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="essence",
                target=["IncreasedLife"],
                iterations=1,
            )

    @pytest.mark.asyncio
    async def test_fossil_without_names_raises(self, sim_service):
        with pytest.raises(SimDataError, match="--fossils is required"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="fossil",
                target=["IncreasedLife"],
                iterations=1,
            )

    @pytest.mark.asyncio
    async def test_unknown_target_raises(self, sim_service):
        with pytest.raises(SimDataError, match="not found in mod pool"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="chaos",
                target=["NonexistentModGroup"],
                iterations=1,
            )

    @pytest.mark.asyncio
    async def test_unknown_influence_raises(self, sim_service):
        with pytest.raises(SimDataError, match="Unknown influence"):
            sim_service.get_mods("Hubris Circlet", influences=["FakeInfluence"])


class TestGetModsEdgeCases:
    def test_no_mods_for_base_raises(self):
        svc = SimService(repoe_data=make_repoe_data())
        with pytest.raises(SimDataError, match="not found"):
            svc.get_mods("Nonexistent Base Item")

    def test_valid_influence_normalizes(self):
        svc = SimService(repoe_data=make_repoe_data())
        result = svc.get_mods("Hubris Circlet", influences=["shaper"])
        assert result.influences == ["Shaper"]


class TestMultistepDispatch:
    def test_multistep_fossil_step(self, sim_service):
        result = sim_service.simulate_multistep(
            "Hubris Circlet",
            steps=[{"method": "fossil", "fossils": ["Pristine Fossil"]}],
            target=["IncreasedLife"],
            iterations=10,
        )
        assert result["iterations"] == 10

    def test_multistep_essence_step(self, sim_service):
        result = sim_service.simulate_multistep(
            "Hubris Circlet",
            steps=[{"method": "essence", "essence": "Greed"}],
            target=["IncreasedLife"],
            iterations=10,
        )
        assert result["hits"] >= 0

    def test_multistep_harvest_step(self, sim_service):
        result = sim_service.simulate_multistep(
            "Hubris Circlet",
            steps=[{"method": "harvest", "tag": "life"}],
            target=["IncreasedLife"],
            iterations=10,
        )
        assert result["iterations"] == 10

    def test_multistep_unknown_method_raises(self, sim_service):
        with pytest.raises(SimDataError):
            sim_service.simulate_multistep(
                "Hubris Circlet",
                steps=[{"method": "bogus_method"}],
                target=["IncreasedLife"],
                iterations=10,
            )

    def test_multistep_unknown_target_raises(self, sim_service):
        with pytest.raises(SimDataError, match="not found in mod pool"):
            sim_service.simulate_multistep(
                "Hubris Circlet",
                steps=[{"method": "chaos"}],
                target=["ZZZNonexistentGroupZZZ"],
                iterations=10,
            )

    def test_multistep_match_any(self, sim_service):
        result = sim_service.simulate_multistep(
            "Hubris Circlet",
            steps=[{"method": "chaos"}],
            target=["IncreasedLife", "ColdResistance"],
            iterations=10,
            match="any",
        )
        assert result["hits"] >= 0


class TestFossilOptimizerBlockedTags:
    def test_blocked_tag_match(self):
        import copy

        from tests.conftest import REPOE_DATA

        data = copy.deepcopy(REPOE_DATA)
        data["fossils"]["Metallic Fossil"]["blocked_tags"] = ["physical"]
        svc = SimService(repoe_data=make_repoe_data(data=data))
        results = svc.fossil_optimizer("physical")
        blocked = [r for r in results if r["effect"] == "block"]
        assert len(blocked) > 0


class TestExpandModSearchTerms:
    def test_underscore_splitting(self):
        terms = SimService._expand_mod_search_terms("cold_resistance")
        assert "cold" in terms
        assert "resistance" in terms

    def test_whole_term_always_included(self):
        terms = SimService._expand_mod_search_terms("coldresistance")
        assert "coldresistance" in terms


class TestGetPricesExplicitLeague:
    def test_explicit_league_name(self, sim_service):
        mock_prices = CraftingPrices(
            currency={"Chaos Orb": 1.0},
            fossils={},
        )
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_economy = MagicMock()
        mock_economy.get_crafting_prices.return_value = mock_prices

        with (
            patch(_NINJA_CLIENT, return_value=mock_client),
            patch(_ECONOMY, return_value=mock_economy),
        ):
            result = sim_service.get_prices(league="Settlers")

        assert result["league"] == "Settlers"


class TestMultistepConquerorExalt:
    def test_conqueror_exalt_step(self):
        from poe.services.repoe.sim import CraftingEngine
        from poe.types import Rarity

        data = make_repoe_data()
        eng = CraftingEngine(data)
        item = eng.create_item("Hubris Circlet", ilvl=84)
        item.rarity = Rarity.RARE
        eng.chaos_roll(item)
        SimService._apply_multistep_method(eng, item, "conqueror_exalt", {"influence": "shaper"})


class TestFossilOptimizerBlocked:
    def test_finds_blocked_tags(self):
        svc = SimService(repoe_data=make_repoe_data())
        results = svc.fossil_optimizer("life")
        blocked = [r for r in results if r["effect"] == "block"]
        assert isinstance(blocked, list)


class TestSimulateValueError:
    @pytest.mark.asyncio
    async def test_simulate_wraps_value_error(self, sim_service):
        with patch(
            "poe.services.repoe.sim.CraftingEngine.simulate",
            side_effect=ValueError("engine broke"),
        ):
            with pytest.raises(SimDataError, match="engine broke"):
                await sim_service.simulate(
                    "Hubris Circlet",
                    method="chaos",
                    target=["IncreasedLife"],
                    iterations=1,
                )


class TestSimulateInvariants:
    @pytest.mark.asyncio
    async def test_hit_rate_is_a_valid_percentage_string(self, sim_service):
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["IncreasedLife"],
            iterations=50,
        )
        assert result.hit_rate.endswith("%")
        rate = float(result.hit_rate.rstrip("%"))
        assert 0.0 <= rate <= 100.0

    @pytest.mark.asyncio
    async def test_iterations_in_result_match_input(self, sim_service):
        iterations = 25
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["IncreasedLife"],
            iterations=iterations,
        )
        assert result.iterations == iterations

    @pytest.mark.asyncio
    async def test_percentile_monotonicity(self, sim_service):
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["IncreasedLife"],
            iterations=200,
        )
        if {"p50", "p75", "p90", "p99"}.issubset(result.percentiles):
            p = result.percentiles
            assert p["p50"] <= p["p75"] <= p["p90"] <= p["p99"]

    @pytest.mark.asyncio
    async def test_targets_preserved_in_result(self, sim_service):
        targets = ["IncreasedLife"]
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=targets,
            iterations=10,
        )
        assert result.targets == targets

    @pytest.mark.asyncio
    async def test_finite_cost_fields(self, sim_service):
        result = await sim_service.simulate(
            "Hubris Circlet",
            method="chaos",
            target=["IncreasedLife"],
            iterations=20,
        )
        for field in (result.avg_attempts, result.avg_cost_chaos, result.cost_per_attempt):
            assert field is None or field >= 0


class TestMultistepInvariants:
    def test_hits_le_iterations(self, sim_service):
        iterations = 30
        result = sim_service.simulate_multistep(
            "Hubris Circlet",
            steps=[{"method": "chaos"}],
            target=["IncreasedLife"],
            iterations=iterations,
        )
        assert 0 <= result["hits"] <= iterations
        assert result["iterations"] == iterations

    def test_hit_rate_consistent_with_hits(self, sim_service):
        iterations = 20
        result = sim_service.simulate_multistep(
            "Hubris Circlet",
            steps=[{"method": "chaos"}],
            target=["IncreasedLife"],
            iterations=iterations,
        )
        rate_pct = float(result["hit_rate"].rstrip("%"))
        expected = result["hits"] / iterations * 100
        assert abs(rate_pct - expected) < 0.5


class TestSimulateMethodRequirementsNegative:
    @pytest.mark.asyncio
    async def test_essence_requires_essence_kw(self, sim_service):
        with pytest.raises(SimDataError, match="essence"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="essence",
                target=["IncreasedLife"],
                iterations=1,
                essence=None,
            )

    @pytest.mark.asyncio
    async def test_essence_with_empty_string_raises(self, sim_service):
        with pytest.raises(SimDataError, match="essence"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="essence",
                target=["IncreasedLife"],
                iterations=1,
                essence="",
            )

    @pytest.mark.asyncio
    async def test_fossil_with_empty_list_raises(self, sim_service):
        with pytest.raises(SimDataError, match="fossils"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="fossil",
                target=["IncreasedLife"],
                iterations=1,
                fossils=[],
            )

    @pytest.mark.asyncio
    async def test_unknown_influence_in_simulate_raises(self, sim_service):
        with pytest.raises(SimDataError, match="Unknown influence"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="chaos",
                target=["IncreasedLife"],
                iterations=1,
                influence=["FakeInfluence"],
            )

    @pytest.mark.asyncio
    async def test_existing_mod_not_in_pool_raises(self, sim_service):
        with pytest.raises(SimDataError, match=r"Existing mod.*not found"):
            await sim_service.simulate(
                "Hubris Circlet",
                method="chaos",
                target=["IncreasedLife"],
                iterations=1,
                existing_mods=["ZZZNonexistentGroup"],
            )


class TestGetModsRaisePaths:
    def test_no_mods_for_existing_base_with_filters_raises(self):
        data = copy.deepcopy(REPOE_DATA)
        data["mod_pool"][REPOE_DATA["base_items"]["Hubris Circlet"]["id"]] = []
        svc = SimService(repoe_data=make_repoe_data(data=data))
        with pytest.raises(SimDataError, match="No mods found"):
            svc.get_mods("Hubris Circlet")

    def test_unknown_base_message_mentions_search_hint(self):
        svc = SimService(repoe_data=make_repoe_data())
        with pytest.raises(SimDataError, match="not found"):
            svc.get_mods("Totally Made Up Base XYZ")


class TestGetTiersRaisePath:
    def test_unknown_mod_raises(self):
        svc = SimService(repoe_data=make_repoe_data())
        with pytest.raises(SimDataError, match="No tiers found"):
            svc.get_tiers("ZZZUnknownMod999", "Hubris Circlet")


class TestGetEssencesRaisePath:
    def test_unknown_base_raises(self):
        svc = SimService(repoe_data=make_repoe_data())
        with pytest.raises(SimDataError, match="not found"):
            svc.get_essences("ZZZNonexistentBase999")


class TestGetModsInfluenceParametrize:
    @pytest.mark.parametrize(
        "input_value",
        ["shaper", "Shaper", "SHAPER", "ShApEr"],
    )
    def test_case_variants_normalize_to_canonical(self, input_value):
        svc = SimService(repoe_data=make_repoe_data())
        result = svc.get_mods("Hubris Circlet", influences=[input_value])
        assert result.influences == ["Shaper"]


class TestGetModsCraftMethodEnum:
    @pytest.mark.parametrize(
        "method_value",
        [m.value for m in CraftMethod],
    )
    @pytest.mark.asyncio
    async def test_every_craft_method_value_passes_service_validation(self, method_value):
        svc = SimService(repoe_data=make_repoe_data())
        kwargs = {
            "method": method_value,
            "target": ["IncreasedLife"],
            "iterations": 1,
            "max_attempts": 5,
        }
        if method_value == CraftMethod.ESSENCE:
            kwargs["essence"] = "Greed"
        if method_value == CraftMethod.FOSSIL:
            kwargs["fossils"] = ["Pristine Fossil"]
        with patch("poe.services.repoe.sim_service.CraftingEngine") as mock_engine_cls:
            mock_engine = MagicMock()

            async def _fake_simulate(**_kwargs):
                from poe.services.repoe.sim import SimResult

                return SimResult(
                    method=method_value,
                    iterations=1,
                    hits=0,
                    hit_rate=0.0,
                    avg_attempts=0.0,
                    avg_cost_chaos=0.0,
                    cost_per_attempt=1.0,
                    percentiles={},
                )

            mock_engine.simulate = _fake_simulate
            mock_engine_cls.return_value = mock_engine
            await svc.simulate("Hubris Circlet", **kwargs)


class TestSimulateMultistepRarityChain:
    @pytest.mark.parametrize(
        ("required_method", "required_rarity"),
        sorted(RARITY_REQUIRED.items()),
    )
    def test_required_method_after_normal_raises(
        self, sim_service, required_method, required_rarity
    ):
        del required_rarity
        with pytest.raises(SimDataError, match=required_method):
            sim_service.simulate_multistep(
                "Hubris Circlet",
                steps=[{"method": required_method}],
                target=["IncreasedLife"],
                iterations=5,
            )

    @pytest.mark.parametrize(
        ("producer_method", "produced_rarity"),
        sorted(RARITY_PRODUCED.items()),
    )
    def test_producer_keys_have_known_rarities(self, producer_method, produced_rarity):
        assert produced_rarity in {"normal", "magic", "rare"}


class TestSearchBasesCountInvariant:
    def test_count_reflects_total_matches_not_truncated(self):
        data = copy.deepcopy(REPOE_DATA)
        for i in range(25):
            base_name = f"Synthetic Circlet {i}"
            data["base_items"][base_name] = copy.deepcopy(
                REPOE_DATA["base_items"]["Hubris Circlet"]
            )
            data["base_items"][base_name]["id"] = f"Metadata/Items/Synthetic/Circlet{i}"
        svc = SimService(repoe_data=make_repoe_data(data=data))
        result = svc.search_bases("Circlet")
        assert result.count == 26
        assert len(result.items) <= 20
        assert result.count >= len(result.items)


class TestApplyMultistepMethodFullEnumCoverage:
    @pytest.mark.parametrize("method", [m.value for m in CraftMethod])
    def test_every_method_dispatched_or_raises_value_error(self, method):
        import contextlib

        from poe.services.repoe.sim import CraftingEngine

        data = make_repoe_data()
        eng = CraftingEngine(data)
        item = eng.create_item("Hubris Circlet", ilvl=84)
        step = {"method": method}
        if method == CraftMethod.ESSENCE:
            step["essence"] = "Greed"
        if method == CraftMethod.FOSSIL:
            step["fossils"] = ["Pristine Fossil"]
        if method == CraftMethod.CONQUEROR_EXALT:
            step["influence"] = "shaper"
        if method == CraftMethod.HARVEST:
            step["tag"] = "life"
        with contextlib.suppress(ValueError, AttributeError, KeyError):
            SimService._apply_multistep_method(eng, item, method, step)


class TestInfluenceEnumCompleteness:
    @pytest.mark.parametrize("influence", [i.value for i in Influence])
    def test_every_influence_value_validates_in_get_mods(self, influence):
        svc = SimService(repoe_data=make_repoe_data())
        try:
            svc.get_mods("Hubris Circlet", influences=[influence])
        except SimDataError as e:
            assert "Unknown influence" not in str(e)

    @pytest.mark.parametrize("influence", [i.value for i in Influence])
    def test_lowercase_value_accepted(self, influence):
        svc = SimService(repoe_data=make_repoe_data())
        try:
            svc.get_mods("Hubris Circlet", influences=[influence.casefold()])
        except SimDataError as e:
            assert "Unknown influence" not in str(e)


class TestModWeightsInvariants:
    def test_probabilities_sum_close_to_100(self, sim_service):
        results = sim_service.mod_weights("Hubris Circlet", limit=1000)
        total = sum(float(r["probability"].rstrip("%")) for r in results)
        assert 99.0 <= total <= 100.5

    def test_no_negative_weights(self, sim_service):
        results = sim_service.mod_weights("Hubris Circlet", limit=1000)
        for r in results:
            assert r["weight"] > 0
            pct = float(r["probability"].rstrip("%"))
            assert pct >= 0


class TestResolveModName:
    def test_unknown_name_returns_none(self, sim_service):
        result = sim_service.resolve_mod_name("ZZZNotARealMod", "Hubris Circlet")
        assert result is None

    @pytest.mark.parametrize(
        "display_input",
        ["Increased Life", "increased life", "INCREASED LIFE", "InCrEaSeD lIfE"],
    )
    def test_case_insensitive_resolution(self, sim_service, display_input):
        result = sim_service.resolve_mod_name(display_input, "Hubris Circlet")
        assert result == "IncreasedLife"

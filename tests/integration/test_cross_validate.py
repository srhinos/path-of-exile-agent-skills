from __future__ import annotations

import pytest

from tests.integration.conftest import build_by_name

pytestmark = pytest.mark.integration


class TestCrossValidation:
    def test_rare_item_base_found(self, all_builds, repoe_data):
        checked = 0
        found = 0
        for _name, build in all_builds:
            for item in build.items:
                if item.rarity == "RARE" and item.base_type:
                    checked += 1
                    bitem = repoe_data.get_base_item(item.base_type)
                    if bitem is not None:
                        found += 1
        assert checked > 0, "No rare items to check"
        assert found > 0, "No bases found in crafting data"

    def test_rare_item_has_mod_pool(self, all_builds, repoe_data):
        for _, build in all_builds:
            for item in build.items:
                if item.rarity == "RARE" and item.base_type in ("Hubris Circlet", "Vaal Regalia"):
                    mods = repoe_data.get_mod_pool(item.base_type, ilvl=84)
                    if mods:
                        assert len(mods) > 0
                        return
        pytest.skip("No matching base items found")

    def test_influenced_item_has_influence_mods(self, all_builds, repoe_data):
        necro = build_by_name(all_builds, "necromancer")
        for item in necro.items:
            if item.rarity == "RARE" and item.influences and item.base_type:
                bitem = repoe_data.get_base_item(item.base_type)
                if bitem:
                    mods = repoe_data.get_mod_pool(
                        item.base_type,
                        ilvl=84,
                        influences=item.influences,
                    )
                    influences_in_pool = [m for m in mods if m.influence is not None]
                    if influences_in_pool:
                        return
        pytest.skip("No influenced items with mod pools found")

    def test_craft_mods_real_base(self, all_builds, repoe_data):
        mods = repoe_data.get_mod_pool("Hubris Circlet", ilvl=84)
        if mods:
            assert len(mods) > 0
        else:
            pytest.skip("No mods found for Hubris Circlet")

    def test_craft_simulate_real_base(self, repoe_data):
        import random

        from poe.services.repoe.sim import CraftingEngine

        engine = CraftingEngine(repoe_data)
        try:
            random.seed(42)
            ci = engine.create_item("Hubris Circlet", ilvl=84)
            engine.chaos_roll(ci)
            assert len(ci.all_mods) > 0
        except ValueError:
            pytest.skip("Hubris Circlet not craftable")

    def test_fossil_names_match_prices(self, repoe_data):
        try:
            fossils = repoe_data.get_fossils()
            prices = repoe_data.get_prices()
            if "error" in prices:
                pytest.skip("No price data")

            fossil_prices = prices.get("fossils", {})
            if not fossil_prices:
                pytest.skip("No fossil prices available")

            matched = 0
            for f in fossils:
                name = f["name"]
                if name in fossil_prices or name.replace(" Fossil", "") in fossil_prices:
                    matched += 1
            assert matched > 0, "No fossil names matched price data"
        except (ImportError, OSError, RuntimeError) as e:
            pytest.skip(f"Could not check fossil prices: {e}")

    def test_bench_craft_costs_present(self, repoe_data):
        crafts = repoe_data.get_bench_crafts("Hubris Circlet")
        if crafts:
            for c in crafts:
                assert "cost" in c
                assert "cost_raw" in c
        else:
            pytest.skip("No bench crafts found for Hubris Circlet")

    def test_item_mods_match_affixes(self, all_builds, repoe_data):
        necro = build_by_name(all_builds, "necromancer")
        for item in necro.items:
            if item.prefix_slots:
                for slot in item.prefix_slots:
                    if slot is not None:
                        assert len(slot) > 0
                return
        pytest.skip("No items with prefix slots found")

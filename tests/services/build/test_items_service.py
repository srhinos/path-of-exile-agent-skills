from __future__ import annotations

import pytest

from poe.exceptions import BuildValidationError, SlotError
from poe.services.build.build_service import BuildService
from poe.services.build.items_service import (
    ItemsService,
    _find_active_item_set,
    _find_item_in_slot,
    _slot_matches_type,
)


class TestItemsService:
    def test_list_items(self, builds_dir):
        svc = ItemsService()
        result = svc.list_items("TestBuild")
        assert isinstance(result, list)

    def test_list_sets(self, builds_dir):
        svc = ItemsService()
        result = svc.list_sets("TestBuild")
        assert result.sets is not None

    def test_add_item(self, build_file):
        svc = ItemsService()
        result = svc.add_item(
            "ignored",
            slot="Ring 1",
            base="Coral Ring",
            file_path=str(build_file),
        )
        assert result.status == "ok"

    def test_remove_item_no_target(self, build_file):
        svc = ItemsService()
        with pytest.raises(BuildValidationError):
            svc.remove_item("ignored", file_path=str(build_file))

    def test_edit_invalid_rarity(self, build_file):
        svc = ItemsService()
        with pytest.raises(BuildValidationError, match="rarity"):
            svc.edit_item(
                "ignored",
                slot="Helmet",
                set_rarity="INVALID",
                file_path=str(build_file),
            )

    def test_search(self, builds_dir):
        svc = ItemsService()
        result = svc.search("TestBuild")
        assert isinstance(result, list)


class TestItemsServiceAdditional:
    def test_remove_by_slot(self, rich_build):
        svc = ItemsService()
        r = svc.remove_item("ignored", slot="Ring 1", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_by_id(self, rich_build):
        svc = ItemsService()
        build_svc = BuildService()
        _, build = build_svc.load("ignored", file_path=str(rich_build))
        item_id = build.items[0].id
        r = svc.remove_item("ignored", item_id=item_id, file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_invalid_id(self, rich_build):
        svc = ItemsService()
        with pytest.raises(SlotError):
            svc.remove_item("ignored", item_id=9999, file_path=str(rich_build))

    def test_edit_item_mods(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            add_explicit=["+50 to Maximum Life"],
            set_name="New Name",
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_active_item_set(self, rich_build):
        svc = ItemsService()
        r = svc.set_active("ignored", "1", file_path=str(rich_build))
        assert r.status == "ok"

    def test_set_active_invalid(self, rich_build):
        svc = ItemsService()
        with pytest.raises(BuildValidationError):
            svc.set_active("ignored", "99", file_path=str(rich_build))

    def test_add_set(self, rich_build):
        svc = ItemsService()
        r = svc.add_set("ignored", file_path=str(rich_build))
        assert r.status == "ok"
        assert hasattr(r, "new_set_id") or "new_set_id" in getattr(r, "model_extra", {})

    def test_remove_set(self, rich_build):
        svc = ItemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        r = svc.remove_set("ignored", "2", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_last_set(self, rich_build):
        svc = ItemsService()
        with pytest.raises(BuildValidationError, match="last"):
            svc.remove_set("ignored", "1", file_path=str(rich_build))

    def test_search_by_slot(self, rich_build):
        svc = ItemsService()
        r = svc.search("ignored", slot="flask", file_path=str(rich_build))
        assert all("Flask" in item.slot for item in r)


class TestItemsHelpers:
    def test_slot_matches_jewel(self):
        assert _slot_matches_type("Jewel 1", "jewel") is True
        assert _slot_matches_type("Ring 1", "jewel") is False

    def test_slot_matches_unknown(self):
        assert _slot_matches_type("Ring 1", "zzz") is False

    def test_find_item_no_set(self, rich_build):
        svc = BuildService()
        _, build = svc.load("ignored", file_path=str(rich_build))
        build.item_sets = []
        assert _find_active_item_set(build) is None
        assert _find_item_in_slot(build, "Ring 1") is None


class TestItemsServiceCoverage:
    def test_remove_by_slot_not_found(self, rich_build):
        svc = ItemsService()
        with pytest.raises(SlotError, match="not found"):
            svc.remove_item(
                "ignored",
                slot="Nonexistent Slot",
                file_path=str(rich_build),
            )

    def test_edit_remove_explicit(self, rich_build):
        svc = ItemsService()
        svc.edit_item(
            "ignored",
            slot="Helmet",
            add_explicit=["+50 to Life"],
            file_path=str(rich_build),
        )
        result = svc.edit_item(
            "ignored",
            slot="Helmet",
            remove_explicit=[0],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_edit_set_all_fields(self, rich_build):
        svc = ItemsService()
        result = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_name="New Name",
            set_base="New Base",
            set_rarity="MAGIC",
            set_quality=20,
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_edit_slot_not_found(self, rich_build):
        svc = ItemsService()
        with pytest.raises(SlotError, match="No item"):
            svc.edit_item("ignored", slot="Nonexistent", file_path=str(rich_build))

    def test_edit_invalid_explicit_index(self, rich_build):
        svc = ItemsService()
        with pytest.raises(BuildValidationError, match="Explicit"):
            svc.edit_item(
                "ignored",
                slot="Helmet",
                remove_explicit=[99],
                file_path=str(rich_build),
            )

    def test_edit_invalid_implicit_index(self, rich_build):
        svc = ItemsService()
        with pytest.raises(BuildValidationError, match="Implicit"):
            svc.edit_item(
                "ignored",
                slot="Helmet",
                remove_implicit=[99],
                file_path=str(rich_build),
            )

    def test_remove_set_active_switches(self, rich_build):
        svc = ItemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        svc.set_active("ignored", "2", file_path=str(rich_build))
        result = svc.remove_set("ignored", "2", file_path=str(rich_build))
        assert result.status == "ok"

    def test_remove_set_not_found(self, rich_build):
        svc = ItemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        with pytest.raises(BuildValidationError, match="not found"):
            svc.remove_set("ignored", "99", file_path=str(rich_build))

    def test_search_by_influence(self, rich_build):
        svc = ItemsService()
        result = svc.search("ignored", influence="Shaper", file_path=str(rich_build))
        assert isinstance(result, list)

    def test_search_by_rarity(self, rich_build):
        svc = ItemsService()
        result = svc.search("ignored", rarity="RARE", file_path=str(rich_build))
        assert isinstance(result, list)

    def test_search_by_mod(self, rich_build):
        svc = ItemsService()
        result = svc.search("ignored", mod="Life", file_path=str(rich_build))
        assert isinstance(result, list)


class TestEditItemExpanded:
    def test_set_sockets(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_sockets="B-B-B-B",
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_influences(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_influences=["Shaper"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_armour(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_armour=500,
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_evasion(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_evasion=300,
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_energy_shield(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_energy_shield=400,
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_multiple_defenses(self, rich_build):
        svc = ItemsService()
        r = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_armour=100,
            set_evasion=200,
            set_energy_shield=300,
            file_path=str(rich_build),
        )
        assert r.status == "ok"


class TestItemsMoveSwap:
    def test_move_item(self, rich_build):
        svc = ItemsService()
        svc.add_item("ignored", slot="Weapon 1", base="Dagger", file_path=str(rich_build))
        r = svc.move_item(
            "ignored",
            from_slot="Weapon 1",
            to_slot="Weapon 2",
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_move_item_not_found(self, rich_build):
        svc = ItemsService()
        with pytest.raises(SlotError):
            svc.move_item(
                "ignored",
                from_slot="Weapon 2",
                to_slot="Weapon 1",
                file_path=str(rich_build),
            )

    def test_swap_items(self, rich_build):
        svc = ItemsService()
        r = svc.swap_items("ignored", slot1="Ring 1", slot2="Ring 2", file_path=str(rich_build))
        assert r.status == "ok"


class TestItemsImport:
    def test_import_item_text(self, rich_build):
        svc = ItemsService()
        text = """Rarity: RARE
Test Crown
Hubris Circlet
--------
+90 to maximum Life
+40% to Cold Resistance"""
        r = svc.import_item_text(
            "ignored",
            slot="Helmet",
            item_text=text,
            file_path=str(rich_build),
        )
        assert r.status == "ok"


class TestItemsCompare:
    def test_compare_items(self, rich_build):
        svc = ItemsService()
        diffs = svc.compare_items("ignored", "Helmet", file_path=str(rich_build))
        assert isinstance(diffs, list)


class TestItemsListExcludesFlasks:
    def test_list_items_excludes_flask_slots(self, builds_dir):
        svc = ItemsService()
        items = svc.list_items("TestBuild")
        flask_slots = {"Flask 1", "Flask 2", "Flask 3", "Flask 4", "Flask 5"}
        for item in items:
            assert item.slot not in flask_slots, f"Flask slot {item.slot} in items list"


class TestSlotMatchesIndividualNames:
    def test_matches_helmet(self):
        assert _slot_matches_type("Helmet", "Helmet")

    def test_matches_helmet_case_insensitive(self):
        assert _slot_matches_type("Helmet", "helmet")

    def test_matches_ring_1(self):
        assert _slot_matches_type("Ring 1", "Ring 1")

    def test_category_still_works(self):
        assert _slot_matches_type("Helmet", "armour")
        assert _slot_matches_type("Ring 1", "jewellery")


class TestItemsServiceAddItemEnumCoverage:
    @pytest.mark.parametrize(
        "slot",
        [
            "Helmet",
            "Body Armour",
            "Gloves",
            "Boots",
            "Amulet",
            "Ring 1",
            "Ring 2",
            "Belt",
        ],
    )
    def test_add_item_each_gear_slot(self, rich_build, slot):
        svc = ItemsService()
        result = svc.add_item(
            "ignored",
            slot=slot,
            base="Coral Ring",
            file_path=str(rich_build),
        )
        assert result.status == "ok"
        assert result.slot == slot

    @pytest.mark.parametrize("rarity", ["NORMAL", "MAGIC", "RARE", "UNIQUE", "RELIC"])
    def test_add_item_each_rarity_via_default(self, rich_build, rarity):
        svc = ItemsService()
        result = svc.add_item(
            "ignored",
            slot="Ring 1",
            base="Coral Ring",
            rarity=rarity,
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_add_item_unknown_slot_raises(self, rich_build):
        svc = ItemsService()
        with pytest.raises(SlotError, match="Unknown slot"):
            svc.add_item(
                "ignored",
                slot="ZZZ Garbage Slot",
                base="Coral Ring",
                file_path=str(rich_build),
            )


class TestEditItemRarityCoverage:
    @pytest.mark.parametrize("rarity", ["NORMAL", "MAGIC", "RARE", "UNIQUE", "RELIC"])
    def test_edit_set_rarity_valid(self, rich_build, rarity):
        svc = ItemsService()
        result = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_rarity=rarity,
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    @pytest.mark.parametrize(
        "bad",
        ["normal", "magic", "rare", "unique", "RAREE", "Mythic", "EPIC"],
    )
    def test_edit_set_rarity_invalid(self, rich_build, bad):
        svc = ItemsService()
        with pytest.raises(BuildValidationError, match=r"rarity|Invalid"):
            svc.edit_item(
                "ignored",
                slot="Helmet",
                set_rarity=bad,
                file_path=str(rich_build),
            )

    @pytest.mark.xfail(
        strict=True,
        reason="empty set_rarity skipped by truthiness check; should be rejected explicitly",
    )
    def test_edit_set_rarity_empty_string_should_fail(self, rich_build):
        svc = ItemsService()
        with pytest.raises(BuildValidationError):
            svc.edit_item(
                "ignored",
                slot="Helmet",
                set_rarity="",
                file_path=str(rich_build),
            )


class TestEditItemInfluenceCoverage:
    @pytest.mark.parametrize(
        "influence",
        [
            "Shaper",
            "Elder",
            "Crusader",
            "Hunter",
            "Redeemer",
            "Warlord",
            "Searing Exarch",
            "Eater of Worlds",
        ],
    )
    def test_each_canonical_influence_accepted(self, rich_build, influence):
        svc = ItemsService()
        result = svc.edit_item(
            "ignored",
            slot="Helmet",
            set_influences=[influence],
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_set_influences_replaces_existing(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        svc.edit_item(
            "ignored",
            slot="Helmet",
            set_influences=["Shaper"],
            file_path=str(rich_build),
        )
        svc.edit_item(
            "ignored",
            slot="Helmet",
            set_influences=["Elder"],
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        helmet = next(i for i in build.items if i.base_type == "Hubris Circlet")
        assert helmet.influences == ["Elder"]

    def test_set_influences_to_empty(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        svc.edit_item(
            "ignored",
            slot="Helmet",
            set_influences=["Shaper", "Elder"],
            file_path=str(rich_build),
        )
        svc.edit_item(
            "ignored",
            slot="Helmet",
            set_influences=[],
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        helmet = next(i for i in build.items if i.base_type == "Hubris Circlet")
        assert helmet.influences == []


class TestItemsAddItemInvariants:
    def test_unique_id_assigned(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        _, before = BuildService().load("ignored", file_path=str(rich_build))
        before_ids = {i.id for i in before.items}
        result = svc.add_item(
            "ignored",
            slot="Gloves",
            base="Sorcerer Gloves",
            file_path=str(rich_build),
        )
        assert result.item_id not in before_ids
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        assert result.item_id in {i.id for i in after.items}

    def test_add_replaces_slot_in_active_set_only(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        svc.add_item(
            "ignored",
            slot="Ring 1",
            base="Coral Ring",
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        active = next((s for s in build.item_sets if s.id == build.active_item_set), None)
        if active is None:
            active = build.item_sets[0]
        ring1_slots = [s for s in active.slots if s.name == "Ring 1"]
        assert len(ring1_slots) == 1


class TestItemsRemoveInvariants:
    def test_remove_clears_item_and_all_slot_refs(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        result = svc.remove_item("ignored", slot="Helmet", file_path=str(rich_build))
        assert result.status == "ok"
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert not any(i.id == result.removed_id for i in build.items)
        for iset in build.item_sets:
            assert not any(s.item_id == result.removed_id for s in iset.slots)


class TestItemsAddSetInvariant:
    def test_added_set_has_unique_id(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        result = svc.add_set("ignored", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        ids = [s.id for s in build.item_sets]
        assert len(ids) == len(set(ids))
        assert result.new_set_id in ids

    def test_set_active_propagates(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        svc.add_set("ignored", file_path=str(rich_build))
        svc.set_active("ignored", "2", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert build.active_item_set == "2"


class TestItemSearchCaseInsensitive:
    def test_search_rarity_case_insensitive(self, rich_build):
        svc = ItemsService()
        upper = svc.search("ignored", rarity="RARE", file_path=str(rich_build))
        lower = svc.search("ignored", rarity="rare", file_path=str(rich_build))
        mixed = svc.search("ignored", rarity="Rare", file_path=str(rich_build))
        assert {i.slot for i in upper} == {i.slot for i in lower} == {i.slot for i in mixed}


class TestItemPydanticInvariants:
    def test_item_rarity_accepts_arbitrary_string(self):
        from poe.models.build.items import Item

        item = Item(id=1, text="", rarity="HEROIC")
        assert item.rarity == "HEROIC"

    def test_item_influences_accepts_arbitrary_strings(self):
        from poe.models.build.items import Item

        item = Item(id=1, text="", influences=["Bogus", "Fake"])
        assert item.influences == ["Bogus", "Fake"]

    @pytest.mark.xfail(strict=True, reason="Item.rarity should reject invalid rarities")
    def test_item_rarity_rejects_invalid(self):
        from pydantic import ValidationError

        from poe.models.build.items import Item

        with pytest.raises(ValidationError):
            Item(id=1, text="", rarity="HEROIC")

    @pytest.mark.xfail(
        strict=True, reason="Item.influences should reject unknown influence strings"
    )
    def test_item_influences_rejects_unknown(self):
        from pydantic import ValidationError

        from poe.models.build.items import Item

        with pytest.raises(ValidationError):
            Item(id=1, text="", influences=["NotAnInfluence"])


class TestSwapItemsInvariants:
    def test_swap_round_trip(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = ItemsService()
        _, before = BuildService().load("ignored", file_path=str(rich_build))
        active_before = next(
            (s for s in before.item_sets if s.id == before.active_item_set),
            before.item_sets[0],
        )
        ring1_id_before = next(s.item_id for s in active_before.slots if s.name == "Ring 1")
        ring2_id_before = next(s.item_id for s in active_before.slots if s.name == "Ring 2")
        svc.swap_items("ignored", slot1="Ring 1", slot2="Ring 2", file_path=str(rich_build))
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        active_after = next(
            (s for s in after.item_sets if s.id == after.active_item_set),
            after.item_sets[0],
        )
        ring1_id_after = next(s.item_id for s in active_after.slots if s.name == "Ring 1")
        ring2_id_after = next(s.item_id for s in active_after.slots if s.name == "Ring 2")
        assert ring1_id_after == ring2_id_before
        assert ring2_id_after == ring1_id_before


class TestEditItemNotFound:
    def test_edit_no_item_in_slot(self, rich_build):
        svc = ItemsService()
        with pytest.raises(SlotError, match="No item"):
            svc.edit_item("ignored", slot="Body Armour", file_path=str(rich_build))

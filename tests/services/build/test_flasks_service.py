from __future__ import annotations

import pytest

from poe.exceptions import BuildValidationError, SlotError
from poe.services.build.flasks_service import FlasksService


class TestFlasksService:
    def test_list_flasks(self, builds_dir):
        svc = FlasksService()
        result = svc.list_flasks("TestBuild")
        assert isinstance(result, list)


class TestFlasksCRUD:
    def test_add_flask(self, rich_build):
        svc = FlasksService()
        r = svc.add_flask("ignored", base="Diamond Flask", file_path=str(rich_build))
        assert r.status == "ok"
        assert r.slot.startswith("Flask")

    def test_add_flask_specific_slot(self, rich_build):
        svc = FlasksService()
        r = svc.add_flask(
            "ignored",
            base="Quicksilver Flask",
            slot="Flask 3",
            file_path=str(rich_build),
        )
        assert r.slot == "Flask 3"

    def test_add_flask_invalid_slot(self, rich_build):
        svc = FlasksService()
        with pytest.raises(SlotError, match="Invalid flask slot"):
            svc.add_flask("ignored", base="Flask", slot="Ring 1", file_path=str(rich_build))

    def test_remove_flask(self, rich_build):
        svc = FlasksService()
        svc.add_flask("ignored", base="Diamond Flask", slot="Flask 2", file_path=str(rich_build))
        r = svc.remove_flask("ignored", slot="Flask 2", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_flask_not_found(self, rich_build):
        svc = FlasksService()
        with pytest.raises(SlotError, match="No flask"):
            svc.remove_flask("ignored", slot="Flask 5", file_path=str(rich_build))

    def test_remove_flask_invalid_slot(self, rich_build):
        svc = FlasksService()
        with pytest.raises(SlotError, match="Invalid"):
            svc.remove_flask("ignored", slot="Ring 1", file_path=str(rich_build))

    def test_edit_flask(self, rich_build):
        svc = FlasksService()
        r = svc.edit_flask(
            "ignored",
            slot="Flask 1",
            set_name="Better Flask",
            set_quality=20,
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_edit_flask_not_found(self, rich_build):
        svc = FlasksService()
        with pytest.raises(SlotError):
            svc.edit_flask("ignored", slot="Flask 5", file_path=str(rich_build))

    def test_edit_flask_add_explicit(self, rich_build):
        svc = FlasksService()
        r = svc.edit_flask(
            "ignored",
            slot="Flask 1",
            add_explicit=["Increased Duration"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_reorder_flasks(self, rich_build):
        svc = FlasksService()
        svc.add_flask("ignored", base="Diamond Flask", slot="Flask 2", file_path=str(rich_build))
        r = svc.reorder_flasks(
            "ignored",
            order=["Flask 2", "Flask 1"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_reorder_flasks_invalid_slot(self, rich_build):
        svc = FlasksService()
        with pytest.raises(SlotError):
            svc.reorder_flasks("ignored", order=["Ring 1"], file_path=str(rich_build))

    def test_reorder_flasks_duplicate(self, rich_build):
        svc = FlasksService()
        with pytest.raises(BuildValidationError, match="Duplicate"):
            svc.reorder_flasks(
                "ignored",
                order=["Flask 1", "Flask 1"],
                file_path=str(rich_build),
            )


class TestFlasksSlotEnumCoverage:
    @pytest.mark.parametrize(
        "slot",
        ["Flask 1", "Flask 2", "Flask 3", "Flask 4", "Flask 5"],
    )
    def test_each_flask_slot_accepted(self, rich_build, slot):
        svc = FlasksService()
        result = svc.add_flask(
            "ignored",
            base="Diamond Flask",
            slot=slot,
            file_path=str(rich_build),
        )
        assert result.slot == slot

    @pytest.mark.parametrize(
        "bad_slot",
        ["Flask 0", "Flask 6", "Ring 1", "Helmet", "Flask1"],
    )
    def test_invalid_slot_rejected(self, rich_build, bad_slot):
        from poe.exceptions import SlotError

        svc = FlasksService()
        with pytest.raises(SlotError, match="Invalid"):
            svc.add_flask(
                "ignored",
                base="Diamond Flask",
                slot=bad_slot,
                file_path=str(rich_build),
            )

    @pytest.mark.parametrize("good_slot", ["flask 1", "FLASK 2", "Flask 3"])
    def test_slot_case_insensitive(self, rich_build, good_slot):
        """User-typed casing should normalize to canonical 'Flask N'."""
        svc = FlasksService()
        result = svc.add_flask(
            "ignored",
            base="Diamond Flask",
            slot=good_slot,
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_empty_slot_should_be_rejected(self, rich_build):
        from poe.exceptions import SlotError

        svc = FlasksService()
        with pytest.raises(SlotError):
            svc.add_flask(
                "ignored",
                base="Diamond Flask",
                slot="",
                file_path=str(rich_build),
            )

    @pytest.mark.parametrize(
        "bad_slot",
        ["Flask 6", "Ring 1", "Helmet"],
    )
    def test_remove_invalid_slot(self, rich_build, bad_slot):
        from poe.exceptions import SlotError

        svc = FlasksService()
        with pytest.raises(SlotError, match="Invalid"):
            svc.remove_flask("ignored", slot=bad_slot, file_path=str(rich_build))

    @pytest.mark.parametrize(
        "bad_slot",
        ["Flask 6", "Ring 1", "Helmet"],
    )
    def test_edit_invalid_slot(self, rich_build, bad_slot):
        from poe.exceptions import SlotError

        svc = FlasksService()
        with pytest.raises(SlotError, match="Invalid"):
            svc.edit_flask("ignored", slot=bad_slot, file_path=str(rich_build))


class TestFlasksCapacityInvariant:
    def test_cannot_exceed_5_flasks(self, rich_build):
        svc = FlasksService()
        for i in range(2, 6):
            svc.add_flask(
                "ignored",
                base="Diamond Flask",
                slot=f"Flask {i}",
                file_path=str(rich_build),
            )
        with pytest.raises(BuildValidationError, match="occupied"):
            svc.add_flask(
                "ignored",
                base="Diamond Flask",
                file_path=str(rich_build),
            )


class TestFlasksAutoSlotPicksFirstFree:
    def test_auto_slot_picks_lowest_unoccupied(self, rich_build):
        svc = FlasksService()
        result = svc.add_flask(
            "ignored",
            base="Diamond Flask",
            file_path=str(rich_build),
        )
        assert result.slot == "Flask 2"


class TestFlasksRemoveInvariants:
    def test_remove_clears_item_and_slot(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = FlasksService()
        svc.add_flask(
            "ignored",
            base="Diamond Flask",
            slot="Flask 2",
            file_path=str(rich_build),
        )
        result = svc.remove_flask("ignored", slot="Flask 2", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert not any(i.id == result.removed_id for i in build.items)
        for iset in build.item_sets:
            assert not any(s.name == "Flask 2" for s in iset.slots)


class TestFlasksReorderInvariants:
    def test_reorder_preserves_item_count(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = FlasksService()
        svc.add_flask("ignored", base="Diamond Flask", slot="Flask 2", file_path=str(rich_build))
        _, before = BuildService().load("ignored", file_path=str(rich_build))
        before_count = len(before.items)
        svc.reorder_flasks(
            "ignored",
            order=["Flask 2", "Flask 1"],
            file_path=str(rich_build),
        )
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        assert len(after.items) == before_count

    def test_reorder_adjacent_swap(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = FlasksService()
        svc.add_flask(
            "ignored",
            base="Quicksilver Flask",
            slot="Flask 2",
            file_path=str(rich_build),
        )
        _, before = BuildService().load("ignored", file_path=str(rich_build))
        active_before = next(
            (s for s in before.item_sets if s.id == before.active_item_set),
            before.item_sets[0],
        )
        f1_before = next(s.item_id for s in active_before.slots if s.name == "Flask 1")
        f2_before = next(s.item_id for s in active_before.slots if s.name == "Flask 2")
        svc.reorder_flasks(
            "ignored",
            order=["Flask 2", "Flask 1"],
            file_path=str(rich_build),
        )
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        active_after = next(
            (s for s in after.item_sets if s.id == after.active_item_set),
            after.item_sets[0],
        )
        f1_after = next(s.item_id for s in active_after.slots if s.name == "Flask 1")
        f2_after = next(s.item_id for s in active_after.slots if s.name == "Flask 2")
        assert f1_after == f2_before
        assert f2_after == f1_before

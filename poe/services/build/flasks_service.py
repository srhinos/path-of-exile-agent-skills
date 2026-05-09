from __future__ import annotations

from poe.exceptions import BuildValidationError, SlotError
from poe.models.build.build import MutationResult
from poe.models.build.items import EquippedItem, Item, ItemMod, ItemSlot
from poe.services.build.build_service import BuildService
from poe.services.build.constants import FLASK_SLOT_NAMES, STALE_STATS_WARNING


class FlasksService:
    """Owns flask business logic."""

    def __init__(self, build_svc: BuildService | None = None) -> None:
        self._build = build_svc or BuildService()

    def list_flasks(self, name: str, *, file_path: str | None = None) -> list[EquippedItem]:
        _, build_obj = self._build.load(name, file_path)
        equipped = build_obj.get_equipped_items()
        return [
            EquippedItem(slot=slot_name, **item.model_dump())
            for slot_name, item in equipped
            if slot_name.startswith("Flask")
        ]

    def add_flask(
        self,
        name: str,
        *,
        base: str,
        flask_name: str = "New Flask",
        rarity: str = "MAGIC",
        quality: int = 0,
        explicits: list[str] | None = None,
        slot: str | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        equipped = build_obj.get_equipped_items()
        occupied = {s for s, _ in equipped if s.startswith("Flask")}
        if slot is not None:
            if slot not in FLASK_SLOT_NAMES:
                raise SlotError(f"Invalid flask slot: {slot!r}")
            target_slot = slot
        else:
            target_slot = next((s for s in FLASK_SLOT_NAMES if s not in occupied), None)
            if not target_slot:
                raise BuildValidationError("All 5 flask slots are occupied")
        next_id = max((i.id for i in build_obj.items), default=0) + 1
        item = Item(
            id=next_id,
            text="",
            rarity=rarity,
            name=flask_name,
            base_type=base,
            quality=quality,
            explicits=[ItemMod(text=m) for m in (explicits or [])],
        )
        build_obj.items.append(item)
        active_set = build_obj.item_sets[0] if build_obj.item_sets else None
        for iset in build_obj.item_sets:
            if iset.id == build_obj.active_item_set:
                active_set = iset
                break
        if active_set:
            active_set.slots = [s for s in active_set.slots if s.name != target_slot]
            active_set.slots.append(ItemSlot(name=target_slot, item_id=next_id))
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=next_id,
            slot=target_slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_flask(
        self,
        name: str,
        *,
        slot: str,
        file_path: str | None = None,
    ) -> MutationResult:
        if slot not in FLASK_SLOT_NAMES:
            raise SlotError(f"Invalid flask slot: {slot!r}")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        removed_id = None
        for iset in build_obj.item_sets:
            for item_slot in iset.slots:
                if item_slot.name == slot:
                    removed_id = item_slot.item_id
                    break
        if removed_id is None:
            raise SlotError(f"No flask in slot {slot!r}")
        build_obj.items = [i for i in build_obj.items if i.id != removed_id]
        for iset in build_obj.item_sets:
            iset.slots = [s for s in iset.slots if s.name != slot]
        self._build.save(build_obj, path)
        return MutationResult(
            removed_id=removed_id,
            slot=slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def edit_flask(
        self,
        name: str,
        *,
        slot: str,
        set_base: str | None = None,
        set_name: str | None = None,
        set_quality: int | None = None,
        add_explicit: list[str] | None = None,
        remove_explicit: list[int] | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        if slot not in FLASK_SLOT_NAMES:
            raise SlotError(f"Invalid flask slot: {slot!r}")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        item_map = {i.id: i for i in build_obj.items}
        target = None
        for iset in build_obj.item_sets:
            if iset.id == build_obj.active_item_set:
                for item_slot in iset.slots:
                    if item_slot.name == slot and item_slot.item_id in item_map:
                        target = item_map[item_slot.item_id]
                        break
        if target is None:
            raise SlotError(f"No flask in slot {slot!r}")
        if set_base is not None:
            target.base_type = set_base
        if set_name is not None:
            target.name = set_name
        if set_quality is not None:
            target.quality = set_quality
        for idx in sorted(remove_explicit or [], reverse=True):
            if 0 <= idx < len(target.explicits):
                target.explicits.pop(idx)
        for mod_text in add_explicit or []:
            target.explicits.append(ItemMod(text=mod_text))
        target.text = ""
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=target.id,
            slot=slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def reorder_flasks(
        self,
        name: str,
        *,
        order: list[str],
        file_path: str | None = None,
    ) -> MutationResult:
        if len(order) != len(set(order)):
            raise BuildValidationError("Duplicate flask slots in order")
        for s in order:
            if s not in FLASK_SLOT_NAMES:
                raise SlotError(f"Invalid flask slot: {s!r}")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        active_set = None
        for iset in build_obj.item_sets:
            if iset.id == build_obj.active_item_set:
                active_set = iset
                break
        if not active_set:
            raise BuildValidationError("No active item set")
        flask_slots = {s.name: s.item_id for s in active_set.slots if s.name in FLASK_SLOT_NAMES}
        non_flask_slots = [s for s in active_set.slots if s.name not in FLASK_SLOT_NAMES]
        source_ids = [flask_slots.get(s) for s in order if s in flask_slots]
        new_flask_slots = []
        for i, item_id in enumerate(source_ids):
            if item_id is not None:
                new_flask_slots.append(ItemSlot(name=FLASK_SLOT_NAMES[i], item_id=item_id))
        active_set.slots = non_flask_slots + new_flask_slots
        self._build.save(build_obj, path)
        return MutationResult(
            order=[s.name for s in new_flask_slots],
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

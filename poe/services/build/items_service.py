from __future__ import annotations

from typing import TYPE_CHECKING

from poe.exceptions import BuildValidationError, SlotError
from poe.models.build.build import MutationResult
from poe.models.build.items import (
    _INFLUENCE_BY_CASEFOLD,
    _RARITY_BY_CASEFOLD,
    VALID_RARITIES,
    EquippedItem,
    Item,
    ItemDiff,
    ItemMod,
    ItemSet,
    ItemSetList,
    ItemSetSummary,
    ItemSlot,
    filter_to_active_variant,
)
from poe.services.build.build_service import BuildService
from poe.services.build.constants import SLOT_TYPE_MAP, STALE_STATS_WARNING
from poe.services.build.xml.slots import normalize_slot

if TYPE_CHECKING:
    from poe.models.build.build import BuildDocument


_ITEM_TEXT_NAME_LINE = 1
_ITEM_TEXT_BASE_LINE = 2
_ITEM_TEXT_SKIP_PREFIXES = ("Rarity:", "--------")


def _parse_item_text(text: str) -> dict:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    rarity = "RARE"
    item_name = ""
    base_type = ""
    explicits: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("Rarity:"):
            rarity = line.split(":", 1)[1].strip().upper()
        elif i == _ITEM_TEXT_NAME_LINE and not line.startswith(("{", "Rarity")):
            item_name = line
        elif i == _ITEM_TEXT_BASE_LINE and not line.startswith(("{", "Rarity")):
            base_type = line
        elif i > _ITEM_TEXT_BASE_LINE and not any(
            line.startswith(p) for p in _ITEM_TEXT_SKIP_PREFIXES
        ):
            explicits.append(line)
    return {"rarity": rarity, "name": item_name, "base_type": base_type, "explicits": explicits}


def _slot_matches_type(slot_name: str, slot_type: str) -> bool:
    canonical = normalize_slot(slot_type)
    if canonical and slot_name == canonical:
        return True
    normalized = slot_type.casefold()
    if slot_name.casefold() == normalized:
        return True
    if normalized == "jewel":
        return slot_name.startswith("Jewel")
    mapped = SLOT_TYPE_MAP.get(normalized)
    return slot_name in mapped if mapped else False


def _find_active_item_set(build_obj: BuildDocument) -> ItemSet | None:
    for item_set in build_obj.item_sets:
        if item_set.id == build_obj.active_item_set:
            return item_set
    return build_obj.item_sets[0] if build_obj.item_sets else None


def _find_item_in_slot(build_obj: BuildDocument, slot: str) -> Item | None:
    active_set = _find_active_item_set(build_obj)
    if not active_set:
        return None
    canonical = normalize_slot(slot)
    if not canonical:
        return None
    item_map = {item.id: item for item in build_obj.items}
    for item_slot in active_set.slots:
        if item_slot.name == canonical and item_slot.item_id in item_map:
            return item_map[item_slot.item_id]
    return None


class ItemsService:
    """Owns item business logic."""

    def __init__(self, build_svc: BuildService | None = None) -> None:
        self._build = build_svc or BuildService()

    def list_sets(self, name: str) -> ItemSetList:
        _, build_obj = self._build.load(name)
        return ItemSetList(
            active_item_set=build_obj.active_item_set,
            sets=[
                ItemSetSummary(
                    id=s.id,
                    slot_count=len(s.slots),
                    active=s.id == build_obj.active_item_set,
                )
                for s in build_obj.item_sets
            ],
        )

    def list_items(
        self, name: str, *, item_set: str | None = None, file_path: str | None = None
    ) -> list[EquippedItem]:
        _, build_obj = self._build.load(name, file_path)
        equipped = build_obj.get_equipped_items(item_set_id=item_set)
        flask_slots = set(SLOT_TYPE_MAP["flask"])
        # Filter multi-variant items to the active variant for display.
        # Parser preserves all variants for round-trip safety; downstream
        # consumers (open-slot counts, mod listings) expect only the
        # active-variant mods.
        return [
            EquippedItem(slot=slot_name, **filter_to_active_variant(item).model_dump())
            for slot_name, item in equipped
            if slot_name not in flask_slots
        ]

    def add_item(
        self,
        name: str,
        *,
        slot: str,
        base: str,
        rarity: str = "RARE",
        item_name: str = "New Item",
        armour: int = 0,
        evasion: int = 0,
        energy_shield: int = 0,
        quality: int = 0,
        sockets: str = "",
        level_req: int = 0,
        influences: list[str] | None = None,
        implicits: list[str] | None = None,
        explicits: list[str] | None = None,
        crafted_mods: list[str] | None = None,
        fractured_mods: list[str] | None = None,
        synthesised: bool = False,
        file_path: str | None = None,
    ) -> dict:
        canonical_slot = normalize_slot(slot)
        if not canonical_slot:
            raise SlotError(f"Unknown slot: {slot!r}")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        next_id = max((i.id for i in build_obj.items), default=0) + 1
        item = Item(
            id=next_id,
            text="",
            rarity=rarity,
            name=item_name,
            base_type=base,
            influences=list(influences or []),
            is_synthesised=synthesised,
            armour=armour,
            evasion=evasion,
            energy_shield=energy_shield,
            quality=quality,
            sockets=sockets,
            level_req=level_req,
            implicits=[ItemMod(text=m) for m in (implicits or [])],
            explicits=[ItemMod(text=m) for m in (explicits or [])]
            + [ItemMod(text=m, is_fractured=True) for m in (fractured_mods or [])]
            + [ItemMod(text=m, is_crafted=True) for m in (crafted_mods or [])],
        )
        build_obj.items.append(item)
        if build_obj.item_sets:
            target_set = _find_active_item_set(build_obj) or build_obj.item_sets[0]
            target_set.slots = [s for s in target_set.slots if s.name != canonical_slot]
            target_set.slots.append(ItemSlot(name=canonical_slot, item_id=next_id))
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=next_id,
            slot=canonical_slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_item(
        self,
        name: str,
        *,
        slot: str | None = None,
        item_id: int | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        if not slot and item_id is None:
            raise BuildValidationError("Specify slot or item_id")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        removed_id = None
        if item_id is not None:
            if not any(i.id == item_id for i in build_obj.items):
                raise SlotError(f"No item with id {item_id}")
            removed_id = item_id
        elif slot:
            canonical_slot = normalize_slot(slot)
            active_set = _find_active_item_set(build_obj)
            if active_set and canonical_slot:
                for item_slot in active_set.slots:
                    if item_slot.name == canonical_slot:
                        removed_id = item_slot.item_id
                        break
        if removed_id is None:
            raise SlotError("Item not found")
        build_obj.items = [i for i in build_obj.items if i.id != removed_id]
        for item_set in build_obj.item_sets:
            item_set.slots = [s for s in item_set.slots if s.item_id != removed_id]
        self._build.save(build_obj, path)
        return MutationResult(
            removed_id=removed_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def edit_item(
        self,
        name: str,
        *,
        slot: str,
        add_explicit: list[str] | None = None,
        remove_explicit: list[int] | None = None,
        add_implicit: list[str] | None = None,
        remove_implicit: list[int] | None = None,
        set_name: str | None = None,
        set_base: str | None = None,
        set_rarity: str | None = None,
        set_quality: int | None = None,
        set_sockets: str | None = None,
        set_influences: list[str] | None = None,
        set_armour: int | None = None,
        set_evasion: int | None = None,
        set_energy_shield: int | None = None,
        file_path: str | None = None,
    ) -> dict:
        add_explicit = add_explicit or []
        remove_explicit = remove_explicit or []
        add_implicit = add_implicit or []
        remove_implicit = remove_implicit or []
        if set_rarity is not None:
            normalized = _RARITY_BY_CASEFOLD.get(set_rarity.casefold(), set_rarity)
            if normalized not in VALID_RARITIES:
                raise BuildValidationError(
                    f"Invalid rarity: {set_rarity!r}. Must be one of {sorted(VALID_RARITIES)}"
                )
            set_rarity = normalized
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        target_item = _find_item_in_slot(build_obj, slot)
        if target_item is None:
            raise SlotError(f"No item found in slot {slot!r} in the active item set")
        for idx in remove_explicit:
            if idx < 0 or idx >= len(target_item.explicits):
                raise BuildValidationError(
                    f"Explicit mod index {idx} out of range (0-{len(target_item.explicits) - 1})"
                )
        for idx in remove_implicit:
            if idx < 0 or idx >= len(target_item.implicits):
                raise BuildValidationError(
                    f"Implicit mod index {idx} out of range (0-{len(target_item.implicits) - 1})"
                )
        field_updates: dict = {
            "name": set_name,
            "base_type": set_base,
            "rarity": set_rarity,
            "quality": set_quality,
            "sockets": set_sockets,
            "armour": set_armour,
            "evasion": set_evasion,
            "energy_shield": set_energy_shield,
        }
        for field, value in field_updates.items():
            if value is not None:
                setattr(target_item, field, value)
        if set_influences is not None:
            target_item.influences = list(set_influences)
        for idx in sorted(remove_explicit, reverse=True):
            target_item.explicits.pop(idx)
        for idx in sorted(remove_implicit, reverse=True):
            target_item.implicits.pop(idx)
        for mod_text in add_explicit:
            target_item.explicits.append(ItemMod(text=mod_text))
        for mod_text in add_implicit:
            target_item.implicits.append(ItemMod(text=mod_text))
        target_item.text = ""
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=target_item.id,
            slot=slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def set_active(self, name: str, item_set: str, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if not any(s.id == item_set for s in build_obj.item_sets):
            raise BuildValidationError(f"Item set {item_set} not found")
        build_obj.active_item_set = item_set
        self._build.save(build_obj, path)
        return MutationResult(
            active_item_set=item_set,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def add_set(self, name: str, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        max_id = max((int(s.id) for s in build_obj.item_sets), default=0)
        new_id = str(max_id + 1)
        build_obj.item_sets.append(ItemSet(id=new_id))
        self._build.save(build_obj, path)
        return MutationResult(
            new_set_id=new_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_set(self, name: str, item_set: str, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if len(build_obj.item_sets) <= 1:
            raise BuildValidationError("Cannot remove the last remaining item set")
        if not any(s.id == item_set for s in build_obj.item_sets):
            raise BuildValidationError(f"Item set {item_set} not found")
        build_obj.item_sets = [s for s in build_obj.item_sets if s.id != item_set]
        if build_obj.active_item_set == item_set:
            build_obj.active_item_set = build_obj.item_sets[0].id
        self._build.save(build_obj, path)
        return MutationResult(
            removed_set_id=item_set,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def search(
        self,
        name: str,
        *,
        mod: str | None = None,
        slot: str | None = None,
        influence: str | None = None,
        rarity: str | None = None,
        file_path: str | None = None,
    ) -> list[EquippedItem]:
        # Validate filters BEFORE loading the build so a typo'd --rarity or
        # --influence raises a clear error instead of silently returning
        # an empty list.
        normalized_influence: str | None = None
        if influence:
            normalized_influence = _INFLUENCE_BY_CASEFOLD.get(influence.casefold())
            if normalized_influence is None:
                raise BuildValidationError(
                    f"Unknown influence: {influence!r}. "
                    f"Valid: {sorted(_INFLUENCE_BY_CASEFOLD.values())}"
                )
        normalized_rarity: str | None = None
        if rarity:
            normalized_rarity = _RARITY_BY_CASEFOLD.get(rarity.casefold())
            if normalized_rarity is None:
                raise BuildValidationError(
                    f"Unknown rarity: {rarity!r}. "
                    f"Valid: {sorted(_RARITY_BY_CASEFOLD.values())}"
                )

        _, build_obj = self._build.load(name, file_path)
        equipped = build_obj.get_equipped_items()
        flask_slots = set(SLOT_TYPE_MAP["flask"])
        result = []
        for slot_name, item in equipped:
            if slot_name in flask_slots:
                continue
            if slot and not _slot_matches_type(slot_name, slot):
                continue
            if normalized_influence and normalized_influence not in item.influences:
                continue
            if normalized_rarity and item.rarity != normalized_rarity:
                continue
            if mod:
                mod_lower = mod.casefold()
                all_mods = [m.text.casefold() for m in item.implicits] + [
                    m.text.casefold() for m in item.explicits
                ]
                if not any(mod_lower in m for m in all_mods):
                    continue
            result.append(EquippedItem(slot=slot_name, **item.model_dump()))
        return result

    def compare_items(
        self,
        name: str,
        slot: str,
        *,
        name2: str | None = None,
        file_path: str | None = None,
        file_path2: str | None = None,
    ) -> list[ItemDiff]:
        _, build1 = self._build.load(name, file_path)
        build2_obj = self._build.load(name2 or name, file_path2)[1] if name2 else build1
        item1 = _find_item_in_slot(build1, slot)
        item2 = _find_item_in_slot(build2_obj, slot)
        if not item1 or not item2:
            raise SlotError(f"Item not found in slot {slot!r}")
        diffs = []
        compare_fields = (
            "name",
            "base_type",
            "rarity",
            "armour",
            "evasion",
            "energy_shield",
            "quality",
            "sockets",
        )
        for field in compare_fields:
            v1, v2 = getattr(item1, field), getattr(item2, field)
            if v1 != v2:
                diffs.append(ItemDiff(slot=slot, field=field, old_value=str(v1), new_value=str(v2)))
        mods1 = [m.text for m in item1.explicits]
        mods2 = [m.text for m in item2.explicits]
        if mods1 != mods2:
            diffs.append(
                ItemDiff(slot=slot, field="explicits", old_value=str(mods1), new_value=str(mods2))
            )
        return diffs

    def move_item(
        self,
        name: str,
        *,
        from_slot: str,
        to_slot: str,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        active_set = _find_active_item_set(build_obj)
        if not active_set:
            raise BuildValidationError("No active item set")
        from_canonical = normalize_slot(from_slot) or from_slot
        to_canonical = normalize_slot(to_slot) or to_slot
        moved = False
        for slot in active_set.slots:
            if slot.name == from_canonical:
                slot.name = to_canonical
                moved = True
                break
        if not moved:
            raise SlotError(f"No item in slot {from_slot!r}")
        self._build.save(build_obj, path)
        return MutationResult(
            from_slot=from_canonical,
            to_slot=to_canonical,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def swap_items(
        self,
        name: str,
        *,
        slot1: str,
        slot2: str,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        active_set = _find_active_item_set(build_obj)
        if not active_set:
            raise BuildValidationError("No active item set")
        s1 = normalize_slot(slot1) or slot1
        s2 = normalize_slot(slot2) or slot2
        slot_a = slot_b = None
        for slot in active_set.slots:
            if slot.name == s1:
                slot_a = slot
            elif slot.name == s2:
                slot_b = slot
        if not slot_a or not slot_b:
            raise SlotError("Both slots must have items for swap")
        slot_a.name, slot_b.name = s2, s1
        self._build.save(build_obj, path)
        return MutationResult(
            slot1=s1,
            slot2=s2,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def import_item_text(
        self,
        name: str,
        *,
        slot: str,
        item_text: str,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        next_id = max((i.id for i in build_obj.items), default=0) + 1
        parsed = _parse_item_text(item_text)
        rarity = parsed["rarity"]
        item_name = parsed["name"]
        base_type = parsed["base_type"]
        explicits = parsed["explicits"]
        item = Item(
            id=next_id,
            text="",
            rarity=rarity,
            name=item_name,
            base_type=base_type,
            explicits=[ItemMod(text=m) for m in explicits],
        )
        build_obj.items.append(item)
        canonical_slot = normalize_slot(slot) or slot
        active_set = _find_active_item_set(build_obj)
        if active_set:
            active_set.slots = [s for s in active_set.slots if s.name != canonical_slot]
            active_set.slots.append(ItemSlot(name=canonical_slot, item_id=next_id))
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=next_id,
            slot=canonical_slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

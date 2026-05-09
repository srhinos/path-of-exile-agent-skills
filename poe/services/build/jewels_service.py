from __future__ import annotations

from poe.exceptions import BuildValidationError, SlotError
from poe.models.build.build import MutationResult
from poe.models.build.items import Item, ItemMod, ItemSlot
from poe.models.build.jewels import EquippedJewel, JewelListResult
from poe.models.build.tree import TreeSocket
from poe.services.build.build_service import BuildService
from poe.services.build.constants import JEWEL_BASE_TYPES, STALE_STATS_WARNING


class JewelsService:
    """Owns jewel business logic."""

    def __init__(self, build_svc: BuildService | None = None) -> None:
        self._build = build_svc or BuildService()

    def list_jewels(self, name: str, *, file_path: str | None = None) -> JewelListResult:
        _, build_obj = self._build.load(name, file_path)
        item_map = {i.id: i for i in build_obj.items}

        spec = build_obj.get_active_spec()
        socket_map: dict[int, int] = {}
        if spec:
            for s in spec.sockets:
                socket_map[s.item_id] = s.node_id

        seen_ids: set[int] = set()
        regular_jewels = []
        cluster_jewels = []

        equipped = build_obj.get_equipped_items()
        for slot_name, item in equipped:
            if item.base_type not in JEWEL_BASE_TYPES:
                continue
            seen_ids.add(item.id)
            jewel = EquippedJewel(
                slot=slot_name,
                tree_node=socket_map.get(item.id),
                **item.model_dump(),
            )
            if "Cluster" in item.base_type:
                cluster_jewels.append(jewel)
            else:
                regular_jewels.append(jewel)

        target_set = None
        target_id = build_obj.active_item_set
        for s in build_obj.item_sets:
            if s.id == target_id:
                target_set = s
                break
        if not target_set and build_obj.item_sets:
            target_set = build_obj.item_sets[0]
        if target_set:
            for sock in target_set.socket_id_urls:
                if sock.item_id in seen_ids or sock.item_id not in item_map:
                    continue
                item = item_map[sock.item_id]
                if item.base_type not in JEWEL_BASE_TYPES:
                    continue
                seen_ids.add(item.id)
                jewel = EquippedJewel(
                    slot=f"TreeSocket:{sock.node_id}",
                    tree_node=sock.node_id,
                    **item.model_dump(),
                )
                if "Cluster" in item.base_type:
                    cluster_jewels.append(jewel)
                else:
                    regular_jewels.append(jewel)

        return JewelListResult(jewels=regular_jewels, cluster_jewels=cluster_jewels)

    def add_jewel(
        self,
        name: str,
        *,
        base: str,
        slot: str,
        jewel_name: str = "New Jewel",
        rarity: str = "RARE",
        explicits: list[str] | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        if base not in JEWEL_BASE_TYPES:
            valid = sorted(JEWEL_BASE_TYPES)
            raise BuildValidationError(f"Invalid jewel base type {base!r}. Valid types: {valid}")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        next_id = max((i.id for i in build_obj.items), default=0) + 1
        item = Item(
            id=next_id,
            text="",
            rarity=rarity,
            name=jewel_name,
            base_type=base,
            explicits=[ItemMod(text=m) for m in (explicits or [])],
        )
        build_obj.items.append(item)
        active_set = None
        for iset in build_obj.item_sets:
            if iset.id == build_obj.active_item_set:
                active_set = iset
                break
        if not active_set and build_obj.item_sets:
            active_set = build_obj.item_sets[0]
        if active_set:
            active_set.slots = [s for s in active_set.slots if s.name != slot]
            active_set.slots.append(ItemSlot(name=slot, item_id=next_id))
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=next_id,
            slot=slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_jewel(
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
            for iset in build_obj.item_sets:
                if iset.id == build_obj.active_item_set:
                    for item_slot in iset.slots:
                        if item_slot.name == slot:
                            removed_id = item_slot.item_id
                            break
        if removed_id is None:
            raise SlotError("Jewel not found")
        build_obj.items = [i for i in build_obj.items if i.id != removed_id]
        for iset in build_obj.item_sets:
            iset.slots = [s for s in iset.slots if s.item_id != removed_id]
        spec = build_obj.get_active_spec()
        if spec:
            spec.sockets = [s for s in spec.sockets if s.item_id != removed_id]
        self._build.save(build_obj, path)
        return MutationResult(
            removed_id=removed_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def socket_jewel(
        self,
        name: str,
        *,
        item_id: int,
        node_id: int,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if not any(i.id == item_id for i in build_obj.items):
            raise SlotError(f"No item with id {item_id}")
        spec = build_obj.get_active_spec()
        if not spec:
            raise BuildValidationError("No active tree spec")
        spec.sockets = [s for s in spec.sockets if s.item_id != item_id]
        spec.sockets.append(TreeSocket(node_id=node_id, item_id=item_id))
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=item_id,
            node_id=node_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def unsocket_jewel(
        self,
        name: str,
        *,
        item_id: int | None = None,
        node_id: int | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        if item_id is None and node_id is None:
            raise BuildValidationError("Specify item_id or node_id")
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        spec = build_obj.get_active_spec()
        if not spec:
            raise BuildValidationError("No active tree spec")
        removed = None
        for s in spec.sockets:
            if (item_id is not None and s.item_id == item_id) or (
                node_id is not None and s.node_id == node_id
            ):
                removed = s
                break
        if not removed:
            raise SlotError("Socket binding not found")
        spec.sockets.remove(removed)
        self._build.save(build_obj, path)
        return MutationResult(
            item_id=removed.item_id,
            node_id=removed.node_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

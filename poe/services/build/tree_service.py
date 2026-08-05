from __future__ import annotations

from poe.exceptions import BuildValidationError
from poe.models.build.build import MutationResult
from poe.models.build.tree import (
    MasteryMapping,
    TreeComparison,
    TreeDetail,
    TreeSpec,
    TreeSpecList,
    TreeSummary,
)
from poe.services.build.build_service import BuildService
from poe.services.build.constants import (
    ASCENDANCY_ID_TO_NAME,
    CLASS_ID_TO_NAME,
    DEFAULT_TREE_VERSION,
    STALE_STATS_WARNING,
)


class TreeService:
    """Owns passive tree business logic."""

    def __init__(self, build_svc: BuildService | None = None) -> None:
        self._build = build_svc or BuildService()

    def get_specs(self, name: str) -> TreeSpecList:
        _, build_obj = self._build.load(name)
        return TreeSpecList(
            active_spec=build_obj.active_spec,
            specs=[
                TreeSummary(
                    index=i + 1,
                    title=s.title or f"Spec {i + 1}",
                    tree_version=s.tree_version,
                    node_count=len(s.nodes),
                    class_id=s.class_id,
                    ascend_class_id=s.ascend_class_id,
                    active=(i + 1) == build_obj.active_spec,
                )
                for i, s in enumerate(build_obj.specs)
            ],
        )

    def get_tree(self, name: str, *, spec_index: int | None = None) -> TreeDetail:
        _, build_obj = self._build.load(name)
        if spec_index is not None:
            idx = spec_index - 1
            if idx < 0 or idx >= len(build_obj.specs):
                raise BuildValidationError(
                    f"Spec {spec_index} not found (build has {len(build_obj.specs)} specs)"
                )
            active_spec = build_obj.specs[idx]
        else:
            active_spec = build_obj.get_active_spec()
        if not active_spec:
            raise BuildValidationError("No tree spec found")
        idx_for_title = (spec_index or build_obj.active_spec) - 1
        spec_data = active_spec.model_dump()
        if not spec_data.get("title"):
            spec_data["title"] = f"Spec {idx_for_title + 1}"
        return TreeDetail(
            spec_index=spec_index or build_obj.active_spec,
            node_count=len(active_spec.nodes),
            **spec_data,
        )

    def compare_trees(self, name1: str, name2: str) -> TreeComparison:
        _, build1 = self._build.load(name1)
        _, build2 = self._build.load(name2)
        spec1 = build1.get_active_spec()
        spec2 = build2.get_active_spec()
        nodes1 = set(spec1.nodes) if spec1 else set()
        nodes2 = set(spec2.nodes) if spec2 else set()
        masteries1 = {(m.node_id, m.effect_id) for m in (spec1.mastery_effects if spec1 else [])}
        masteries2 = {(m.node_id, m.effect_id) for m in (spec2.mastery_effects if spec2 else [])}
        class_diff: dict = {}
        if (
            spec1
            and spec2
            and (spec1.class_id != spec2.class_id or spec1.ascend_class_id != spec2.ascend_class_id)
        ):
            class_diff = {
                name1: {"class_id": spec1.class_id, "ascend_class_id": spec1.ascend_class_id},
                name2: {"class_id": spec2.class_id, "ascend_class_id": spec2.ascend_class_id},
            }
        return TreeComparison(
            build1_only=sorted(nodes1 - nodes2),
            build2_only=sorted(nodes2 - nodes1),
            shared=sorted(nodes1 & nodes2),
            build1_count=len(nodes1),
            build2_count=len(nodes2),
            mastery_diff={
                "build1_only": [list(m) for m in sorted(masteries1 - masteries2)],
                "build2_only": [list(m) for m in sorted(masteries2 - masteries1)],
                "shared": [list(m) for m in sorted(masteries1 & masteries2)],
            },
            class_diff=class_diff,
        )

    def set_tree(
        self,
        name: str,
        *,
        nodes: str | None = None,
        add_nodes: str | None = None,
        remove_nodes: str | None = None,
        mastery: list[str] | None = None,
        add_mastery: list[str] | None = None,
        remove_mastery: list[str] | None = None,
        class_id: int | None = None,
        ascend_class_id: int | None = None,
        tree_version: str | None = None,
        spec_index: int | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        idx = (spec_index or build_obj.active_spec) - 1
        if idx < 0 or idx >= len(build_obj.specs):
            raise BuildValidationError("Spec index out of range")
        active_spec = build_obj.specs[idx]
        try:
            if nodes is not None:
                active_spec.nodes = sorted({int(n) for n in nodes.split(",") if n.strip()})
            if add_nodes:
                existing = set(active_spec.nodes)
                for raw in add_nodes.split(","):
                    s = raw.strip()
                    if s:
                        existing.add(int(s))
                active_spec.nodes = sorted(existing)
            if remove_nodes:
                to_remove = {int(n.strip()) for n in remove_nodes.split(",") if n.strip()}
                active_spec.nodes = [n for n in active_spec.nodes if n not in to_remove]
        except ValueError as e:
            # int(...) raises ValueError on non-numeric input. Translate so
            # users see a clean PoeError envelope rather than a raw traceback.
            raise BuildValidationError(
                f"Tree node IDs must be comma-separated integers: {e}"
            ) from e
        try:
            self._apply_mastery_changes(active_spec, mastery, add_mastery, remove_mastery)
        except ValueError as e:
            raise BuildValidationError(
                f"Mastery entries must be 'node_id:effect_id' pairs: {e}"
            ) from e
        if class_id is not None:
            active_spec.class_id = class_id
            build_obj.class_name = CLASS_ID_TO_NAME.get(class_id, build_obj.class_name)
        if ascend_class_id is not None:
            active_spec.ascend_class_id = ascend_class_id
            eff_class = class_id if class_id is not None else active_spec.class_id
            build_obj.ascend_class_name = ASCENDANCY_ID_TO_NAME.get(
                (eff_class, ascend_class_id),
                "",
            )
        if tree_version is not None:
            active_spec.tree_version = tree_version
        self._build.save(build_obj, path)
        return MutationResult(
            node_count=len(active_spec.nodes),
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    @staticmethod
    def _apply_mastery_changes(
        spec: TreeSpec,
        mastery: list[str] | None,
        add_mastery: list[str] | None,
        remove_mastery: list[str] | None,
    ) -> None:
        if mastery:
            seen_nodes: set[int] = set()
            spec.mastery_effects = []
            for m in mastery:
                nid, eid = m.split(":", 1)
                node_id = int(nid)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                spec.mastery_effects.append(MasteryMapping(node_id=node_id, effect_id=int(eid)))
        if add_mastery:
            for m in add_mastery:
                nid, eid = m.split(":", 1)
                node_id, effect_id = int(nid), int(eid)
                spec.mastery_effects = [me for me in spec.mastery_effects if me.node_id != node_id]
                spec.mastery_effects.append(MasteryMapping(node_id=node_id, effect_id=effect_id))
        if remove_mastery:
            to_remove = {
                (int(nid), int(eid)) for m in remove_mastery for nid, eid in [m.split(":", 1)]
            }
            spec.mastery_effects = [
                m for m in spec.mastery_effects if (m.node_id, m.effect_id) not in to_remove
            ]

    def search_nodes(
        self,
        name: str,
        query: str,
        *,
        spec_index: int | None = None,
        file_path: str | None = None,
    ) -> list[dict]:
        _, build_obj = self._build.load(name, file_path)
        idx = (spec_index or build_obj.active_spec) - 1
        if idx < 0 or idx >= len(build_obj.specs):
            raise BuildValidationError("Spec index out of range")
        spec = build_obj.specs[idx]
        q = query.casefold()

        override_map = {o.node_id: o for o in spec.overrides}
        results = []
        for node_id in spec.nodes:
            override = override_map.get(node_id)
            if override and (q in override.name.casefold() or q in override.text.casefold()):
                results.append(
                    {
                        "node_id": node_id,
                        "name": override.name,
                        "text": override.text,
                        "allocated": True,
                    }
                )
            elif q in str(node_id):
                results.append({"node_id": node_id, "allocated": True})
        return results

    def set_active(self, name: str, spec: int, *, file_path: str | None = None) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if spec < 1 or spec > len(build_obj.specs):
            raise BuildValidationError(
                f"Spec {spec} out of range (build has {len(build_obj.specs)} specs)"
            )
        build_obj.active_spec = spec
        self._build.save(build_obj, path)
        return MutationResult(
            active_spec=spec,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def add_spec(
        self, name: str, *, title: str = "", file_path: str | None = None
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        new_spec = TreeSpec(title=title, tree_version=DEFAULT_TREE_VERSION)
        build_obj.specs.append(new_spec)
        self._build.save(build_obj, path)
        return MutationResult(
            spec_index=len(build_obj.specs),
            title=title,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_spec(self, name: str, spec: int, *, file_path: str | None = None) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if len(build_obj.specs) <= 1:
            raise BuildValidationError("Cannot remove the last remaining spec")
        if spec < 1 or spec > len(build_obj.specs):
            raise BuildValidationError(
                f"Spec {spec} out of range (build has {len(build_obj.specs)} specs)"
            )
        build_obj.specs.pop(spec - 1)
        build_obj.active_spec = min(build_obj.active_spec, len(build_obj.specs))
        self._build.save(build_obj, path)
        return MutationResult(
            remaining_specs=len(build_obj.specs),
            active_spec=build_obj.active_spec,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

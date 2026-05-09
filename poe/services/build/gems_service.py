from __future__ import annotations

from poe.exceptions import BuildValidationError
from poe.models.build.build import MutationResult
from poe.models.build.gems import Gem, GemGroup, SkillSetList, SkillSetSummary
from poe.services.build.build_service import BuildService
from poe.services.build.constants import STALE_STATS_WARNING


class GemsService:
    """Owns skill gem business logic."""

    def __init__(self, build_svc: BuildService | None = None) -> None:
        self._build = build_svc or BuildService()

    def list_sets(self, name: str) -> SkillSetList:
        _, build_obj = self._build.load(name)
        return SkillSetList(
            active_skill_set=build_obj.active_skill_set,
            sets=[
                SkillSetSummary(id=sid, active=sid == build_obj.active_skill_set)
                for sid in build_obj.skill_set_ids
            ],
        )

    def list_gems(self, name: str, *, skill_set: int | None = None) -> list[GemGroup]:
        _, build_obj = self._build.load(name, skill_set_id=skill_set)
        return list(build_obj.skill_groups)

    def add_group(
        self,
        name: str,
        *,
        gems: list[str] | list[dict] | None = None,
        slot: str = "",
        level: int = 20,
        quality: int = 0,
        quality_id: str = "Default",
        include_full_dps: bool = False,
        file_path: str | None = None,
    ) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        new_gems = []
        for g in gems or []:
            if isinstance(g, dict):
                new_gems.append(
                    Gem(
                        name_spec=g["name"],
                        level=g.get("level", level),
                        quality=g.get("quality", quality),
                        quality_id=g.get("quality_id", quality_id),
                    )
                )
            else:
                new_gems.append(
                    Gem(name_spec=g, level=level, quality=quality, quality_id=quality_id)
                )
        group = GemGroup(
            slot=slot,
            enabled=True,
            include_in_full_dps=include_full_dps,
            gems=new_gems,
        )
        build_obj.skill_groups.append(group)
        if build_obj.skill_sets:
            build_obj.skill_sets.setdefault(build_obj.active_skill_set, []).append(group)
        self._build.save(build_obj, path)
        return MutationResult(
            index=len(build_obj.skill_groups) - 1,
            gems=[g.name_spec for g in new_gems],
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_group(self, name: str, index: int, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if index < 0 or index >= len(build_obj.skill_groups):
            raise BuildValidationError(
                f"Index {index} out of range (0-{len(build_obj.skill_groups) - 1})"
            )
        removed = build_obj.skill_groups.pop(index)
        if build_obj.skill_sets:
            for sid_groups in build_obj.skill_sets.values():
                if removed in sid_groups:
                    sid_groups.remove(removed)
        self._build.save(build_obj, path)
        return MutationResult(
            removed_index=index,
            slot=removed.slot,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def edit_group(
        self,
        name: str,
        group: int,
        *,
        swap: list[str] | None = None,
        set_level: list[str] | None = None,
        set_quality: list[str] | None = None,
        set_quality_id: list[str] | None = None,
        toggle: list[str] | None = None,
        set_slot: str | None = None,
        file_path: str | None = None,
    ) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if group < 0 or group >= len(build_obj.skill_groups):
            raise BuildValidationError(
                f"Group index {group} out of range (0-{len(build_obj.skill_groups) - 1})"
            )
        sg = build_obj.skill_groups[group]
        for swap_pair in swap or []:
            old_name, new_name = swap_pair.split(",", 1)
            gem = self._find_gem(sg, old_name, group)
            gem.name_spec = new_name
            gem.skill_id = ""
            gem.gem_id = ""
        for lp in set_level or []:
            gn, lv = lp.split(",", 1)
            self._find_gem(sg, gn, group).level = int(lv)
        for qp in set_quality or []:
            gn, qv = qp.split(",", 1)
            self._find_gem(sg, gn, group).quality = int(qv)
        for qid in set_quality_id or []:
            gn, qi = qid.split(",", 1)
            self._find_gem(sg, gn, group).quality_id = qi
        for gn in toggle or []:
            g = self._find_gem(sg, gn, group)
            g.enabled = not g.enabled
        if set_slot is not None:
            sg.slot = set_slot
        self._build.save(build_obj, path)
        return MutationResult(
            group_index=group,
            gems=[g.name_spec for g in sg.gems],
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def add_gem_to_group(
        self,
        name: str,
        group: int,
        *,
        gem_name: str,
        level: int = 20,
        quality: int = 0,
        quality_id: str = "Default",
        file_path: str | None = None,
    ) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if group < 0 or group >= len(build_obj.skill_groups):
            raise BuildValidationError(
                f"Group index {group} out of range (0-{len(build_obj.skill_groups) - 1})"
            )
        sg = build_obj.skill_groups[group]
        sg.gems.append(Gem(name_spec=gem_name, level=level, quality=quality, quality_id=quality_id))
        self._build.save(build_obj, path)
        return MutationResult(
            group_index=group,
            gems=[g.name_spec for g in sg.gems],
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_gem_from_group(
        self,
        name: str,
        group: int,
        *,
        gem_name: str,
        file_path: str | None = None,
    ) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if group < 0 or group >= len(build_obj.skill_groups):
            raise BuildValidationError(
                f"Group index {group} out of range (0-{len(build_obj.skill_groups) - 1})"
            )
        sg = build_obj.skill_groups[group]
        gem = self._find_gem(sg, gem_name, group)
        sg.gems.remove(gem)
        self._build.save(build_obj, path)
        return MutationResult(
            group_index=group,
            gems=[g.name_spec for g in sg.gems],
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def set_active(self, name: str, skill_set: int, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if skill_set not in build_obj.skill_set_ids:
            raise BuildValidationError(f"Skill set {skill_set} not found")
        build_obj.active_skill_set = skill_set
        self._build.save(build_obj, path)
        return MutationResult(
            active_skill_set=skill_set,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def add_set(self, name: str, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        max_id = max(build_obj.skill_set_ids, default=0)
        new_id = max_id + 1
        build_obj.skill_set_ids.append(new_id)
        build_obj.skill_sets[new_id] = []
        self._build.save(build_obj, path)
        return MutationResult(
            new_set_id=new_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_set(self, name: str, skill_set: int, *, file_path: str | None = None) -> dict:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if len(build_obj.skill_set_ids) <= 1:
            raise BuildValidationError("Cannot remove the last remaining skill set")
        if skill_set not in build_obj.skill_set_ids:
            raise BuildValidationError(f"Skill set {skill_set} not found")
        build_obj.skill_set_ids.remove(skill_set)
        build_obj.skill_sets.pop(skill_set, None)
        if build_obj.active_skill_set == skill_set:
            build_obj.active_skill_set = build_obj.skill_set_ids[0]
        self._build.save(build_obj, path)
        return MutationResult(
            removed_set_id=skill_set,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    @staticmethod
    def _find_gem(sg: GemGroup, gem_name: str, group_idx: int) -> Gem:
        for gem in sg.gems:
            if gem.name_spec.casefold() == gem_name.casefold():
                return gem
        raise BuildValidationError(f"Gem {gem_name!r} not found in group {group_idx}")

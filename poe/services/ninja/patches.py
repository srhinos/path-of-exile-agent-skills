from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from poe.models.ninja.builds import DimensionEntry, SearchResults


class NodeChange(BaseModel):
    """A single node that changed between two snapshots."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    change_type: str
    old_pct: float = 0.0
    new_pct: float = 0.0
    delta_pct: float = 0.0


class PatchDiff(BaseModel):
    """Diff between two search result snapshots."""

    model_config = ConfigDict(validate_assignment=True)

    added: list[NodeChange] = []
    removed: list[NodeChange] = []
    changed: list[NodeChange] = []
    total_old: int = 0
    total_new: int = 0


SIGNIFICANCE_THRESHOLD = 2.0


def diff_snapshots(
    old: SearchResults,
    new: SearchResults,
    *,
    dimension_id: str | None = None,
) -> PatchDiff:
    old_dims = _extract_entries(old, dimension_id)
    new_dims = _extract_entries(new, dimension_id)

    old_map = {e.name: e.percentage for e in old_dims}
    new_map = {e.name: e.percentage for e in new_dims}

    all_names = set(old_map) | set(new_map)

    added: list[NodeChange] = []
    removed: list[NodeChange] = []
    changed: list[NodeChange] = []

    for name in sorted(all_names):
        old_pct = old_map.get(name, 0.0)
        new_pct = new_map.get(name, 0.0)
        delta = new_pct - old_pct

        if name not in old_map:
            added.append(
                NodeChange(
                    name=name,
                    change_type="added",
                    new_pct=new_pct,
                    delta_pct=delta,
                )
            )
        elif name not in new_map:
            removed.append(
                NodeChange(
                    name=name,
                    change_type="removed",
                    old_pct=old_pct,
                    delta_pct=delta,
                )
            )
        elif abs(delta) >= SIGNIFICANCE_THRESHOLD:
            changed.append(
                NodeChange(
                    name=name,
                    change_type="increased" if delta > 0 else "decreased",
                    old_pct=old_pct,
                    new_pct=new_pct,
                    delta_pct=round(delta, 2),
                )
            )

    changed.sort(key=lambda c: abs(c.delta_pct), reverse=True)

    return PatchDiff(
        added=added,
        removed=removed,
        changed=changed,
        total_old=old.total,
        total_new=new.total,
    )


def find_build_impact(
    diff: PatchDiff,
    character_nodes: set[str],
) -> list[NodeChange]:
    return [change for change in [*diff.removed, *diff.changed] if change.name in character_nodes]


def _extract_entries(
    results: SearchResults,
    dimension_id: str | None,
) -> list[DimensionEntry]:
    if not results.dimensions:
        return []
    if dimension_id:
        dim = next(
            (d for d in results.dimensions if d.id == dimension_id),
            None,
        )
        return dim.entries if dim else []
    all_entries: list[DimensionEntry] = []
    for dim in results.dimensions:
        all_entries.extend(dim.entries)
    return all_entries

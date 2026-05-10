from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from poe.exceptions import PoeError
from poe.services.ninja.comparison import compare_to_meta
from poe.services.ninja.costing import cost_build, find_budget_alternatives
from poe.services.ninja.patches import diff_snapshots

if TYPE_CHECKING:
    from poe.services.ninja.atlas import AtlasService
    from poe.services.ninja.builds import BuildsService
    from poe.services.ninja.economy import EconomyService


class WorkflowResult(BaseModel):
    """Result from a compound workflow, with partial results on failure."""

    model_config = ConfigDict(validate_assignment=True)

    workflow: str
    success: bool = True
    data: dict[str, Any] = {}
    errors: list[str] = []


def fix_my_build(
    account: str,
    character: str,
    builds: BuildsService,
    economy: EconomyService,
    league: str,
    *,
    game: str = "poe1",
) -> WorkflowResult:
    result = WorkflowResult(workflow="fix_my_build")

    char = _try(result, "character", lambda: builds.get_character(account, character, game=game))
    if not char:
        result.success = False
        return result

    result.data["character"] = {
        "name": char.name,
        "class": char.class_name,
        "level": char.level,
    }

    search = _try(
        result,
        "meta_search",
        lambda: builds.search(game=game, class_filter=char.class_name),
    )

    if search:
        comparison = _try(result, "comparison", lambda: compare_to_meta(char, search))
        if comparison:
            result.data["comparison"] = comparison.model_dump()

    build_cost = _try(result, "costing", lambda: cost_build(char, economy, league, game=game))
    if build_cost:
        result.data["total_cost_chaos"] = build_cost.total_chaos
        alternatives = _try(
            result,
            "alternatives",
            lambda: find_budget_alternatives(build_cost, economy, league, game=game),
        )
        if alternatives:
            result.data["budget_alternatives"] = [a.model_dump() for a in alternatives[:5]]

    return result


def what_to_farm(
    atlas: AtlasService,
    economy: EconomyService,
    league: str,
) -> WorkflowResult:
    result = WorkflowResult(workflow="what_to_farm")

    profits = _try(result, "profit", lambda: atlas.estimate_profit(economy, league))
    if profits:
        result.data["top_strategies"] = profits[:10]

    popular = _try(result, "popular_nodes", lambda: atlas.get_popular_nodes(top_n=10))
    if popular:
        result.data["popular_atlas_nodes"] = [
            {"name": n.name, "pct": n.percentage} for n in popular
        ]

    return result


def what_build_to_play(
    builds: BuildsService,
    *,
    game: str = "poe1",
    budget_chaos: float | None = None,
) -> WorkflowResult:
    result = WorkflowResult(workflow="what_build_to_play")

    meta = _try(result, "meta", lambda: builds.get_meta_summary(game=game))
    if meta:
        result.data["league"] = meta.league
        result.data["total_builds"] = meta.total_builds
        result.data["top_builds"] = meta.top_builds[:10]
        result.data["rising"] = meta.rising

    if budget_chaos is not None:
        result.data["budget_chaos"] = budget_chaos

    return result


def how_should_i_craft(
    economy: EconomyService,
    league: str,
) -> WorkflowResult:
    result = WorkflowResult(workflow="how_should_i_craft")

    crafting = _try(result, "crafting_prices", lambda: economy.get_crafting_prices(league))
    if crafting:
        result.data["currency"] = dict(sorted(crafting.currency.items(), key=lambda x: x[1]))
        result.data["fossils"] = dict(sorted(crafting.fossils.items(), key=lambda x: x[1]))
        result.data["essences"] = dict(sorted(crafting.essences.items(), key=lambda x: x[1]))
        result.data["resonators"] = dict(sorted(crafting.resonators.items(), key=lambda x: x[1]))

    return result


def budget_upgrade(
    account: str,
    character: str,
    builds: BuildsService,
    economy: EconomyService,
    league: str,
    budget_chaos: float,
    *,
    game: str = "poe1",
) -> WorkflowResult:
    result = WorkflowResult(workflow="budget_upgrade")
    result.data["budget_chaos"] = budget_chaos

    char = _try(result, "character", lambda: builds.get_character(account, character, game=game))
    if not char:
        result.success = False
        return result

    build_cost = _try(result, "costing", lambda: cost_build(char, economy, league, game=game))
    if not build_cost:
        result.success = False
        return result

    result.data["current_cost"] = build_cost.total_chaos

    alternatives = _try(
        result,
        "alternatives",
        lambda: find_budget_alternatives(build_cost, economy, league, game=game),
    )
    if alternatives:
        within_budget = [a for a in alternatives if a.suggested_cost <= budget_chaos]
        result.data["suggestions"] = [a.model_dump() for a in within_budget[:5]]
        result.data["suggestions_count"] = len(within_budget)

    return result


def what_changed(
    builds: BuildsService,
    *,
    game: str = "poe1",
    old_time_machine: str = "week-1",
) -> WorkflowResult:
    result = WorkflowResult(workflow="what_changed")

    current = _try(result, "current", lambda: builds.search(game=game))
    old = _try(
        result,
        "old_snapshot",
        lambda: builds.search(game=game, time_machine=old_time_machine),
    )

    if current and old:
        diff = _try(result, "diff", lambda: diff_snapshots(old, current))
        if diff:
            result.data["added"] = [n.model_dump() for n in diff.added[:10]]
            result.data["removed"] = [n.model_dump() for n in diff.removed[:10]]
            result.data["changed"] = [n.model_dump() for n in diff.changed[:10]]
            result.data["total_old"] = diff.total_old
            result.data["total_new"] = diff.total_new

    return result


def _try(result: WorkflowResult, step: str, fn: Any) -> Any:
    try:
        return fn()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, PoeError) as e:
        # PoeError covers NinjaError, RateLimitError, ApiSchemaError, NetworkError —
        # the actual transport/schema failures the workflow exists to tolerate.
        # Without it, any of those crashed the whole workflow mid-flow.
        result.errors.append(f"{step}: {e}")
        return None

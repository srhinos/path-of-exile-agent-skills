from __future__ import annotations

from typing import TYPE_CHECKING

from poe.models.build.build import ValidationIssue
from poe.services.build.constants import (
    ACCURACY_LOW,
    AILMENT_IMMUNITY_CAP,
    BLOCK_THRESHOLD,
    FLASK_SLOTS,
    GEAR_SLOTS,
    HP_CRITICAL,
    HP_LOW,
    MOVE_SPEED_LOW,
    OVERCAPPED_RES_THRESHOLD,
    RES_CAP,
    SPELL_BLOCK_THRESHOLD,
    STUN_AVOIDANCE_PARTIAL,
    SUPPRESS_CAP,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from poe.models.build.build import BuildDocument


def _issue(severity: str, category: str, message: str) -> ValidationIssue:
    return ValidationIssue(severity=severity, category=category, message=message)


def _check_resistances(get: Callable, issues: list[ValidationIssue]) -> None:
    for res_name in ["Fire", "Cold", "Lightning"]:
        val = get(f"{res_name}Resist")
        if val is not None and val < RES_CAP:
            issues.append(
                _issue("critical", "resistances", f"{res_name} resistance is {val}% (cap is 75%)")
            )
        overcap = get(f"{res_name}ResistOverCap")
        if overcap is not None and overcap > OVERCAPPED_RES_THRESHOLD:
            issues.append(
                _issue(
                    "medium",
                    "resistances",
                    f"{res_name} resistance is overcapped by {overcap}% (wasted stats)",
                )
            )
    chaos_res = get("ChaosResist")
    if chaos_res is not None and chaos_res < 0:
        issues.append(_issue("high", "resistances", f"Chaos resistance is negative: {chaos_res}%"))


def _check_life_pool(get: Callable, issues: list[ValidationIssue]) -> None:
    life = get("Life") or 0
    es = get("EnergyShield") or 0
    total_hp = life + es
    if total_hp < HP_CRITICAL:
        issues.append(
            _issue(
                "critical",
                "life_pool",
                f"Total HP pool is very low: {total_hp:.0f} (Life: {life:.0f}, ES: {es:.0f})",
            )
        )
    elif total_hp < HP_LOW:
        issues.append(
            _issue(
                "high",
                "life_pool",
                f"Total HP pool is low: {total_hp:.0f} (Life: {life:.0f}, ES: {es:.0f})",
            )
        )


def _check_defenses(get: Callable, issues: list[ValidationIssue]) -> None:
    suppress = get("EffectiveSpellSuppressionChance") or 0
    if 0 < suppress < SUPPRESS_CAP:
        issues.append(
            _issue(
                "medium",
                "defenses",
                f"Spell suppression is {suppress}%"
                " (partial - consider reaching 100% or dropping it)",
            )
        )
    block_val = get("EffectiveBlockChance") or 0
    spell_block = get("EffectiveSpellBlockChance") or 0
    if block_val > BLOCK_THRESHOLD and spell_block < SPELL_BLOCK_THRESHOLD:
        issues.append(
            _issue(
                "medium",
                "defenses",
                f"Attack block is {block_val}% but spell block is only {spell_block}%",
            )
        )
    stun_avoid = get("StunAvoidChance") or 0
    if 0 < stun_avoid < STUN_AVOIDANCE_PARTIAL:
        issues.append(
            _issue(
                "medium",
                "defenses",
                f"Stun avoidance is {stun_avoid:.0f}% (consider reaching 100%)",
            )
        )
    for ailment in ["Freeze", "Ignite", "Shock"]:
        avoidance = get(f"Avoid{ailment}") or 0
        if 0 < avoidance < AILMENT_IMMUNITY_CAP:
            issues.append(
                _issue(
                    "medium",
                    "ailments",
                    f"{ailment} avoidance is {avoidance:.0f}% (not immune)",
                )
            )


def _check_combat(get: Callable, issues: list[ValidationIssue]) -> None:
    for attr, req_attr in [("Str", "ReqStr"), ("Dex", "ReqDex"), ("Int", "ReqInt")]:
        val = get(attr) or 0
        req = get(req_attr) or 0
        if req > val:
            issues.append(
                _issue("critical", "attributes", f"{attr} is {val:.0f} but {req:.0f} is required")
            )
    hit_chance = get("HitChance")
    if hit_chance is not None and hit_chance < ACCURACY_LOW:
        issues.append(
            _issue(
                "high",
                "accuracy",
                f"Hit chance is {hit_chance:.0f}% (consider accuracy improvements)",
            )
        )
    mana_cost = get("ManaPerSecondCost") or 0
    mana_regen = get("ManaRegenRecovery") or 0
    if mana_cost > 0 and mana_regen > 0 and mana_cost > mana_regen:
        issues.append(
            _issue(
                "high",
                "mana",
                f"Mana cost ({mana_cost:.0f}/s) exceeds regen ({mana_regen:.0f}/s)",
            )
        )
    move_speed = get("EffectiveMovementSpeedMod")
    if move_speed is not None and move_speed <= MOVE_SPEED_LOW:
        issues.append(
            _issue("medium", "movement", f"Movement speed modifier is {move_speed:.0f}% (no bonus)")
        )


def _check_equipment(build_obj: BuildDocument, issues: list[ValidationIssue]) -> None:
    equipped = build_obj.get_equipped_items()
    equipped_slots = {s for s, _ in equipped}
    empty_gear = [s for s in GEAR_SLOTS if s not in equipped_slots]
    if empty_gear:
        issues.append(_issue("high", "gear", f"Empty gear slots: {', '.join(empty_gear)}"))
    flask_items = [(s, item) for s, item in equipped if s.startswith("Flask")]
    if len(flask_items) < FLASK_SLOTS:
        issues.append(
            _issue("medium", "flasks", f"Fewer than 5 flasks equipped ({len(flask_items)} found)")
        )
    if flask_items and not any("Life Flask" in item.base_type for _, item in flask_items):
        issues.append(_issue("medium", "flasks", "No Life Flask equipped"))


def validate_build(build_obj: BuildDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    get = build_obj.get_stat
    _check_resistances(get, issues)
    _check_life_pool(get, issues)
    _check_defenses(get, issues)
    _check_combat(get, issues)
    _check_equipment(build_obj, issues)
    return issues

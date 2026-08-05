from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from poe.models.ninja.builds import CharacterResponse, SearchResults

POPULAR_THRESHOLD_PCT = 80.0
DEFENSIVE_THRESHOLDS = {
    "life": 3500,
    "energy_shield": 0,
    "fire_resistance": 75,
    "cold_resistance": 75,
    "lightning_resistance": 75,
    "chaos_resistance": -60,
    "spell_suppression_chance": 100,
}


class StatPercentile(BaseModel):
    """Percentile placement for a single stat."""

    model_config = ConfigDict(validate_assignment=True)

    stat: str
    value: int = 0
    percentile: float = 0.0
    min_value: int = 0
    max_value: int = 0


class GapEntry(BaseModel):
    """A missing or underused element compared to meta."""

    model_config = ConfigDict(validate_assignment=True)

    category: str
    name: str
    meta_pct: float = 0.0
    present: bool = False


class ComparisonResult(BaseModel):
    """Full comparison of a character against the meta."""

    model_config = ConfigDict(validate_assignment=True)

    character_name: str = ""
    class_name: str = ""
    stat_percentiles: list[StatPercentile] = []
    missing_keystones: list[GapEntry] = []
    missing_gems: list[GapEntry] = []
    missing_masteries: list[GapEntry] = []
    missing_anointments: list[GapEntry] = []
    defensive_flags: list[str] = []
    conformity_score: float = 0.0


def compare_to_meta(
    character: CharacterResponse,
    search_results: SearchResults,
) -> ComparisonResult:
    stat_pcts = _compute_stat_percentiles(character, search_results)
    missing_ks = _find_missing_keystones(character, search_results)
    missing_gems = _find_missing_gems(character, search_results)
    missing_masteries = _find_missing_masteries(character, search_results)
    missing_anointments = _find_missing_anointments(character, search_results)
    flags = _flag_defenses(character)
    conformity = _conformity_score(missing_ks, missing_gems, stat_pcts)

    return ComparisonResult(
        character_name=character.name,
        class_name=character.class_name,
        stat_percentiles=stat_pcts,
        missing_keystones=missing_ks,
        missing_gems=missing_gems,
        missing_masteries=missing_masteries,
        missing_anointments=missing_anointments,
        defensive_flags=flags,
        conformity_score=round(conformity, 1),
    )


def _compute_stat_percentiles(
    character: CharacterResponse,
    search_results: SearchResults,
) -> list[StatPercentile]:
    if not character.defensive_stats:
        return []

    stat_map = {
        "level": character.level,
        "life": character.defensive_stats.life,
        "energyshield": character.defensive_stats.energy_shield,
        "es": character.defensive_stats.energy_shield,
    }

    percentiles = []
    for ir in search_results.integer_ranges:
        value = stat_map.get(ir.id.lower())
        if value is None:
            continue
        span = ir.max_value - ir.min_value
        pct = 50.0 if span <= 0 else max(0.0, min(100.0, (value - ir.min_value) / span * 100))
        percentiles.append(
            StatPercentile(
                stat=ir.id,
                value=value,
                percentile=round(pct, 1),
                min_value=ir.min_value,
                max_value=ir.max_value,
            )
        )
    return percentiles


def _find_missing_keystones(
    character: CharacterResponse,
    search_results: SearchResults,
) -> list[GapEntry]:
    char_keystones = {k.name.lower() for k in character.keystones}

    # Match the canonical dim ID exactly. Substring "key in d.id.lower()"
    # would match a future dim ID like "keyword" and silently mis-route.
    ks_dim = next(
        (d for d in search_results.dimensions if d.id == "keypassives"),
        None,
    )
    if not ks_dim:
        return []

    missing = []
    for entry in ks_dim.entries:
        if entry.percentage < POPULAR_THRESHOLD_PCT:
            continue
        present = entry.name.lower() in char_keystones
        if not present:
            missing.append(
                GapEntry(
                    category="keystone",
                    name=entry.name,
                    meta_pct=entry.percentage,
                    present=False,
                )
            )
    return missing


def _find_missing_gems(
    character: CharacterResponse,
    search_results: SearchResults,
) -> list[GapEntry]:
    char_gems: set[str] = set()
    for skill in character.skills:
        for gem in skill.all_gems:
            char_gems.add(gem.name.lower())

    gem_dim = next(
        (d for d in search_results.dimensions if d.id == "skills"),
        None,
    )
    if not gem_dim:
        return []

    missing = []
    for entry in gem_dim.entries:
        if entry.percentage < POPULAR_THRESHOLD_PCT:
            continue
        present = entry.name.lower() in char_gems
        if not present:
            missing.append(
                GapEntry(
                    category="gem",
                    name=entry.name,
                    meta_pct=entry.percentage,
                    present=False,
                )
            )
    return missing


def _find_missing_masteries(
    character: CharacterResponse,
    search_results: SearchResults,
) -> list[GapEntry]:
    char_masteries = {m.name.lower() for m in character.masteries}

    mastery_dim = next(
        (d for d in search_results.dimensions if d.id == "masteries"),
        None,
    )
    if not mastery_dim:
        return []

    return [
        GapEntry(
            category="mastery",
            name=entry.name,
            meta_pct=entry.percentage,
            present=False,
        )
        for entry in mastery_dim.entries
        if entry.percentage >= POPULAR_THRESHOLD_PCT and entry.name.lower() not in char_masteries
    ]


def _find_missing_anointments(
    character: CharacterResponse,
    search_results: SearchResults,
) -> list[GapEntry]:
    anoint_dim = next(
        (d for d in search_results.dimensions if d.id == "anointed"),
        None,
    )
    if not anoint_dim:
        return []

    # CharacterResponse doesn't carry a structured anointment list, but
    # masteries-with-name-prefix "Anointed" appears in some snapshots, and
    # the keystones list can include anointment-granted keystones. Build
    # the present-set from both signals so we don't report user-owned
    # anointments as missing.
    char_anointments: set[str] = set()
    for m in character.masteries:
        char_anointments.add(m.name.casefold())
    for k in character.keystones:
        char_anointments.add(k.name.casefold())

    return [
        GapEntry(
            category="anointment",
            name=entry.name,
            meta_pct=entry.percentage,
            present=False,
        )
        for entry in anoint_dim.entries
        if entry.percentage >= POPULAR_THRESHOLD_PCT
        and entry.name.casefold() not in char_anointments
    ]


def _flag_defenses(character: CharacterResponse) -> list[str]:
    flags: list[str] = []
    ds = character.defensive_stats
    if not ds:
        return ["No defensive stats available"]

    for stat, threshold in DEFENSIVE_THRESHOLDS.items():
        val = getattr(ds, stat, 0)
        if threshold > 0 and val < threshold:
            flags.append(f"{stat} ({val}) below threshold ({threshold})")
    return flags


def _conformity_score(
    missing_keystones: list[GapEntry],
    missing_gems: list[GapEntry],
    stat_percentiles: list[StatPercentile],
) -> float:
    penalties = len(missing_keystones) * 10 + len(missing_gems) * 5
    if stat_percentiles:
        avg_pct = sum(s.percentile for s in stat_percentiles) / len(stat_percentiles)
    else:
        avg_pct = 50.0
    raw = avg_pct - penalties
    return max(0.0, min(100.0, raw))

from __future__ import annotations

from poe.models.ninja.builds import (
    CharacterResponse,
    DimensionEntry,
    IntegerRange,
    ResolvedDimension,
    SearchResults,
)
from poe.services.ninja.comparison import (
    ComparisonResult,
    _conformity_score,
    _flag_defenses,
    compare_to_meta,
)


def _make_search_results(
    keystones: list[tuple[str, float]] | None = None,
    gems: list[tuple[str, float]] | None = None,
    int_ranges: list[tuple[str, int, int]] | None = None,
) -> SearchResults:
    dims = []
    if keystones:
        dims.append(
            ResolvedDimension(
                id="keypassives",
                entries=[
                    DimensionEntry(name=name, count=int(pct * 10), percentage=pct)
                    for name, pct in keystones
                ],
            )
        )
    if gems:
        dims.append(
            ResolvedDimension(
                id="gem",
                entries=[
                    DimensionEntry(name=name, count=int(pct * 10), percentage=pct)
                    for name, pct in gems
                ],
            )
        )
    ranges = [
        IntegerRange(id=name, min_value=lo, max_value=hi) for name, lo, hi in (int_ranges or [])
    ]
    return SearchResults(
        total=1000,
        dimensions=dims,
        integer_ranges=ranges,
    )


def _make_character(**overrides) -> CharacterResponse:
    defaults = {
        "account": "test",
        "name": "TestChar",
        "class": "Pathfinder",
        "level": 95,
        "defensiveStats": {
            "life": 5000,
            "energyShield": 0,
            "fireResistance": 75,
            "coldResistance": 75,
            "lightningResistance": 75,
            "chaosResistance": 40,
            "spellSuppressionChance": 100,
        },
        "keyStones": [{"name": "Acrobatics"}, {"name": "Phase Acrobatics"}],
        "skills": [
            {
                "allGems": [
                    {"name": "Lightning Arrow", "isBuiltInSupport": False},
                    {"name": "GMP", "isBuiltInSupport": True},
                ],
            },
        ],
    }
    defaults.update(overrides)
    return CharacterResponse.model_validate(defaults)


class TestStatPercentiles:
    def test_percentile_placement(self):
        char = _make_character()
        meta = _make_search_results(int_ranges=[("level", 70, 100), ("life", 3000, 8000)])
        result = compare_to_meta(char, meta)

        level_pct = next(s for s in result.stat_percentiles if s.stat == "level")
        assert level_pct.percentile > 50

        life_pct = next(s for s in result.stat_percentiles if s.stat == "life")
        assert life_pct.value == 5000
        assert life_pct.percentile > 0

    def test_at_minimum(self):
        char = _make_character(level=70)
        meta = _make_search_results(int_ranges=[("level", 70, 100)])
        result = compare_to_meta(char, meta)

        level_pct = next(s for s in result.stat_percentiles if s.stat == "level")
        assert level_pct.percentile == 0.0

    def test_at_maximum(self):
        char = _make_character(level=100)
        meta = _make_search_results(int_ranges=[("level", 70, 100)])
        result = compare_to_meta(char, meta)

        level_pct = next(s for s in result.stat_percentiles if s.stat == "level")
        assert level_pct.percentile == 100.0

    def test_zero_span(self):
        char = _make_character(level=95)
        meta = _make_search_results(int_ranges=[("level", 95, 95)])
        result = compare_to_meta(char, meta)

        level_pct = next(s for s in result.stat_percentiles if s.stat == "level")
        assert level_pct.percentile == 50.0


class TestMissingKeystones:
    def test_detects_missing_popular_keystone(self):
        char = _make_character(keyStones=[{"name": "Acrobatics"}])
        meta = _make_search_results(
            keystones=[("Acrobatics", 90.0), ("Iron Reflexes", 85.0)],
        )
        result = compare_to_meta(char, meta)

        assert len(result.missing_keystones) == 1
        assert result.missing_keystones[0].name == "Iron Reflexes"
        assert result.missing_keystones[0].meta_pct == 85.0

    def test_no_missing_when_all_present(self):
        char = _make_character(keyStones=[{"name": "Acrobatics"}, {"name": "Iron Reflexes"}])
        meta = _make_search_results(
            keystones=[("Acrobatics", 90.0), ("Iron Reflexes", 85.0)],
        )
        result = compare_to_meta(char, meta)
        assert result.missing_keystones == []

    def test_ignores_unpopular_keystones(self):
        char = _make_character(keyStones=[])
        meta = _make_search_results(
            keystones=[("Rare Keystone", 20.0)],
        )
        result = compare_to_meta(char, meta)
        assert result.missing_keystones == []

    def test_threshold_at_80(self):
        char = _make_character(keyStones=[])
        meta = _make_search_results(
            keystones=[("Popular", 80.0), ("NotQuite", 79.9)],
        )
        result = compare_to_meta(char, meta)
        assert len(result.missing_keystones) == 1
        assert result.missing_keystones[0].name == "Popular"


class TestMissingGems:
    def test_detects_missing_gem(self):
        char = _make_character(skills=[{"allGems": [{"name": "Lightning Arrow"}]}])
        meta = _make_search_results(
            gems=[("Lightning Arrow", 90.0), ("GMP", 85.0)],
        )
        result = compare_to_meta(char, meta)
        assert len(result.missing_gems) == 1
        assert result.missing_gems[0].name == "GMP"


class TestDefensiveFlags:
    def test_flags_low_life(self):
        char = _make_character(
            defensiveStats={
                "life": 2000,
                "fireResistance": 75,
                "coldResistance": 75,
                "lightningResistance": 75,
                "chaosResistance": 40,
                "spellSuppressionChance": 100,
            }
        )
        result = compare_to_meta(char, _make_search_results())
        assert any("life" in f for f in result.defensive_flags)

    def test_no_flags_when_healthy(self):
        char = _make_character()
        result = compare_to_meta(char, _make_search_results())
        life_flags = [f for f in result.defensive_flags if "life" in f]
        assert life_flags == []

    def test_no_stats_available(self):
        char = _make_character(defensiveStats=None)
        flags = _flag_defenses(char)
        assert "No defensive stats available" in flags


class TestConformityScore:
    def test_perfect_conformity(self):
        char = _make_character(
            keyStones=[{"name": "Acrobatics"}],
            skills=[{"allGems": [{"name": "LA"}]}],
        )
        meta = _make_search_results(
            keystones=[("Acrobatics", 90.0)],
            gems=[("LA", 90.0)],
            int_ranges=[("level", 70, 100)],
        )
        result = compare_to_meta(char, meta)
        assert result.conformity_score > 50

    def test_missing_everything_lowers_score(self):
        char = _make_character(keyStones=[], skills=[])
        meta = _make_search_results(
            keystones=[("A", 90.0), ("B", 85.0), ("C", 82.0)],
            gems=[("X", 90.0), ("Y", 85.0)],
        )
        result = compare_to_meta(char, meta)
        assert result.conformity_score < 50

    def test_score_clamped_to_0_100(self):
        score = _conformity_score(
            [object()] * 20,
            [object()] * 20,
            [],
        )
        assert score >= 0.0
        assert score <= 100.0


class TestCompareToMeta:
    def test_returns_comparison_result(self):
        char = _make_character()
        meta = _make_search_results()
        result = compare_to_meta(char, meta)
        assert isinstance(result, ComparisonResult)
        assert result.character_name == "TestChar"
        assert result.class_name == "Pathfinder"

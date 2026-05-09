from __future__ import annotations

import math

import pytest

from poe.models.ninja.builds import (
    CharacterResponse,
    DimensionEntry,
    IntegerRange,
    ResolvedDimension,
    SearchResults,
)
from poe.services.ninja.comparison import (
    DEFENSIVE_THRESHOLDS,
    POPULAR_THRESHOLD_PCT,
    ComparisonResult,
    GapEntry,
    StatPercentile,
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


class TestComparisonInvariants:
    def test_conformity_score_bounded_for_full_meta(self):
        char = _make_character()
        meta = _make_search_results(
            keystones=[("Acrobatics", 90.0), ("Phase Acrobatics", 85.0)],
            gems=[("Lightning Arrow", 95.0), ("GMP", 92.0)],
            int_ranges=[("level", 70, 100), ("life", 3000, 8000)],
        )
        result = compare_to_meta(char, meta)
        assert 0.0 <= result.conformity_score <= 100.0
        assert math.isfinite(result.conformity_score)

    @pytest.mark.parametrize(
        ("level", "life", "es"),
        [
            (1, 100, 0),
            (50, 2500, 1000),
            (95, 5000, 0),
            (100, 8000, 5000),
        ],
    )
    def test_conformity_score_bounded_across_levels(self, level, life, es):
        char = _make_character(
            level=level,
            defensiveStats={
                "life": life,
                "energyShield": es,
                "fireResistance": 75,
                "coldResistance": 75,
                "lightningResistance": 75,
                "chaosResistance": 30,
                "spellSuppressionChance": 100,
            },
        )
        meta = _make_search_results(
            keystones=[("Acrobatics", 90.0)],
            gems=[("LA", 90.0)],
            int_ranges=[("level", 1, 100), ("life", 0, 10000), ("es", 0, 10000)],
        )
        result = compare_to_meta(char, meta)
        assert 0.0 <= result.conformity_score <= 100.0

    def test_integer_range_bounds_min_le_max(self):
        ranges = [
            IntegerRange(id="level", min_value=70, max_value=100),
            IntegerRange(id="life", min_value=3000, max_value=8000),
            IntegerRange(id="energyshield", min_value=0, max_value=12000),
        ]
        for r in ranges:
            assert r.min_value <= r.max_value

    def test_stat_percentile_bounds(self):
        char = _make_character()
        meta = _make_search_results(
            int_ranges=[
                ("level", 70, 100),
                ("life", 3000, 8000),
                ("energyshield", 0, 5000),
            ],
        )
        result = compare_to_meta(char, meta)
        for sp in result.stat_percentiles:
            assert 0.0 <= sp.percentile <= 100.0
            assert sp.min_value <= sp.max_value

    def test_below_minimum_clamped_to_zero(self):
        char = _make_character(level=10)
        meta = _make_search_results(int_ranges=[("level", 70, 100)])
        result = compare_to_meta(char, meta)
        level_pct = next(s for s in result.stat_percentiles if s.stat == "level")
        assert level_pct.percentile == 0.0

    def test_above_maximum_clamped_to_hundred(self):
        char = _make_character(level=200)
        meta = _make_search_results(int_ranges=[("level", 70, 100)])
        result = compare_to_meta(char, meta)
        level_pct = next(s for s in result.stat_percentiles if s.stat == "level")
        assert level_pct.percentile == 100.0


class TestPopularThresholdParametrize:
    @pytest.mark.parametrize(
        ("pct", "expected_missing"),
        [
            (100.0, True),
            (90.0, True),
            (80.0, True),
            (79.99, False),
            (50.0, False),
            (0.0, False),
        ],
    )
    def test_threshold_for_keystones(self, pct, expected_missing):
        char = _make_character(keyStones=[])
        meta = _make_search_results(keystones=[("K", pct)])
        result = compare_to_meta(char, meta)
        assert (len(result.missing_keystones) == 1) is expected_missing

    @pytest.mark.parametrize(
        ("pct", "expected_missing"),
        [
            (100.0, True),
            (POPULAR_THRESHOLD_PCT, True),
            (POPULAR_THRESHOLD_PCT - 0.01, False),
        ],
    )
    def test_threshold_for_gems(self, pct, expected_missing):
        char = _make_character(skills=[])
        meta = _make_search_results(gems=[("Some Gem", pct)])
        result = compare_to_meta(char, meta)
        assert (len(result.missing_gems) == 1) is expected_missing


class TestCaseInsensitiveMatching:
    @pytest.mark.parametrize(
        "char_name",
        ["Acrobatics", "acrobatics", "ACROBATICS", "AcRoBaTiCs"],
    )
    def test_keystone_match_is_case_insensitive(self, char_name):
        char = _make_character(keyStones=[{"name": char_name}])
        meta = _make_search_results(keystones=[("Acrobatics", 90.0)])
        result = compare_to_meta(char, meta)
        assert result.missing_keystones == []

    @pytest.mark.parametrize(
        "meta_name",
        ["Acrobatics", "acrobatics", "ACROBATICS"],
    )
    def test_meta_name_case_insensitive(self, meta_name):
        char = _make_character(keyStones=[{"name": "ACROBATICS"}])
        meta = _make_search_results(keystones=[(meta_name, 90.0)])
        result = compare_to_meta(char, meta)
        assert result.missing_keystones == []

    @pytest.mark.parametrize(
        "gem_name",
        ["Lightning Arrow", "lightning arrow", "LIGHTNING ARROW"],
    )
    def test_gem_match_case_insensitive(self, gem_name):
        char = _make_character(skills=[{"allGems": [{"name": gem_name}]}])
        meta = _make_search_results(gems=[("Lightning Arrow", 90.0)])
        result = compare_to_meta(char, meta)
        assert result.missing_gems == []


class TestDefensiveThresholdCoverage:
    @pytest.mark.parametrize("stat", list(DEFENSIVE_THRESHOLDS.keys()))
    def test_each_stat_threshold_can_flag(self, stat):
        threshold = DEFENSIVE_THRESHOLDS[stat]
        if threshold <= 0:
            pytest.skip("non-positive thresholds are not flagged by current logic")
        ds_dict = dict.fromkeys(DEFENSIVE_THRESHOLDS, 999)
        ds_dict[stat] = threshold - 1
        char = _make_character(
            defensiveStats={
                "life": ds_dict["life"],
                "energyShield": ds_dict["energy_shield"],
                "fireResistance": ds_dict["fire_resistance"],
                "coldResistance": ds_dict["cold_resistance"],
                "lightningResistance": ds_dict["lightning_resistance"],
                "chaosResistance": ds_dict["chaos_resistance"],
                "spellSuppressionChance": ds_dict["spell_suppression_chance"],
            }
        )
        flags = _flag_defenses(char)
        assert any(stat in f for f in flags)


class TestMissingMasteries:
    def test_detects_missing_popular_mastery(self):
        char = CharacterResponse.model_validate(
            {
                "account": "a",
                "name": "n",
                "class": "Witch",
                "level": 90,
                "masteries": [{"name": "Other"}],
            }
        )
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="masteries",
                    entries=[
                        DimensionEntry(name="Life Mastery", count=900, percentage=90.0),
                        DimensionEntry(name="Other", count=850, percentage=85.0),
                    ],
                )
            ],
        )
        result = compare_to_meta(char, meta)
        names = [m.name for m in result.missing_masteries]
        assert "Life Mastery" in names
        assert "Other" not in names


class TestMissingAnointments:
    def test_returns_only_above_threshold(self):
        char = _make_character()
        meta = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="anointed",
                    entries=[
                        DimensionEntry(name="Charisma", count=900, percentage=90.0),
                        DimensionEntry(name="Rare Anoint", count=10, percentage=1.0),
                    ],
                )
            ],
        )
        result = compare_to_meta(char, meta)
        names = [a.name for a in result.missing_anointments]
        assert "Charisma" in names
        assert "Rare Anoint" not in names

    def test_returns_empty_when_no_anoint_dim(self):
        char = _make_character()
        meta = _make_search_results()
        result = compare_to_meta(char, meta)
        assert result.missing_anointments == []


class TestStatPercentilesEmpty:
    def test_empty_when_no_defensive_stats(self):
        char = _make_character(defensiveStats=None)
        meta = _make_search_results(int_ranges=[("level", 70, 100)])
        result = compare_to_meta(char, meta)
        assert result.stat_percentiles == []


class TestGapEntrySemanticInvariants:
    def test_default_present_false(self):
        ge = GapEntry(category="keystone", name="X")
        assert ge.present is False
        assert ge.meta_pct == 0.0

    @pytest.mark.parametrize("category", ["keystone", "gem", "mastery", "anointment"])
    def test_category_field_round_trip(self, category):
        ge = GapEntry(category=category, name="X", meta_pct=85.0)
        assert ge.category == category
        assert 0.0 <= ge.meta_pct <= 100.0


class TestStatPercentileSemanticInvariants:
    def test_min_le_max(self):
        sp = StatPercentile(stat="level", value=95, percentile=80.0, min_value=70, max_value=100)
        assert sp.min_value <= sp.max_value
        assert 0.0 <= sp.percentile <= 100.0

    def test_default_zero(self):
        sp = StatPercentile(stat="x")
        assert sp.value == 0
        assert sp.percentile == 0.0
        assert sp.min_value == 0
        assert sp.max_value == 0


class TestConformityScoreEdgeCases:
    def test_no_penalties_no_percentiles(self):
        score = _conformity_score([], [], [])
        assert score == 50.0

    def test_score_finite(self):
        score = _conformity_score(
            [GapEntry(category="keystone", name="K")],
            [GapEntry(category="gem", name="G")],
            [StatPercentile(stat="level", percentile=80.0)],
        )
        assert math.isfinite(score)
        assert 0.0 <= score <= 100.0

    @pytest.mark.parametrize("avg_pct", [0.0, 25.0, 50.0, 75.0, 100.0])
    def test_score_clamped_with_extreme_percentiles(self, avg_pct):
        score = _conformity_score(
            [],
            [],
            [StatPercentile(stat="x", percentile=avg_pct)],
        )
        assert 0.0 <= score <= 100.0


class TestComparisonResultInvariants:
    def test_all_lists_default_empty(self):
        cr = ComparisonResult()
        assert cr.stat_percentiles == []
        assert cr.missing_keystones == []
        assert cr.missing_gems == []
        assert cr.missing_masteries == []
        assert cr.missing_anointments == []
        assert cr.defensive_flags == []
        assert cr.conformity_score == 0.0

    def test_score_clamp_invariant_holds_after_compare(self):
        char = _make_character(keyStones=[], skills=[])
        meta = _make_search_results(
            keystones=[(f"K{i}", 90.0) for i in range(50)],
            gems=[(f"G{i}", 90.0) for i in range(50)],
        )
        result = compare_to_meta(char, meta)
        assert 0.0 <= result.conformity_score <= 100.0

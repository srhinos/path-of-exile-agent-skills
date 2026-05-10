from __future__ import annotations

import pytest
from pydantic import ValidationError

from poe.models.sim import SimulationResult


class TestSimResultValidators:
    """Direct negative tests for every field_validator on SimulationResult.

    These validators raise ValueError on bad input; without explicit
    pytest.raises tests for each, the validation paths are effectively
    untested.
    """

    def _make(self, **overrides):
        defaults = {
            "base": "Hubris Circlet",
            "ilvl": 84,
            "method": "chaos",
            "targets": ["IncreasedLife"],
            "match_mode": "all",
            "iterations": 100,
            "hit_rate": "12.5%",
            "avg_attempts": 8.0,
            "cost_per_attempt": 1.0,
            "avg_cost_chaos": 8.0,
            "percentiles": {"p50": 5, "p90": 20},
        }
        defaults.update(overrides)
        return SimulationResult(**defaults)

    def test_clean_construction_passes(self):
        result = self._make()
        assert result.method == "chaos"

    def test_invalid_method_raises(self):
        with pytest.raises(ValidationError, match="valid CraftMethod"):
            self._make(method="bogus")

    def test_invalid_match_mode_raises(self):
        with pytest.raises(ValidationError, match="match_mode must be one of"):
            self._make(match_mode="sometimes")

    def test_invalid_hit_rate_format_raises(self):
        with pytest.raises(ValidationError, match=r"N% or N\.N%"):
            self._make(hit_rate="not-a-percent")

    def test_hit_rate_pattern_accepts_canonical_forms(self):
        for form in ["0%", "12%", "12.5%", "100.0%"]:
            self._make(hit_rate=form)

    def test_non_finite_avg_attempts_raises(self):
        for bad in [float("nan"), float("inf"), -float("inf")]:
            with pytest.raises(ValidationError, match="finite or None"):
                self._make(avg_attempts=bad)

    def test_negative_cost_per_attempt_raises(self):
        with pytest.raises(ValidationError, match="non-negative"):
            self._make(cost_per_attempt=-1.0)

    def test_negative_avg_cost_chaos_raises(self):
        with pytest.raises(ValidationError, match="non-negative"):
            self._make(avg_cost_chaos=-0.001)

    def test_none_finite_optional_allowed(self):
        # The optional float fields permit None to signal "no successful
        # trials" (avg_attempts=None when 0 hits).
        result = self._make(avg_attempts=None, cost_per_attempt=None, avg_cost_chaos=None)
        assert result.avg_attempts is None
        assert result.cost_per_attempt is None
        assert result.avg_cost_chaos is None

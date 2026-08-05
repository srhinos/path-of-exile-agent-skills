from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from poe.app import app
from poe.models.ninja.builds import DimensionEntry, ResolvedDimension, SearchResults
from poe.services.ninja.patches import diff_snapshots, find_build_impact
from tests.conftest import invoke_cli


def _make_results(
    entries: dict[str, float], *, total: int = 1000, dim_id: str = "class"
) -> SearchResults:
    return SearchResults(
        total=total,
        dimensions=[
            ResolvedDimension(
                id=dim_id,
                entries=[
                    DimensionEntry(name=name, count=int(pct * 10), percentage=pct)
                    for name, pct in entries.items()
                ],
            ),
        ],
    )


class TestDiffSnapshots:
    def test_detects_added_nodes(self):
        old = _make_results({"A": 50.0, "B": 30.0})
        new = _make_results({"A": 50.0, "B": 30.0, "C": 20.0})
        diff = diff_snapshots(old, new)

        assert len(diff.added) == 1
        assert diff.added[0].name == "C"
        assert diff.added[0].change_type == "added"

    def test_detects_removed_nodes(self):
        old = _make_results({"A": 50.0, "B": 30.0, "C": 20.0})
        new = _make_results({"A": 50.0, "B": 30.0})
        diff = diff_snapshots(old, new)

        assert len(diff.removed) == 1
        assert diff.removed[0].name == "C"
        assert diff.removed[0].change_type == "removed"

    def test_detects_significant_changes(self):
        old = _make_results({"A": 50.0, "B": 30.0})
        new = _make_results({"A": 55.0, "B": 25.0})
        diff = diff_snapshots(old, new)

        assert len(diff.changed) == 2
        a_change = next(c for c in diff.changed if c.name == "A")
        assert a_change.change_type == "increased"
        assert a_change.delta_pct == 5.0

        b_change = next(c for c in diff.changed if c.name == "B")
        assert b_change.change_type == "decreased"
        assert b_change.delta_pct == -5.0

    def test_ignores_insignificant_changes(self):
        old = _make_results({"A": 50.0})
        new = _make_results({"A": 51.0})
        diff = diff_snapshots(old, new)

        assert diff.changed == []

    def test_changed_sorted_by_magnitude(self):
        old = _make_results({"A": 50.0, "B": 30.0, "C": 20.0})
        new = _make_results({"A": 55.0, "B": 20.0, "C": 25.0})
        diff = diff_snapshots(old, new)

        deltas = [abs(c.delta_pct) for c in diff.changed]
        assert deltas == sorted(deltas, reverse=True)

    def test_totals_preserved(self):
        old = _make_results({"A": 50.0}, total=500)
        new = _make_results({"A": 50.0}, total=1000)
        diff = diff_snapshots(old, new)

        assert diff.total_old == 500
        assert diff.total_new == 1000

    def test_empty_snapshots(self):
        old = SearchResults(total=0, dimensions=[])
        new = SearchResults(total=0, dimensions=[])
        diff = diff_snapshots(old, new)

        assert diff.added == []
        assert diff.removed == []
        assert diff.changed == []

    def test_filter_by_dimension_id(self):
        old = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[DimensionEntry(name="A", count=500, percentage=50.0)],
                ),
                ResolvedDimension(
                    id="gem",
                    entries=[DimensionEntry(name="X", count=300, percentage=30.0)],
                ),
            ],
        )
        new = SearchResults(
            total=1000,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[DimensionEntry(name="A", count=500, percentage=50.0)],
                ),
                ResolvedDimension(
                    id="gem",
                    entries=[DimensionEntry(name="Y", count=300, percentage=30.0)],
                ),
            ],
        )
        diff = diff_snapshots(old, new, dimension_id="gem")
        assert len(diff.added) == 1
        assert diff.added[0].name == "Y"
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "X"


class TestFindBuildImpact:
    def test_finds_impacted_nodes(self):
        old = _make_results({"A": 50.0, "B": 30.0, "C": 20.0})
        new = _make_results({"A": 55.0, "B": 20.0})
        diff = diff_snapshots(old, new)

        impacted = find_build_impact(diff, {"C", "B"})
        names = {c.name for c in impacted}
        assert "C" in names
        assert "B" in names

    def test_no_impact(self):
        old = _make_results({"A": 50.0})
        new = _make_results({"B": 50.0})
        diff = diff_snapshots(old, new)

        impacted = find_build_impact(diff, {"C"})
        assert impacted == []


class TestToolsCli:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_tooltip_cli(self, mock_cls):
        client = MagicMock(no_cache=False)
        client.get_json.return_value = {
            "name": "Whispers of Doom",
            "implicitMods": [],
            "explicitMods": [{"text": "You can apply an additional Curse", "optional": False}],
            "mutatedMods": [],
        }
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "tooltip", "Whispers of Doom", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Whispers of Doom"

    @patch("poe.commands.ninja.price.commands.NinjaClient")
    def test_price_craft_cli(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return {
                    "economyLeagues": [{"name": "Mirage", "url": "mirage"}],
                    "oldEconomyLeagues": [],
                    "snapshotVersions": [],
                    "buildLeagues": [],
                    "oldBuildLeagues": [],
                }
            return {"lines": [], "currencyDetails": []}

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "price", "craft"])
        assert result.exit_code == 0


# ── Added tests below ────────────────────────────────────────────────────────


class TestDiffSnapshotsInvariants:
    def test_added_have_zero_old_value(self):
        old = _make_results({"A": 50.0})
        new = _make_results({"A": 50.0, "B": 30.0})
        diff = diff_snapshots(old, new)
        for c in diff.added:
            assert c.old_pct == 0.0
            assert c.new_pct > 0.0

    def test_removed_have_zero_new_value(self):
        old = _make_results({"A": 50.0, "B": 30.0})
        new = _make_results({"A": 50.0})
        diff = diff_snapshots(old, new)
        for c in diff.removed:
            assert c.new_pct == 0.0
            assert c.old_pct > 0.0

    def test_change_type_matches_delta_sign(self):
        old = _make_results({"A": 50.0, "B": 30.0})
        new = _make_results({"A": 55.0, "B": 25.0})
        diff = diff_snapshots(old, new)
        for c in diff.changed:
            if c.delta_pct > 0:
                assert c.change_type == "increased"
            elif c.delta_pct < 0:
                assert c.change_type == "decreased"


class TestFindBuildImpactInvariants:
    def test_returned_only_in_search_set(self):
        old = _make_results({"A": 50.0, "B": 30.0, "C": 20.0})
        new = _make_results({"A": 55.0, "B": 20.0})
        diff = diff_snapshots(old, new)

        impacted = find_build_impact(diff, {"B"})
        for entry in impacted:
            assert entry.name == "B"

    def test_impact_empty_set(self):
        old = _make_results({"A": 50.0})
        new = _make_results({"A": 60.0})
        diff = diff_snapshots(old, new)
        assert find_build_impact(diff, set()) == []


class TestTooltipCliHumanOutput:
    @patch("poe.commands.ninja.commands.NinjaClient")
    def test_tooltip_default_human(self, mock_cls):
        from poe.models.ninja.builds import TooltipMod, TooltipResponse

        client = MagicMock(no_cache=False)
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("poe.commands.ninja.commands.BuildsService") as mock_builds_cls:
            mock_svc = MagicMock()
            mock_svc.get_generic_tooltip.return_value = TooltipResponse(
                name="Whispers of Doom",
                implicit_mods=[],
                explicit_mods=[
                    TooltipMod(text="You can apply an additional Curse", optional=False),
                ],
                mutated_mods=[],
            )
            mock_builds_cls.return_value = mock_svc
            result = invoke_cli(app, ["ninja", "tooltip", "Whispers of Doom"])

        assert result.exit_code == 0
        assert "Whispers of Doom" in result.output
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json


class TestPriceCraftHumanOutput:
    @patch("poe.commands.ninja.price.commands.NinjaClient")
    def test_price_craft_default_human(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return {
                    "economyLeagues": [{"name": "Mirage", "url": "mirage"}],
                    "oldEconomyLeagues": [],
                    "snapshotVersions": [],
                    "buildLeagues": [],
                    "oldBuildLeagues": [],
                }
            return {"lines": [], "currencyDetails": []}

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "price", "craft"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json

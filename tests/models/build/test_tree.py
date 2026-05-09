"""Tests for tree models: TreeDetail, TreeSpecList, TreeSummary, TreeComparison."""

from __future__ import annotations

import pytest

from poe.models.build.tree import (
    MasteryMapping,
    TreeComparison,
    TreeDetail,
    TreeSocket,
    TreeSpec,
    TreeSpecList,
    TreeSummary,
)


class TestTreeDetail:
    def test_construction_from_spec(self):
        spec = TreeSpec(
            title="Main",
            tree_version="3_25",
            nodes=[100, 200, 300, 400, 500],
            class_id=5,
            ascend_class_id=2,
            mastery_effects=[MasteryMapping(node_id=100, effect_id=200)],
            sockets=[TreeSocket(node_id=26725, item_id=1)],
        )
        detail = TreeDetail(
            spec_index=1,
            node_count=5,
            **spec.model_dump(),
        )
        assert detail.spec_index == 1
        assert detail.node_count == 5
        assert detail.title == "Main"
        assert detail.tree_version == "3_25"
        assert detail.nodes == [100, 200, 300, 400, 500]
        assert detail.class_id == 5
        assert detail.ascend_class_id == 2
        assert len(detail.mastery_effects) == 1
        assert len(detail.sockets) == 1

    def test_inherits_tree_spec(self):
        assert issubclass(TreeDetail, TreeSpec)


class TestTreeSummary:
    def test_construction(self):
        summary = TreeSummary(
            index=1,
            title="Main",
            tree_version="3_25",
            node_count=42,
            class_id=5,
            ascend_class_id=2,
            active=True,
        )
        assert summary.index == 1
        assert summary.title == "Main"
        assert summary.node_count == 42
        assert summary.active is True

    def test_serialization(self):
        summary = TreeSummary(
            index=1,
            title="Bossing",
            tree_version="3_25",
            node_count=100,
            active=False,
        )
        data = summary.model_dump()
        restored = TreeSummary.model_validate(data)
        assert restored == summary


class TestTreeSpecList:
    def test_serialization(self):
        spec_list = TreeSpecList(
            active_spec=2,
            specs=[
                TreeSummary(
                    index=1,
                    title="Mapping",
                    node_count=80,
                    active=False,
                ),
                TreeSummary(
                    index=2,
                    title="Bossing",
                    node_count=95,
                    active=True,
                ),
            ],
        )
        data = spec_list.model_dump()
        assert data["active_spec"] == 2
        assert len(data["specs"]) == 2

        restored = TreeSpecList.model_validate(data)
        assert restored == spec_list


class TestTreeComparison:
    def test_serialization(self):
        comp = TreeComparison(
            build1_only=[100, 200],
            build2_only=[300],
            shared=[400, 500, 600],
            build1_count=5,
            build2_count=4,
            mastery_diff={"added": [1], "removed": [2]},
            class_diff={"build1": "Witch", "build2": "Ranger"},
        )
        data = comp.model_dump()
        assert data["build1_only"] == [100, 200]
        assert data["shared"] == [400, 500, 600]

        restored = TreeComparison.model_validate(data)
        assert restored == comp

    def test_empty_comparison(self):
        comp = TreeComparison()
        assert comp.build1_only == []
        assert comp.build2_only == []
        assert comp.shared == []
        assert comp.build1_count == 0
        assert comp.build2_count == 0


# ── Pydantic semantic invariants for tree models (Pattern 5) ────────────────


class TestTreeSpecInvariants:
    def test_nodes_rejects_duplicates(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSpec(nodes=[1, 2, 2, 3])

    def test_class_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSpec(class_id=-1)

    def test_ascend_class_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSpec(ascend_class_id=-1)

    def test_tree_version_rejects_invalid_format(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSpec(tree_version="!!!")

    def test_url_default_empty(self):
        spec = TreeSpec()
        assert spec.url == ""

    def test_class_id_zero_is_default(self):
        spec = TreeSpec()
        assert spec.class_id == 0


class TestTreeSummaryInvariants:
    def test_index_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSummary(index=0, title="x")

    def test_node_count_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSummary(index=1, title="x", node_count=-5)


class TestMasteryMappingInvariants:
    def test_node_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            MasteryMapping(node_id=-1, effect_id=200)

    def test_effect_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            MasteryMapping(node_id=1, effect_id=-1)


class TestTreeSocketInvariants:
    def test_node_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSocket(node_id=-1, item_id=1)

    def test_item_id_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            TreeSocket(node_id=1, item_id=-1)

    def test_item_id_zero_means_empty_socket(self):
        s = TreeSocket(node_id=1, item_id=0)
        assert s.item_id == 0


class TestTreeComparisonInvariants:
    def test_build1_count_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            TreeComparison(build1_count=-1)

    def test_serialization_roundtrip(self):
        comp = TreeComparison(build1_only=[1, 2], build2_only=[3], shared=[4])
        rebuilt = TreeComparison.model_validate(comp.model_dump())
        assert rebuilt == comp

from __future__ import annotations

from shutil import copy2

import pytest

from poe.exceptions import BuildValidationError
from poe.services.build.tree_service import TreeService


class TestTreeService:
    def test_get_specs(self, builds_dir):
        svc = TreeService()
        result = svc.get_specs("TestBuild")
        assert result.specs is not None
        assert len(result.specs) >= 1

    def test_get_tree(self, builds_dir):
        svc = TreeService()
        result = svc.get_tree("TestBuild")
        assert result.nodes is not None
        assert len(result.nodes) == 4

    def test_get_tree_invalid_spec(self, builds_dir):
        svc = TreeService()
        with pytest.raises(BuildValidationError):
            svc.get_tree("TestBuild", spec_index=99)

    def test_add_spec(self, build_file):
        svc = TreeService()
        result = svc.add_spec("ignored", title="New", file_path=str(build_file))
        assert result.status == "ok"

    def test_remove_spec_last(self, build_file):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="last"):
            svc.remove_spec("ignored", 1, file_path=str(build_file))

    def test_set_active(self, build_file):
        svc = TreeService()
        result = svc.set_active("ignored", 1, file_path=str(build_file))
        assert result.status == "ok"


class TestTreeServiceAdditional:
    def test_compare_trees(self, rich_build, tmp_path, monkeypatch):
        builds = tmp_path / "cmp_builds"
        builds.mkdir()
        copy2(rich_build, builds / "Build1.xml")
        copy2(rich_build, builds / "Build2.xml")
        monkeypatch.setenv("POB_BUILDS_PATH", str(builds))
        svc = TreeService()
        r = svc.compare_trees("Build1", "Build2")
        assert r.build1_only == []
        assert r.build2_only == []
        assert len(r.shared) == 3

    def test_set_tree_replace_nodes(self, rich_build):
        svc = TreeService()
        r = svc.set_tree("ignored", nodes="500,600", file_path=str(rich_build))
        assert r.status == "ok"
        assert r.node_count == 2

    def test_set_tree_add_nodes(self, rich_build):
        svc = TreeService()
        r = svc.set_tree("ignored", add_nodes="400,500", file_path=str(rich_build))
        assert r.status == "ok"
        assert r.node_count >= 4

    def test_set_tree_remove_nodes(self, rich_build):
        svc = TreeService()
        r = svc.set_tree("ignored", remove_nodes="100,200", file_path=str(rich_build))
        assert r.status == "ok"
        assert r.node_count == 1

    def test_set_tree_mastery(self, rich_build):
        svc = TreeService()
        r = svc.set_tree("ignored", mastery=["100:200"], file_path=str(rich_build))
        assert r.status == "ok"

    def test_set_tree_class_and_ascend(self, rich_build):
        svc = TreeService()
        r = svc.set_tree(
            "ignored",
            class_id=1,
            ascend_class_id=1,
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_set_tree_version(self, rich_build):
        svc = TreeService()
        r = svc.set_tree("ignored", tree_version="3_29", file_path=str(rich_build))
        assert r.status == "ok"

    def test_set_tree_invalid_spec(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.set_tree("ignored", spec_index=99, file_path=str(rich_build))

    def test_set_active_invalid(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.set_active("ignored", 99, file_path=str(rich_build))

    def test_remove_spec(self, rich_build):
        svc = TreeService()
        r = svc.remove_spec("ignored", 2, file_path=str(rich_build))
        assert r.remaining_specs == 1

    def test_remove_spec_invalid(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.remove_spec("ignored", 99, file_path=str(rich_build))


class TestIncrementalMastery:
    def test_add_mastery(self, rich_build):
        svc = TreeService()
        r = svc.set_tree(
            "ignored",
            add_mastery=["999:888"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_add_mastery_no_duplicate(self, rich_build):
        svc = TreeService()
        svc.set_tree(
            "ignored",
            add_mastery=["999:888"],
            file_path=str(rich_build),
        )
        svc.set_tree(
            "ignored",
            add_mastery=["999:888"],
            file_path=str(rich_build),
        )
        from poe.services.build.build_service import BuildService

        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        count = sum(1 for m in spec.mastery_effects if m.node_id == 999 and m.effect_id == 888)
        assert count == 1

    def test_remove_mastery(self, rich_build):
        svc = TreeService()
        svc.set_tree(
            "ignored",
            add_mastery=["111:222"],
            file_path=str(rich_build),
        )
        r = svc.set_tree(
            "ignored",
            remove_mastery=["111:222"],
            file_path=str(rich_build),
        )
        assert r.status == "ok"


class TestSearchNodes:
    def test_search_by_id(self, rich_build):
        svc = TreeService()
        results = svc.search_nodes("ignored", "100", file_path=str(rich_build))
        assert len(results) >= 1
        assert results[0]["node_id"] == 100

    def test_search_no_match(self, rich_build):
        svc = TreeService()
        results = svc.search_nodes("ignored", "99999", file_path=str(rich_build))
        assert results == []


class TestSpecLifeIncStat:
    def test_spec_life_inc_present_in_fixture(self):
        from pathlib import Path

        from poe.services.build.xml.parser import parse_build_file

        fixture = Path(__file__).resolve().parents[2] / "fixtures" / "endgame_full.xml"
        build = parse_build_file(fixture)
        val = build.get_stat("Spec:LifeInc")
        assert val == 112

    def test_spec_life_inc_low_warns_in_skills(self):
        from pathlib import Path

        from poe.services.build.xml.parser import parse_build_file

        fixture = Path(__file__).resolve().parents[2] / "fixtures" / "leveling_minimal.xml"
        build = parse_build_file(fixture)
        val = build.get_stat("Spec:LifeInc")
        assert val == 75


class TestNodeIdUniqueness:
    def test_add_nodes_dedupes(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_tree("ignored", add_nodes="100,100,200,200,300", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        assert len(spec.nodes) == len(set(spec.nodes))

    def test_replace_nodes_with_duplicates_documents_behavior(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_tree("ignored", nodes="500,500,600", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        assert 500 in spec.nodes
        assert 600 in spec.nodes

    def test_replace_nodes_should_dedupe(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_tree("ignored", nodes="500,500,600", file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        assert len(spec.nodes) == len(set(spec.nodes))


class TestMasteryUniqueness:
    def test_add_mastery_dedupes_pair(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_tree(
            "ignored",
            add_mastery=["111:222", "111:222", "111:222"],
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        count = sum(1 for m in spec.mastery_effects if m.node_id == 111 and m.effect_id == 222)
        assert count == 1

    def test_one_effect_per_mastery_node(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_tree("ignored", add_mastery=["555:1"], file_path=str(rich_build))
        svc.set_tree("ignored", add_mastery=["555:2"], file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        nodes_with_mastery = [m for m in spec.mastery_effects if m.node_id == 555]
        assert len(nodes_with_mastery) == 1


class TestRemoveSpecActiveAdjusts:
    def test_remove_active_spec_adjusts_active(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_active("ignored", 2, file_path=str(rich_build))
        result = svc.remove_spec("ignored", 2, file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert result.active_spec <= len(build.specs)
        assert build.active_spec >= 1


class TestSetTreeClassMappings:
    @pytest.mark.parametrize(
        ("class_id", "expected"),
        [
            (0, "Scion"),
            (1, "Marauder"),
            (2, "Ranger"),
            (3, "Witch"),
            (4, "Duelist"),
            (5, "Templar"),
            (6, "Shadow"),
        ],
    )
    def test_class_id_propagates_to_class_name(self, rich_build, class_id, expected):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        svc.set_tree("ignored", class_id=class_id, file_path=str(rich_build))
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        assert build.class_name == expected


class TestSetActiveBoundary:
    def test_set_active_zero_invalid(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.set_active("ignored", 0, file_path=str(rich_build))

    def test_set_active_negative_invalid(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.set_active("ignored", -1, file_path=str(rich_build))


class TestRemoveSpecBoundary:
    def test_remove_spec_zero_invalid(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.remove_spec("ignored", 0, file_path=str(rich_build))

    def test_remove_spec_negative_invalid(self, rich_build):
        svc = TreeService()
        with pytest.raises(BuildValidationError, match="range"):
            svc.remove_spec("ignored", -1, file_path=str(rich_build))


class TestGetTreeBoundary:
    def test_get_tree_zero_invalid(self, builds_dir):
        svc = TreeService()
        with pytest.raises(BuildValidationError):
            svc.get_tree("TestBuild", spec_index=0)

    def test_get_tree_negative_invalid(self, builds_dir):
        svc = TreeService()
        with pytest.raises(BuildValidationError):
            svc.get_tree("TestBuild", spec_index=-1)


class TestSetTreeRemoveNodesIdempotent:
    def test_remove_node_not_present_is_safe(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = TreeService()
        result = svc.set_tree("ignored", remove_nodes="99999", file_path=str(rich_build))
        assert result.status == "ok"
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        spec = build.get_active_spec()
        assert 99999 not in spec.nodes

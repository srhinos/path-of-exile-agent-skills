from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app as cli
from poe.services.build.xml.parser import parse_build_file
from tests.conftest import invoke_cli

# ── builds create ─────────────────────────────────────────────────────────────


class TestBuildsCreate:
    def test_create_default(self, tmp_path):
        out = tmp_path / "new.xml"
        result = invoke_cli(cli, ["build", "create", "new", "--file", str(out), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert out.exists()
        build = parse_build_file(out)
        assert build.class_name == "Scion"

    def test_create_with_class_and_level(self, tmp_path):
        out = tmp_path / "witch.xml"
        result = invoke_cli(
            cli,
            [
                "build",
                "create",
                "witch",
                "--class",
                "Witch",
                "--ascendancy",
                "Necromancer",
                "--level",
                "90",
                "--file",
                str(out),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(out)
        assert build.class_name == "Witch"
        assert build.ascend_class_name == "Necromancer"
        assert build.level == 90

    def test_create_already_exists(self, build_file):
        result = invoke_cli(cli, ["build", "create", "test", "--file", str(build_file)])
        assert result.exit_code != 0
        assert "already exists" in str(result.exception).lower()


# ── builds delete ─────────────────────────────────────────────────────────────


class TestBuildsDelete:
    def test_delete_with_confirm(self, build_file):
        result = invoke_cli(
            cli, ["build", "delete", "test", "--confirm", "--file", str(build_file)]
        )
        assert result.exit_code == 0
        assert not build_file.exists()

    def test_delete_without_confirm(self, build_file):
        result = invoke_cli(cli, ["build", "delete", "test", "--file", str(build_file)])
        assert result.exit_code != 0
        assert build_file.exists()

    def test_delete_not_found(self, tmp_path):
        result = invoke_cli(
            cli, ["build", "delete", "nope", "--confirm", "--file", str(tmp_path / "nope.xml")]
        )
        assert result.exit_code != 0


# ── items add ─────────────────────────────────────────────────────────────────


class TestItemsAdd:
    def test_add_rare_item(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Body Armour",
                "--rarity",
                "RARE",
                "--item-name",
                "Test Chest",
                "--base",
                "Vaal Regalia",
                "--energy-shield",
                "400",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        build = parse_build_file(build_file)
        assert len(build.items) == 2  # original + new
        new_item = build.items[-1]
        assert new_item.base_type == "Vaal Regalia"

    def test_add_with_influences(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Gloves",
                "--base",
                "Sorcerer Gloves",
                "--influence",
                "Shaper",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        assert "Shaper" in new_item.influences

    def test_add_with_crafted_mods(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Ring 1",
                "--base",
                "Diamond Ring",
                "--explicit",
                "+90 to maximum Life",
                "--crafted-mod",
                "+10% to all Resistances",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        assert any(m.is_crafted for m in new_item.explicits)

    def test_add_with_implicits(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Amulet",
                "--base",
                "Onyx Amulet",
                "--implicit",
                "+16 to all Attributes",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        assert len(new_item.implicits) == 1


# ── items add fractured mod ───────────────────────────────────────────────────


class TestItemsAddFracturedMod:
    def test_add_with_fractured_mod(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Body Armour",
                "--base",
                "Vaal Regalia",
                "--fractured-mod",
                "+90 to maximum Life",
                "--explicit",
                "+40% to Cold Resistance",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        fractured = [m for m in new_item.explicits if m.is_fractured]
        non_fractured = [m for m in new_item.explicits if not m.is_fractured]
        assert len(fractured) == 1
        assert fractured[0].text == "+90 to maximum Life"
        assert len(non_fractured) == 1

    def test_add_with_multiple_fractured_mods(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Helmet",
                "--base",
                "Hubris Circlet",
                "--fractured-mod",
                "+90 to maximum Life",
                "--fractured-mod",
                "+40% to Cold Resistance",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        fractured = [m for m in new_item.explicits if m.is_fractured]
        assert len(fractured) == 2

    def test_add_fractured_with_crafted(self, build_file):
        """Fractured and crafted mods can coexist on the same item."""
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Ring 1",
                "--base",
                "Diamond Ring",
                "--fractured-mod",
                "+90 to maximum Life",
                "--crafted-mod",
                "+10% to all Resistances",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        fractured = [m for m in new_item.explicits if m.is_fractured]
        crafted = [m for m in new_item.explicits if m.is_crafted]
        assert len(fractured) == 1
        assert len(crafted) == 1


# ── items add synthesised ─────────────────────────────────────────────────────


class TestItemsAddSynthesised:
    def test_add_synthesised_item(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Body Armour",
                "--base",
                "Vaal Regalia",
                "--synthesised",
                "--implicit",
                "+30 to Dexterity",
                "--explicit",
                "+90 to maximum Life",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        assert new_item.is_synthesised is True
        assert len(new_item.implicits) == 1
        assert len(new_item.explicits) == 1

    def test_add_non_synthesised_item(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Ring 1",
                "--base",
                "Diamond Ring",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        new_item = build.items[-1]
        assert new_item.is_synthesised is False


# ── items remove ──────────────────────────────────────────────────────────────


class TestItemsRemove:
    def test_remove_by_slot(self, build_file):
        build = parse_build_file(build_file)
        assert len(build.items) == 1

        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "remove",
                "test",
                "--slot",
                "Helmet",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert len(build.items) == 0

    def test_remove_by_id(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "remove",
                "test",
                "--id",
                "1",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert len(build.items) == 0

    def test_remove_no_args(self, build_file):
        result = invoke_cli(cli, ["build", "items", "remove", "test", "--file", str(build_file)])
        assert result.exit_code != 0


# ── gems add ──────────────────────────────────────────────────────────────────


class TestGemsAdd:
    def test_add_skill_group(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "add",
                "test",
                "--slot",
                "Helmet",
                "--gem",
                "Arc",
                "--gem",
                "Spell Echo Support",
                "--level",
                "20",
                "--quality",
                "20",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert len(build.skill_groups) == 2  # original + new
        new_group = build.skill_groups[-1]
        assert new_group.slot == "Helmet"
        assert len(new_group.gems) == 2
        assert new_group.gems[0].name_spec == "Arc"

    def test_add_with_full_dps(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "add",
                "test",
                "--gem",
                "Fireball",
                "--include-full-dps",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert build.skill_groups[-1].include_in_full_dps is True


# ── gems remove ───────────────────────────────────────────────────────────────


class TestGemsRemove:
    def test_remove_by_index(self, build_file):
        build = parse_build_file(build_file)
        assert len(build.skill_groups) == 1

        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "remove",
                "test",
                "--index",
                "0",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert len(build.skill_groups) == 0

    def test_remove_out_of_range(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "remove",
                "test",
                "--index",
                "99",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── tree set ──────────────────────────────────────────────────────────────────


class TestTreeSet:
    def test_set_nodes(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--nodes",
                "500,600,700",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        assert set(spec.nodes) == {500, 600, 700}

    def test_add_nodes(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--add-nodes",
                "500,600",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        assert 500 in spec.nodes
        assert 100 in spec.nodes  # original

    def test_remove_nodes(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--remove-nodes",
                "100,200",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        assert 100 not in spec.nodes
        assert 300 in spec.nodes  # remaining

    def test_set_masteries(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--mastery",
                "1000:2000",
                "--mastery",
                "3000:4000",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        assert len(spec.mastery_effects) == 2
        assert spec.mastery_effects[0].node_id == 1000

    def test_set_class_and_version(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--class-id",
                "3",
                "--ascend-class-id",
                "1",
                "--tree-version",
                "3_26",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        assert spec.class_id == 3
        assert spec.ascend_class_id == 1
        assert spec.tree_version == "3_26"


# ── config set ────────────────────────────────────────────────────────────────


class TestConfigSet:
    def test_set_boolean(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "set",
                "test",
                "--boolean",
                "usePowerCharges=true",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        cfg = build.get_active_config()
        inp = next(i for i in cfg.inputs if i.name == "usePowerCharges")
        assert inp.value is True

    def test_set_number(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "set",
                "test",
                "--number",
                "enemyPhysicalHitDamage=9999",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        cfg = build.get_active_config()
        inp = next(i for i in cfg.inputs if i.name == "enemyPhysicalHitDamage")
        assert inp.value == 9999.0

    def test_set_string(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "set",
                "test",
                "--string",
                "customMod=test value",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        cfg = build.get_active_config()
        inp = next(i for i in cfg.inputs if i.name == "customMod")
        assert inp.value == "test value"

    def test_remove_config(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "set",
                "test",
                "--remove",
                "useFrenzyCharges",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        cfg = build.get_active_config()
        names = [i.name for i in cfg.inputs]
        assert "useFrenzyCharges" not in names


# ── builds notes (refactored to use writer) ───────────────────────────────────


class TestBuildsNotes:
    def test_set_notes(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "notes",
                "test",
                "--set",
                "New notes content",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert build.notes.strip() == "New notes content"

    def test_get_notes(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "notes",
                "test",
                "--file",
                str(build_file),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["notes"] == "Build notes here"


# ── Claude/ safety layer ─────────────────────────────────────────────────────


class TestClaudeSafetyLayer:
    """Test that write operations go through the Claude/ subfolder safety layer."""


# ── items edit new params ────────────────────────────────────────────────────


class TestItemsEditNewParams:
    def test_set_sockets(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "edit",
                "test",
                "--slot",
                "Helmet",
                "--set-sockets",
                "B-B-B-B-B-B",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        item = next(i for _, i in build.get_equipped_items() if i.name == "Doom Crown")
        assert item.sockets == "B-B-B-B-B-B"

    def test_set_armour(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "edit",
                "test",
                "--slot",
                "Helmet",
                "--set-armour",
                "100",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        item = next(i for _, i in build.get_equipped_items() if i.name == "Doom Crown")
        assert item.armour == 100

    def test_set_energy_shield(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "edit",
                "test",
                "--slot",
                "Helmet",
                "--set-energy-shield",
                "500",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        item = next(i for _, i in build.get_equipped_items() if i.name == "Doom Crown")
        assert item.energy_shield == 500


# ── items compare file2 ─────────────────────────────────────────────────────


class TestItemsCompareFile2:
    def test_compare_with_file2(self, tmp_path):
        from tests.conftest import MINIMAL_BUILD_XML

        f1 = tmp_path / "build1.xml"
        f2 = tmp_path / "build2.xml"
        f1.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        f2.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "compare",
                "build1",
                "--slot",
                "Helmet",
                "--build2",
                "build2",
                "--file",
                str(f1),
                "--file2",
                str(f2),
            ],
        )
        assert result.exit_code == 0


# ── flasks add explicit ──────────────────────────────────────────────────────


class TestFlasksAddExplicit:
    def test_add_flask_with_explicit(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "flasks",
                "add",
                "test",
                "--base",
                "Granite Flask",
                "--slot",
                "Flask 1",
                "--explicit",
                "+3000 to Armour during Flask Effect",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        assert "status: ok" in result.output


# ── flasks edit explicit ─────────────────────────────────────────────────────


class TestFlasksEditExplicit:
    def test_add_explicit_to_flask(self, build_file):
        invoke_cli(
            cli,
            [
                "build",
                "flasks",
                "add",
                "test",
                "--base",
                "Granite Flask",
                "--slot",
                "Flask 1",
                "--file",
                str(build_file),
            ],
        )
        result = invoke_cli(
            cli,
            [
                "build",
                "flasks",
                "edit",
                "test",
                "--slot",
                "Flask 1",
                "--add-explicit",
                "+3000 to Armour during Flask Effect",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── flasks reorder ───────────────────────────────────────────────────────────


class TestFlasksReorder:
    def test_reorder_flasks(self, build_file):
        for slot in ["Flask 1", "Flask 2"]:
            invoke_cli(
                cli,
                [
                    "build",
                    "flasks",
                    "add",
                    "test",
                    "--base",
                    "Granite Flask",
                    "--slot",
                    slot,
                    "--file",
                    str(build_file),
                ],
            )
        result = invoke_cli(
            cli,
            [
                "build",
                "flasks",
                "reorder",
                "test",
                "--order",
                "Flask 2",
                "--order",
                "Flask 1",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── jewels add explicit ──────────────────────────────────────────────────────


class TestJewelsAddExplicit:
    def test_add_jewel_with_explicit(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "add",
                "test",
                "--base",
                "Cobalt Jewel",
                "--slot",
                "Jewel 1",
                "--explicit",
                "+10% to Fire Resistance",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        assert "status: ok" in result.output


# ── gems edit quality_id ─────────────────────────────────────────────────────


class TestGemsEditQualityId:
    def test_set_quality_id(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "edit",
                "test",
                "--group",
                "0",
                "--set-quality-id",
                "Fireball,Anomalous",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        group = build.skill_groups[0]
        fireball = next(g for g in group.gems if g.name_spec == "Fireball")
        assert fireball.quality_id == "Anomalous"


# ── gems add-to-group / remove-from-group ────────────────────────────────────


class TestGemsAddToGroup:
    def test_add_gem_to_existing_group(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "add-to-group",
                "test",
                "--group",
                "0",
                "--gem",
                "Greater Multiple Projectiles Support",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        group = build.skill_groups[0]
        names = [g.name_spec for g in group.gems]
        assert "Greater Multiple Projectiles Support" in names


class TestGemsRemoveFromGroup:
    def test_remove_gem_from_group(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "remove-from-group",
                "test",
                "--group",
                "0",
                "--gem",
                "Spell Echo Support",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        group = build.skill_groups[0]
        names = [g.name_spec for g in group.gems]
        assert "Spell Echo Support" not in names


# ── tree set add/remove mastery ──────────────────────────────────────────────


class TestTreeSetMastery:
    def test_add_mastery(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--add-mastery",
                "99999:88888",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        mastery_map = {m.node_id: m.effect_id for m in spec.mastery_effects}
        assert mastery_map.get(99999) == 88888

    def test_remove_mastery(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--remove-mastery",
                "53188:64875",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        spec = build.get_active_spec()
        mastery_map = {m.node_id: m.effect_id for m in spec.mastery_effects}
        assert 53188 not in mastery_map


# ── tree search ──────────────────────────────────────────────────────────────


class TestTreeSearch:
    def test_search_nodes(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "search",
                "test",
                "100",
                "--file",
                str(build_file),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert any(str(n["node_id"]).startswith("100") for n in data)


# ── config get --file ────────────────────────────────────────────────────────


class TestConfigGetFile:
    def test_config_get_with_file(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "config", "get", "test", "--file", str(build_file), "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)


# ── config sets ──────────────────────────────────────────────────────────────


class TestConfigSets:
    def test_config_sets(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "config", "sets", "test", "--file", str(build_file), "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1


# ── config add-set ───────────────────────────────────────────────────────────


class TestConfigAddSet:
    def test_config_add_set(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "add-set",
                "test",
                "--title",
                "Bossing",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── config remove-set ────────────────────────────────────────────────────────


class TestConfigRemoveSet:
    def test_config_remove_set(self, build_file):
        invoke_cli(
            cli,
            ["build", "config", "add-set", "test", "--title", "Temp", "--file", str(build_file)],
        )
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "remove-set",
                "test",
                "--config-set",
                "2",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── config switch-set ────────────────────────────────────────────────────────


class TestConfigSwitchSet:
    def test_config_switch_set(self, build_file):
        invoke_cli(
            cli,
            ["build", "config", "add-set", "test", "--title", "Alt", "--file", str(build_file)],
        )
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "switch-set",
                "test",
                "--config-set",
                "2",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── gems sets ────────────────────────────────────────────────────────────────


class TestGemsSets:
    def test_gems_sets(self):
        from poe.models.build.gems import SkillSetList, SkillSetSummary

        mock_svc = MagicMock()
        mock_svc.list_sets.return_value = SkillSetList(
            active_skill_set=1,
            sets=[SkillSetSummary(id=1, active=True)],
        )
        with patch("poe.commands.build.gems.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "gems", "sets", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "sets" in data


# ── gems set-active ──────────────────────────────────────────────────────────


class TestGemsSetActive:
    def test_gems_set_active(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "gems", "set-active", "test", "--skill-set", "1", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── gems add-set ─────────────────────────────────────────────────────────────


class TestGemsAddSet:
    def test_gems_add_set(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "gems", "add-set", "test", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── gems remove-set ──────────────────────────────────────────────────────────


class TestGemsRemoveSet:
    def test_gems_remove_set(self, build_file):
        invoke_cli(cli, ["build", "gems", "add-set", "test", "--file", str(build_file)])
        result = invoke_cli(
            cli,
            ["build", "gems", "remove-set", "test", "--skill-set", "2", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── items list --file ────────────────────────────────────────────────────────


class TestItemsListFile:
    def test_items_list_with_file(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "items", "list", "test", "--file", str(build_file), "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, (list, dict))


# ── items sets ───────────────────────────────────────────────────────────────


class TestItemsSets:
    def test_items_sets(self):
        from poe.models.build.items import ItemSetList, ItemSetSummary

        mock_svc = MagicMock()
        mock_svc.list_sets.return_value = ItemSetList(
            active_item_set="1",
            sets=[ItemSetSummary(id="1", title="Default", active=True, slot_count=1)],
        )
        with patch("poe.commands.build.items.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "items", "sets", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "sets" in data


# ── items set-active ─────────────────────────────────────────────────────────


class TestItemsSetActive:
    def test_items_set_active(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "items", "set-active", "test", "--item-set", "1", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── items add-set ────────────────────────────────────────────────────────────


class TestItemsAddSet:
    def test_items_add_set(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "items", "add-set", "test", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── items remove-set ─────────────────────────────────────────────────────────


class TestItemsRemoveSet:
    def test_items_remove_set(self, build_file):
        invoke_cli(cli, ["build", "items", "add-set", "test", "--file", str(build_file)])
        result = invoke_cli(
            cli,
            ["build", "items", "remove-set", "test", "--item-set", "2", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── items import ─────────────────────────────────────────────────────────────


class TestItemsImport:
    def test_items_import(self, build_file):
        item_text = "Rarity: RARE\nTest Ring\nDiamond Ring\nImplicits: 0\n+90 to maximum Life\n"
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "import",
                "test",
                "--slot",
                "Ring 1",
                "--text",
                item_text,
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── items move ───────────────────────────────────────────────────────────────


class TestItemsMove:
    def test_items_move(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "move",
                "test",
                "--from",
                "Helmet",
                "--to",
                "Body Armour",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── items swap ───────────────────────────────────────────────────────────────


class TestItemsSwap:
    def test_items_swap(self, build_file):
        invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Body Armour",
                "--base",
                "Vaal Regalia",
                "--file",
                str(build_file),
            ],
        )
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "swap",
                "test",
                "--slot1",
                "Helmet",
                "--slot2",
                "Body Armour",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── items search ─────────────────────────────────────────────────────────────


class TestItemsSearch:
    def test_items_search(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "search",
                "test",
                "--mod",
                "Life",
                "--file",
                str(build_file),
                "--json",
            ],
        )
        assert result.exit_code == 0


# ── items compare ────────────────────────────────────────────────────────────


class TestItemsCompare:
    def test_items_compare_json(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "compare",
                "test",
                "--slot",
                "Helmet",
                "--file",
                str(build_file),
                "--json",
            ],
        )
        assert result.exit_code == 0


# ── jewels socket ────────────────────────────────────────────────────────────


class TestJewelsSocket:
    def test_jewels_socket(self, build_file):
        invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "add",
                "test",
                "--base",
                "Cobalt Jewel",
                "--slot",
                "Jewel 1",
                "--file",
                str(build_file),
            ],
        )
        result = invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "socket",
                "test",
                "--id",
                "2",
                "--node",
                "26725",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── jewels unsocket ──────────────────────────────────────────────────────────


class TestJewelsUnsocket:
    def test_jewels_unsocket(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "unsocket",
                "test",
                "--id",
                "1",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── jewels remove ────────────────────────────────────────────────────────────


class TestJewelsRemove:
    def test_jewels_remove_by_slot(self, build_file):
        invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "add",
                "test",
                "--base",
                "Cobalt Jewel",
                "--slot",
                "Jewel 1",
                "--file",
                str(build_file),
            ],
        )
        result = invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "remove",
                "test",
                "--slot",
                "Jewel 1",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0


# ── tree specs ───────────────────────────────────────────────────────────────


class TestTreeSpecs:
    def test_tree_specs(self):
        mock_svc = MagicMock()
        mock_svc.get_specs.return_value = [{"index": 1, "title": "Main", "active": True}]
        with patch("poe.commands.build.tree.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "tree", "specs", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


# ── tree get ─────────────────────────────────────────────────────────────────


class TestTreeGet:
    def test_tree_get(self):
        mock_svc = MagicMock()
        mock_svc.get_tree.return_value = {"nodes": [100, 200], "class_id": 5}
        with patch("poe.commands.build.tree.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "tree", "get", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)


# ── tree compare ─────────────────────────────────────────────────────────────


class TestTreeCompare:
    def test_tree_compare(self):
        mock_svc = MagicMock()
        mock_svc.compare_trees.return_value = {"shared": [100], "only_a": [200], "only_b": [300]}
        with patch("poe.commands.build.tree.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "tree", "compare", "a", "b", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "shared" in data


# ── tree set-active ──────────────────────────────────────────────────────────


class TestTreeSetActive:
    def test_tree_set_active(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "tree", "set-active", "test", "--spec", "1", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── tree add-spec ────────────────────────────────────────────────────────────


class TestTreeAddSpec:
    def test_tree_add_spec(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "tree", "add-spec", "test", "--title", "Alt", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── tree remove-spec ─────────────────────────────────────────────────────────


class TestTreeRemoveSpec:
    def test_tree_remove_spec(self, build_file):
        invoke_cli(
            cli,
            ["build", "tree", "add-spec", "test", "--title", "TempSpec", "--file", str(build_file)],
        )
        result = invoke_cli(
            cli,
            ["build", "tree", "remove-spec", "test", "--spec", "2", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── flasks list ─────────────────────────────────────────────────────────────


class TestFlasksList:
    def test_flasks_list(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "flasks", "list", "test", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── flasks remove ───────────────────────────────────────────────────────────


class TestFlasksRemove:
    def test_flasks_remove(self, build_file):
        invoke_cli(
            cli,
            [
                "build",
                "flasks",
                "add",
                "test",
                "--base",
                "Granite Flask",
                "--slot",
                "Flask 1",
                "--file",
                str(build_file),
            ],
        )
        result = invoke_cli(
            cli,
            ["build", "flasks", "remove", "test", "--slot", "Flask 1", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── gems list with skill_set ────────────────────────────────────────────────


class TestGemsListCoverage:
    def test_gems_list(self):
        from unittest.mock import patch

        mock_svc = MagicMock()
        mock_svc.list_gems.return_value = []
        with patch("poe.commands.build.gems.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "gems", "list", "test", "--json"])
        assert result.exit_code == 0


# ── jewels list ─────────────────────────────────────────────────────────────


class TestJewelsList:
    def test_jewels_list(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "jewels", "list", "test", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── config preset ───────────────────────────────────────────────────────────


class TestConfigPreset:
    def test_config_preset(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "config", "preset", "test", "--preset", "boss", "--file", str(build_file)],
        )
        assert result.exit_code == 0


# ── builds create: every Class enum value ─────────────────────────────────────


class TestBuildsCreateFullClassEnum:
    @pytest.mark.parametrize(
        "cls",
        ["Scion", "Marauder", "Ranger", "Witch", "Duelist", "Templar", "Shadow"],
    )
    def test_create_with_every_class(self, cls, tmp_path):
        out = tmp_path / f"{cls}.xml"
        result = invoke_cli(
            cli,
            ["build", "create", cls, "--class", cls, "--file", str(out)],
        )
        assert result.exit_code == 0
        build = parse_build_file(out)
        assert build.class_name == cls

    def test_create_unknown_class_rejected(self, tmp_path):
        out = tmp_path / "nope.xml"
        result = invoke_cli(
            cli, ["build", "create", "nope", "--class", "Wizard", "--file", str(out)]
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code != 0
        assert isinstance(result.exception, BuildValidationError)

    def test_create_class_ascendancy_mismatch_rejected(self, tmp_path):
        out = tmp_path / "nope.xml"
        result = invoke_cli(
            cli,
            [
                "build",
                "create",
                "nope",
                "--class",
                "Witch",
                "--ascendancy",
                "Slayer",
                "--file",
                str(out),
            ],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code != 0
        assert isinstance(result.exception, BuildValidationError)

    def test_create_level_below_one_rejected(self, tmp_path):
        out = tmp_path / "nope.xml"
        result = invoke_cli(
            cli,
            ["build", "create", "nope", "--level", "0", "--file", str(out)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code != 0
        assert isinstance(result.exception, BuildValidationError)

    def test_create_level_above_max_rejected(self, tmp_path):
        out = tmp_path / "nope.xml"
        result = invoke_cli(
            cli,
            ["build", "create", "nope", "--level", "200", "--file", str(out)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code != 0
        assert isinstance(result.exception, BuildValidationError)

    def test_create_invalid_name_rejected(self, tmp_path):
        out = tmp_path / "nope.xml"
        result = invoke_cli(
            cli,
            ["build", "create", "../escape", "--file", str(out)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code != 0
        assert isinstance(result.exception, BuildValidationError)


# ── items add invariants ──────────────────────────────────────────────────────


class TestItemsAddInvariants:
    def test_add_unknown_slot_raises_slot_error(self, build_file):
        from poe.exceptions import SlotError

        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Backpack",
                "--base",
                "Vaal Regalia",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0
        assert isinstance(result.exception, SlotError)

    def test_add_item_id_is_unique_and_increasing(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "add",
                "test",
                "--slot",
                "Ring 1",
                "--base",
                "Diamond Ring",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        ids = [i.id for i in build.items]
        assert len(ids) == len(set(ids))
        assert ids == sorted(ids)


# ── items edit rarity: enum + negative ───────────────────────────────────────


class TestItemsEditRarityEnum:
    @pytest.mark.parametrize("rarity", ["NORMAL", "MAGIC", "RARE", "UNIQUE", "RELIC"])
    def test_set_rarity_accepts_every_valid_rarity(self, rarity, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "edit",
                "test",
                "--slot",
                "Helmet",
                "--set-rarity",
                rarity,
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code == 0

    def test_set_rarity_rejects_invalid(self, build_file):
        from poe.exceptions import BuildValidationError

        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "edit",
                "test",
                "--slot",
                "Helmet",
                "--set-rarity",
                "LEGENDARY",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0
        assert isinstance(result.exception, BuildValidationError)


# ── items remove negative ─────────────────────────────────────────────────────


class TestItemsRemoveSlotError:
    def test_remove_unknown_slot_raises(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "remove",
                "test",
                "--slot",
                "Backpack",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── items move negative: same source and dest ────────────────────────────────


class TestItemsMoveNegative:
    def test_move_from_empty_slot_raises(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "items",
                "move",
                "test",
                "--from",
                "Belt",
                "--to",
                "Body Armour",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── config preset full enum ──────────────────────────────────────────────────


class TestConfigPresetFullEnum:
    @pytest.mark.parametrize("preset", ["mapping", "boss", "sirus", "shaper"])
    def test_every_preset_applies(self, preset, build_file):
        result = invoke_cli(
            cli,
            ["build", "config", "preset", "test", "--preset", preset, "--file", str(build_file)],
        )
        assert result.exit_code == 0

    def test_unknown_preset_rejected(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "config", "preset", "test", "--preset", "atlas", "--file", str(build_file)],
        )
        assert result.exit_code != 0


# ── tree set: spec selection bounds ──────────────────────────────────────────


class TestTreeSetNegative:
    def test_tree_set_invalid_spec_index_raises(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "tree",
                "set",
                "test",
                "--add-nodes",
                "999",
                "--spec",
                "999",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── tree set-active negative ─────────────────────────────────────────────────


class TestTreeSetActiveNegative:
    def test_tree_set_active_out_of_range(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "tree", "set-active", "test", "--spec", "999", "--file", str(build_file)],
        )
        assert result.exit_code != 0


# ── tree remove-spec: cannot remove last ─────────────────────────────────────


class TestTreeRemoveSpecNegative:
    def test_tree_remove_only_spec(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "tree", "remove-spec", "test", "--spec", "1", "--file", str(build_file)],
        )
        assert result.exit_code != 0


# ── flasks add negative: invalid slot ────────────────────────────────────────


class TestFlasksAddNegative:
    def test_flasks_add_invalid_slot_raises(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "flasks",
                "add",
                "test",
                "--base",
                "Granite Flask",
                "--slot",
                "Flask 99",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── jewels add negative: invalid base ────────────────────────────────────────


class TestJewelsAddNegative:
    def test_jewels_add_invalid_base_raises(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "jewels",
                "add",
                "test",
                "--base",
                "NotAJewel",
                "--slot",
                "Jewel 1",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── gems remove negative: skill set bounds ───────────────────────────────────


class TestGemsRemoveSetNegative:
    def test_gems_remove_unknown_set(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "gems",
                "remove-set",
                "test",
                "--skill-set",
                "999",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── config switch-set negative ───────────────────────────────────────────────


class TestConfigSwitchSetNegative:
    def test_switch_to_unknown_set(self, build_file):
        result = invoke_cli(
            cli,
            [
                "build",
                "config",
                "switch-set",
                "test",
                "--config-set",
                "999",
                "--file",
                str(build_file),
            ],
        )
        assert result.exit_code != 0


# ── notes invariants: empty round-trip ───────────────────────────────────────


class TestNotesRoundTrip:
    def test_set_then_get_preserves_text(self, build_file):
        text = "multi-line\nnotes with special: chars"
        invoke_cli(
            cli,
            ["build", "notes", "test", "--set", text, "--file", str(build_file)],
        )
        result = invoke_cli(
            cli,
            ["build", "notes", "test", "--file", str(build_file), "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["notes"].strip() == text.strip()

    def test_set_empty_notes(self, build_file):
        result = invoke_cli(
            cli,
            ["build", "notes", "test", "--set", "", "--file", str(build_file)],
        )
        assert result.exit_code == 0
        build = parse_build_file(build_file)
        assert build.notes.strip() == ""


# ── build name prefix matching via real builds_path ──────────────────────────


_PATCH_BUILDS = "poe.paths.get_builds_path"


class TestPrefixMatchingAnalyze:
    def test_unique_prefix_resolves_silently(self, tmp_path):
        from tests.conftest import MINIMAL_BUILD_XML

        (tmp_path / "lightning_strike.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(cli, ["build", "analyze", "lightning", "--json"])
        assert result.exit_code == 0

    def test_exact_name_wins_over_prefix(self, tmp_path):
        from tests.conftest import MINIMAL_BUILD_XML

        (tmp_path / "fire.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        (tmp_path / "fireball.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        (tmp_path / "firewall.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(cli, ["build", "analyze", "fire", "--json"])
        assert result.exit_code == 0

    def test_ambiguous_prefix_lists_matches(self, tmp_path):
        from poe.exceptions import BuildNotFoundError
        from tests.conftest import MINIMAL_BUILD_XML

        (tmp_path / "fireball.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        (tmp_path / "firewall.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(cli, ["build", "analyze", "fire"])
        assert result.exit_code != 0
        assert isinstance(result.exception, BuildNotFoundError)
        msg = str(result.exception)
        assert "Ambiguous prefix" in msg
        assert "fireball" in msg and "firewall" in msg


# ── List builds invariants ───────────────────────────────────────────────────


class TestBuildsListInvariants:
    def test_list_returns_array(self):
        mock_svc = MagicMock()
        mock_svc.list_builds.return_value = []
        with patch("poe.commands.build.commands._svc", return_value=mock_svc):
            result = invoke_cli(cli, ["build", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

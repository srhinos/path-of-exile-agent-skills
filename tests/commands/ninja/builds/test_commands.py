from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app
from poe.models.ninja.builds import (
    CharacterResponse,
    DefensiveStats,
    MetaSummary,
    TooltipResponse,
)
from poe.services.ninja.builds import BuildsService
from poe.services.ninja.discovery import DiscoveryService
from tests.conftest import invoke_cli

INDEX_STATE = {
    "economyLeagues": [{"name": "Mirage", "url": "mirage"}],
    "oldEconomyLeagues": [],
    "snapshotVersions": [
        {
            "url": "mirage",
            "type": "exp",
            "name": "Mirage",
            "timeMachineLabels": [],
            "version": "0309-20260316-12036",
            "snapshotName": "mirage",
            "overviewType": 0,
            "passiveTree": "PassiveTree-3.28",
            "atlasTree": "AtlasTree-3.28",
        },
    ],
    "buildLeagues": [],
    "oldBuildLeagues": [],
}

BUILD_INDEX_STATE = {
    "leagueBuilds": [
        {
            "leagueName": "Mirage",
            "leagueUrl": "mirage",
            "total": 124437,
            "status": 0,
            "statistics": [
                {
                    "class": "Pathfinder",
                    "skill": "Lightning Arrow",
                    "percentage": 4.53,
                    "trend": 1,
                },
                {
                    "class": "Necromancer",
                    "skill": "SRS",
                    "percentage": 3.21,
                    "trend": -1,
                },
                {
                    "class": "Champion",
                    "skill": "Boneshatter",
                    "percentage": 2.8,
                    "trend": 0,
                },
            ],
        },
    ],
}

POE1_CHARACTER = {
    "account": "TestAccount",
    "name": "TestChar",
    "league": "Mirage",
    "level": 98,
    "class": "Pathfinder",
    "baseClass": "Ranger",
    "ascendancyClassId": "Pathfinder",
    "ascendancyClassName": "Pathfinder",
    "secondaryAscendancyClassId": None,
    "secondaryAscendancyClassName": None,
    "defensiveStats": {
        "life": 5200,
        "energyShield": 0,
        "mana": 800,
        "evasionRating": 45000,
        "armour": 12000,
        "strength": 100,
        "dexterity": 300,
        "intelligence": 150,
        "fireResistance": 75,
        "coldResistance": 75,
        "lightningResistance": 75,
        "chaosResistance": 40,
        "blockChance": 0,
        "spellBlockChance": 0,
        "spellSuppressionChance": 100,
        "movementSpeed": 50,
    },
    "skills": [
        {
            "allGems": [
                {"name": "Lightning Arrow", "level": 21, "quality": 20, "isBuiltInSupport": False},
                {
                    "name": "Greater Multiple Projectiles",
                    "level": 21,
                    "quality": 20,
                    "isBuiltInSupport": True,
                },
            ],
            "dps": [{"name": "Lightning Arrow", "dps": 500000, "dotDps": 0}],
            "itemSlot": 1,
        },
    ],
    "items": [
        {
            "itemSlot": 10,
            "itemData": {
                "name": "Headhunter",
                "typeLine": "Leather Belt",
                "inventoryId": "Belt",
                "rarity": "unique",
                "implicitMods": ["+40 to maximum Life"],
                "explicitMods": ["Adds 1 to 4 Physical Damage to Attacks"],
            },
        },
    ],
    "flasks": [
        {
            "itemSlot": 1,
            "itemData": {
                "name": "Divine Life Flask",
                "typeLine": "Divine Life Flask",
                "explicitMods": ["Instant Recovery"],
            },
        },
    ],
    "jewels": [
        {
            "itemSlot": 1,
            "itemData": {
                "name": "Watcher's Eye",
                "typeLine": "Prismatic Jewel",
                "explicitMods": ["+50 to maximum Life"],
            },
        },
    ],
    "clusterJewels": [],
    "passiveSelection": [1, 2, 3, 100, 200],
    "passiveTreeName": "PassiveTree-3.28",
    "atlasTreeName": "AtlasTree-3.28",
    "keyStones": [{"name": "Acrobatics"}, {"name": "Phase Acrobatics"}],
    "masteries": [{"name": "Life Mastery", "group": "Life Mastery"}],
    "banditChoice": "Eramir",
    "pantheonMajor": "The Brine King",
    "pantheonMinor": "Shakari",
    "pathOfBuildingExport": "eNp9UVEK",
    "useSecondWeaponSet": False,
}

POE2_CHARACTER = {
    "account": "Poe2Account",
    "name": "Poe2Char",
    "league": "Fate of the Vaal",
    "level": 85,
    "class": "Blood Mage",
    "defensiveStats": {
        "life": 4000,
        "energyShield": 1500,
        "mana": 600,
        "spirit": 200,
        "evasionRating": 3000,
        "armour": 5000,
        "strength": 80,
        "dexterity": 80,
        "intelligence": 200,
        "fireResistance": 75,
        "coldResistance": 75,
        "lightningResistance": 75,
        "chaosResistance": 20,
        "blockChance": 30,
        "spellBlockChance": 20,
        "spellSuppressionChance": 0,
        "physicalMaximumHitTaken": 8000,
        "fireMaximumHitTaken": 6000,
        "coldMaximumHitTaken": 6000,
        "lightningMaximumHitTaken": 6000,
        "chaosMaximumHitTaken": 4000,
        "movementSpeed": 30,
        "itemRarity": 15,
    },
    "skills": [],
    "items": [],
    "flasks": [],
    "jewels": [],
    "keystones": [{"name": "Pain Attunement"}],
    "passives": [10, 20, 30],
    "pathOfBuildingExport": "eNp9ABCD",
}

TOOLTIP_RESPONSE = {
    "name": "Headhunter",
    "implicitMods": [{"text": "+40 to maximum Life", "optional": False}],
    "explicitMods": [
        {"text": "Adds 1 to 4 Physical Damage to Attacks", "optional": False},
    ],
    "mutatedMods": [],
}


def _make_service(tmp_path, fixture_map=None):
    client = MagicMock(no_cache=False)

    def get_json(path, **_kwargs):
        if fixture_map:
            for pattern, data in fixture_map.items():
                if pattern in path:
                    return data
        msg = f"Unmocked: {path}"
        raise ValueError(msg)

    client.get_json.side_effect = get_json
    discovery = DiscoveryService(client, base_dir=tmp_path)
    return BuildsService(client, discovery, base_dir=tmp_path)


class TestCharacterParsing:
    def test_poe1_character(self):
        resp = CharacterResponse.model_validate(POE1_CHARACTER)
        assert resp.name == "TestChar"
        assert resp.class_name == "Pathfinder"
        assert resp.level == 98
        assert resp.defensive_stats.life == 5200
        assert resp.defensive_stats.evasion_rating == 45000
        assert len(resp.skills) == 1
        assert resp.skills[0].all_gems[0].name == "Lightning Arrow"
        assert resp.skills[0].dps[0].name == "Lightning Arrow"
        assert resp.skills[0].item_slot == 1
        assert len(resp.items) == 1
        assert resp.items[0].item_data["name"] == "Headhunter"
        assert resp.items[0].item_slot == 10
        assert len(resp.keystones) == 2
        assert resp.bandit_choice == "Eramir"
        assert resp.pob_export == "eNp9UVEK"

    def test_poe2_character(self):
        resp = CharacterResponse.model_validate(POE2_CHARACTER)
        assert resp.name == "Poe2Char"
        assert resp.class_name == "Blood Mage"
        assert resp.level == 85
        assert resp.defensive_stats.spirit == 200
        assert resp.defensive_stats.physical_max_hit_taken == 8000
        assert resp.pob_export == "eNp9ABCD"

    def test_poe1_fields_absent_in_poe2(self):
        resp = CharacterResponse.model_validate(POE2_CHARACTER)
        assert resp.bandit_choice is None
        assert resp.pantheon_major is None
        assert resp.atlas_tree_name == ""

    def test_extra_fields_allowed(self):
        data = {**POE1_CHARACTER, "newField": "extra", "futureField": {"a": 1}}
        resp = CharacterResponse.model_validate(data)
        assert resp.name == "TestChar"


class TestDefensiveStats:
    def test_all_fields(self):
        ds = DefensiveStats.model_validate(POE1_CHARACTER["defensiveStats"])
        assert ds.life == 5200
        assert ds.fire_resistance == 75
        assert ds.spell_suppression_chance == 100
        assert ds.movement_speed == 50

    def test_poe2_specific_fields(self):
        ds = DefensiveStats.model_validate(POE2_CHARACTER["defensiveStats"])
        assert ds.spirit == 200
        assert ds.item_rarity == 15
        assert ds.physical_max_hit_taken == 8000


class TestTooltipParsing:
    def test_tooltip_response(self):
        resp = TooltipResponse.model_validate(TOOLTIP_RESPONSE)
        assert resp.name == "Headhunter"
        assert len(resp.implicit_mods) == 1
        assert resp.implicit_mods[0].text == "+40 to maximum Life"
        assert len(resp.explicit_mods) == 1
        assert resp.mutated_mods == []


class TestBuildsService:
    def test_get_character(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "index-state": INDEX_STATE,
                "/character": POE1_CHARACTER,
            },
        )
        result = svc.get_character("TestAccount", "TestChar")
        assert result is not None
        assert result.name == "TestChar"
        assert result.class_name == "Pathfinder"

    def test_get_character_no_snapshot(self, tmp_path):
        empty_state = {**INDEX_STATE, "snapshotVersions": []}
        svc = _make_service(tmp_path, {"index-state": empty_state})
        result = svc.get_character("TestAccount", "TestChar")
        assert result is None

    def test_get_tooltip(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "index-state": INDEX_STATE,
                "/tooltip": TOOLTIP_RESPONSE,
            },
        )
        result = svc.get_tooltip("headhunter")
        assert result is not None
        assert result.name == "Headhunter"

    def test_get_generic_tooltip(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "tooltip/any": TOOLTIP_RESPONSE,
            },
        )
        result = svc.get_generic_tooltip("Headhunter", "anointed")
        assert result is not None

    def test_get_meta_summary(self, tmp_path):
        svc = _make_service(
            tmp_path,
            {
                "build-index-state": BUILD_INDEX_STATE,
            },
        )
        result = svc.get_meta_summary()
        assert isinstance(result, MetaSummary)
        assert result.total_builds == 124437
        assert len(result.top_builds) == 3
        assert len(result.rising) == 1
        assert result.rising[0]["class"] == "Pathfinder"
        assert len(result.declining) == 1
        assert result.declining[0]["class"] == "Necromancer"


class TestBuildsCli:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_builds_inspect(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return INDEX_STATE
            if "/character" in path:
                return POE1_CHARACTER
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app, ["ninja", "builds", "inspect", "TestAccount", "TestChar", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "TestChar"
        assert data["class_name"] == "Pathfinder"


class TestMetaCli:
    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_meta_summary(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "build-index-state" in path:
                return BUILD_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "summary", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_builds"] == 124437
        assert len(data["rising"]) == 1

    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_meta_trend(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "build-index-state" in path:
                return BUILD_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "trend", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["league"] == "Mirage"


class TestBuildsSearchClassValidation:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_invalid_class_errors(self, mock_cls):
        from poe.models.ninja.builds import DimensionEntry, ResolvedDimension, SearchResults

        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        client.get_protobuf.return_value = SearchResults(
            total=100,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[
                        DimensionEntry(name="Necromancer", count=50, percentage=50.0),
                        DimensionEntry(name="Deadeye", count=50, percentage=50.0),
                    ],
                ),
            ],
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "search", "--class", "NonExistentClass123"])
        assert result.exit_code == 1


def _make_ninja_context_manager(client):
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__ = MagicMock(return_value=client)
    mock_cls.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cls


def _builds_client(fixture_map=None):
    client = MagicMock(no_cache=False)

    def get_json(path, **_kwargs):
        if fixture_map:
            for pattern, data in fixture_map.items():
                if pattern in path:
                    return data
        msg = f"Unmocked: {path}"
        raise ValueError(msg)

    client.get_json.side_effect = get_json
    return client


class TestBuildsInspectNotFound:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_inspect_not_found(self, mock_cls):
        empty_state = {**INDEX_STATE, "snapshotVersions": []}
        client = _builds_client({"index-state": empty_state})
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "inspect", "Account", "NoChar", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


class TestBuildsImportCli:
    @patch("poe.commands.ninja.builds.commands.decode_build")
    @patch("poe.commands.ninja.builds.commands.get_claude_builds_path")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_import_success(self, mock_cls, mock_claude_dir, mock_decode, tmp_path):
        mock_claude_dir.return_value = tmp_path
        mock_decode.return_value = "<PathOfBuilding/>"
        client = _builds_client(
            {
                "index-state": INDEX_STATE,
                "/character": POE1_CHARACTER,
            }
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app,
            ["ninja", "builds", "import", "TestAccount", "TestChar", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_import_not_found(self, mock_cls):
        empty_state = {**INDEX_STATE, "snapshotVersions": []}
        client = _builds_client({"index-state": empty_state})
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app,
            ["ninja", "builds", "import", "Account", "NoChar", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


class TestBuildsSearchCli:
    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_search_success(self, mock_ninja_cls, mock_builds_cls):
        from poe.models.ninja.builds import DimensionEntry, ResolvedDimension, SearchResults

        mock_svc = MagicMock()
        mock_svc.search.return_value = SearchResults(
            total=100,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[DimensionEntry(name="Necromancer", count=50, percentage=50.0)],
                ),
            ],
        )
        mock_builds_cls.return_value = mock_svc

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 100

    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_search_no_results(self, mock_ninja_cls, mock_builds_cls):
        mock_svc = MagicMock()
        mock_svc.search.return_value = None
        mock_builds_cls.return_value = mock_svc

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


class TestBuildsCompareCli:
    @patch("poe.commands.ninja.builds.commands.compare_to_meta")
    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_compare_success(self, mock_ninja_cls, mock_builds_cls, mock_compare):
        from poe.models.ninja.builds import DimensionEntry, ResolvedDimension, SearchResults

        char = CharacterResponse.model_validate(POE1_CHARACTER)
        mock_svc = MagicMock()
        mock_svc.get_character.return_value = char
        mock_svc.search.return_value = SearchResults(
            total=100,
            dimensions=[
                ResolvedDimension(
                    id="class",
                    entries=[DimensionEntry(name="Pathfinder", count=50, percentage=50.0)],
                ),
            ],
        )
        mock_builds_cls.return_value = mock_svc
        mock_compare.return_value = {"character": "TestChar", "diff": {}}

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app, ["ninja", "builds", "compare", "TestAccount", "TestChar", "--json"]
        )
        assert result.exit_code == 0

    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_compare_char_not_found(self, mock_ninja_cls, mock_builds_cls):
        mock_svc = MagicMock()
        mock_svc.get_character.return_value = None
        mock_builds_cls.return_value = mock_svc

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "compare", "Account", "NoChar", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data

    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_compare_no_meta_data(self, mock_ninja_cls, mock_builds_cls):
        char = CharacterResponse.model_validate(POE1_CHARACTER)
        mock_svc = MagicMock()
        mock_svc.get_character.return_value = char
        mock_svc.search.return_value = None
        mock_builds_cls.return_value = mock_svc

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app, ["ninja", "builds", "compare", "TestAccount", "TestChar", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


class TestBuildsSuggestUpgradeCli:
    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.DiscoveryService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_suggest_upgrade_char_not_found(self, mock_ninja_cls, mock_disc_cls, mock_builds_cls):
        mock_disc = MagicMock()
        mock_disc.get_current_league.return_value = MagicMock(name="Mirage")
        mock_disc_cls.return_value = mock_disc

        mock_svc = MagicMock()
        mock_svc.get_character.return_value = None
        mock_builds_cls.return_value = mock_svc

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app, ["ninja", "builds", "suggest-upgrade", "Account", "NoChar", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data

    @patch("poe.commands.ninja.builds.commands.DiscoveryService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_suggest_upgrade_no_league(self, mock_ninja_cls, mock_disc_cls):
        mock_disc = MagicMock()
        mock_disc.get_current_league.return_value = None
        mock_disc_cls.return_value = mock_disc

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app, ["ninja", "builds", "suggest-upgrade", "Account", "Char", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


class TestBuildsHeatmapCli:
    @patch("poe.commands.ninja.builds.commands.AtlasService")
    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_heatmap(self, mock_ninja_cls, mock_builds_cls, mock_atlas_cls):
        mock_atlas = MagicMock()
        mock_atlas.get_heatmap.return_value = [
            {"name": "Life Node", "count": 80, "percentage": 80.0, "zone": "mandatory"},
        ]
        mock_atlas_cls.return_value = mock_atlas

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "heatmap", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestBuildsImportDecodeError:
    @patch("poe.commands.ninja.builds.commands.decode_build")
    @patch("poe.commands.ninja.builds.commands.get_claude_builds_path")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_import_decode_error(self, mock_cls, mock_claude_dir, mock_decode, tmp_path):
        from poe.exceptions import CodecError

        mock_claude_dir.return_value = tmp_path
        mock_decode.side_effect = ValueError("bad decode")
        client = _builds_client(
            {
                "index-state": INDEX_STATE,
                "/character": POE1_CHARACTER,
            }
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app,
            ["ninja", "builds", "import", "TestAccount", "TestChar", "--json"],
        )
        assert result.exit_code == 1
        assert isinstance(result.exception, CodecError)


class TestBuildsSuggestUpgradeSuccess:
    @patch("poe.commands.ninja.builds.commands.find_budget_alternatives")
    @patch("poe.commands.ninja.builds.commands.cost_build")
    @patch("poe.commands.ninja.builds.commands.EconomyService")
    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.DiscoveryService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_suggest_upgrade_success(
        self,
        mock_ninja_cls,
        mock_disc_cls,
        mock_builds_cls,
        mock_econ_cls,
        mock_cost,
        mock_find,
    ):
        mock_disc = MagicMock()
        mock_disc.get_current_league.return_value = MagicMock(name="Mirage")
        mock_disc_cls.return_value = mock_disc

        char = CharacterResponse.model_validate(POE1_CHARACTER)
        mock_svc = MagicMock()
        mock_svc.get_character.return_value = char
        mock_builds_cls.return_value = mock_svc

        mock_cost.return_value = {"total": 100}
        mock_find.return_value = [{"slot": "Belt", "upgrade": "Mageblood"}]

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app,
            ["ninja", "builds", "suggest-upgrade", "TestAccount", "TestChar", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


# ── Added tests below ────────────────────────────────────────────────────────


class TestBuildsInspectHumanOutput:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_default_human_output(self, mock_cls):
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": POE1_CHARACTER},
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "inspect", "TestAccount", "TestChar"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json
        assert "TestChar" in result.output


class TestBuildsInspectNoCacheFlag:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_no_cache_propagated(self, mock_cls):
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": POE1_CHARACTER},
        )
        client.no_cache = True
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(
            app,
            ["ninja", "builds", "inspect", "TestAccount", "TestChar", "--no-cache", "--json"],
        )
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True


class TestBuildsInspect404:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_inspect_character_returning_none(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "index-state" in path:
                return INDEX_STATE
            from poe.services.ninja.errors import NinjaError

            raise NinjaError("404")

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "inspect", "Account", "Ghost", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data
        assert "Ghost" in data["error"]


class TestBuildsImportInvalidName:
    @pytest.mark.parametrize(
        "bad_class_name",
        ["Bad/Class", "Bad\\Class", 'Bad"Class', "Bad:Class", "Bad|Class", "Bad*Class"],
    )
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_invalid_chars_in_class_name_rejected(self, mock_cls, bad_class_name, tmp_path):
        from poe.exceptions import BuildValidationError

        bad_char = {**POE1_CHARACTER, "class": bad_class_name}
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": bad_char},
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "poe.commands.ninja.builds.commands.get_claude_builds_path", return_value=tmp_path
        ):
            result = invoke_cli(
                app,
                ["ninja", "builds", "import", "TestAccount", "TestChar", "--json"],
            )

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)


class TestBuildsImportPathTraversalName:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_dot_dot_in_class_name_rejected(self, mock_cls, tmp_path):
        from poe.exceptions import BuildValidationError

        traversal_char = {**POE1_CHARACTER, "class": "..Pathfinder"}
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": traversal_char},
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "poe.commands.ninja.builds.commands.get_claude_builds_path", return_value=tmp_path
        ):
            result = invoke_cli(
                app,
                ["ninja", "builds", "import", "TestAccount", "TestChar", "--json"],
            )

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)


class TestBuildsImportNoPobExport:
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_missing_pob_export_returns_error(self, mock_cls, tmp_path):
        no_export_char = {**POE1_CHARACTER, "pathOfBuildingExport": ""}
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": no_export_char},
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "poe.commands.ninja.builds.commands.get_claude_builds_path", return_value=tmp_path
        ):
            result = invoke_cli(
                app,
                ["ninja", "builds", "import", "TestAccount", "TestChar", "--json"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data


class TestBuildsImportSuccessFile:
    @patch("poe.commands.ninja.builds.commands.decode_build")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_writes_xml_to_claude_dir(self, mock_cls, mock_decode, tmp_path):
        mock_decode.return_value = "<PathOfBuilding/>"
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": POE1_CHARACTER},
        )
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        target_dir = tmp_path / "claude_builds"
        target_dir.mkdir()
        with patch(
            "poe.commands.ninja.builds.commands.get_claude_builds_path", return_value=target_dir
        ):
            result = invoke_cli(
                app,
                ["ninja", "builds", "import", "TestAccount", "TestChar", "--json"],
            )
        assert result.exit_code == 0
        xml_files = list(target_dir.glob("*.xml"))
        assert len(xml_files) == 1
        assert xml_files[0].read_text(encoding="utf-8") == "<PathOfBuilding/>"


class TestBuildsImportNoCacheFlag:
    @patch("poe.commands.ninja.builds.commands.decode_build")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_no_cache_propagated(self, mock_cls, mock_decode, tmp_path):
        mock_decode.return_value = "<PathOfBuilding/>"
        client = _builds_client(
            {"index-state": INDEX_STATE, "/character": POE1_CHARACTER},
        )
        client.no_cache = True
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "poe.commands.ninja.builds.commands.get_claude_builds_path", return_value=tmp_path
        ):
            result = invoke_cli(
                app,
                ["ninja", "builds", "import", "Acc", "Char", "--no-cache", "--json"],
            )
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True


class TestMetaSummaryHumanOutput:
    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_meta_summary_default_human(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "build-index-state" in path:
                return BUILD_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "summary"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json


class TestMetaSummaryNoCache:
    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_meta_summary_no_cache(self, mock_cls):
        client = MagicMock(no_cache=True)

        def get_json(path, **_kwargs):
            if "build-index-state" in path:
                return BUILD_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "summary", "--no-cache", "--json"])
        assert result.exit_code == 0
        _, kwargs = mock_cls.call_args
        assert kwargs.get("no_cache") is True


class TestMetaTrendInvariants:
    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_trend_keys_consistent(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "build-index-state" in path:
                return BUILD_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "trend", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for entry in data:
            assert {"league", "total", "status", "top"} <= set(entry.keys())
            for top in entry["top"]:
                assert {"class", "skill", "percentage", "trend"} <= set(top.keys())


class TestMetaSummaryGameRouting:
    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_poe1_default_routing(self, mock_cls):
        client = MagicMock(no_cache=False)
        seen = []

        def get_json(path, **_kwargs):
            seen.append(path)
            return BUILD_INDEX_STATE

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "summary", "--game", "poe1", "--json"])
        assert result.exit_code == 0
        assert any("/poe1/" in p for p in seen)

    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_poe2_routing(self, mock_cls):
        client = MagicMock(no_cache=False)
        seen = []

        def get_json(path, **_kwargs):
            seen.append(path)
            return BUILD_INDEX_STATE

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "summary", "--game", "poe2", "--json"])
        assert result.exit_code == 0
        assert any("/poe2/" in p for p in seen)
        assert not any("/poe1/" in p for p in seen)


class TestMetaSummaryInvariants:
    @patch("poe.commands.ninja.meta.commands.NinjaClient")
    def test_rising_and_declining_partition_top(self, mock_cls):
        client = MagicMock(no_cache=False)

        def get_json(path, **_kwargs):
            if "build-index-state" in path:
                return BUILD_INDEX_STATE
            msg = f"Unmocked: {path}"
            raise ValueError(msg)

        client.get_json.side_effect = get_json
        mock_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "meta", "summary", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        rising_set = {b["class"] for b in data["rising"]}
        declining_set = {b["class"] for b in data["declining"]}
        assert rising_set.isdisjoint(declining_set)
        assert data["total_builds"] >= 0


class TestBuildsHeatmapHumanOutput:
    @patch("poe.commands.ninja.builds.commands.AtlasService")
    @patch("poe.commands.ninja.builds.commands.BuildsService")
    @patch("poe.commands.ninja.builds.commands.NinjaClient")
    def test_heatmap_default_human(self, mock_ninja_cls, mock_builds_cls, mock_atlas_cls):
        mock_atlas = MagicMock()
        mock_atlas.get_heatmap.return_value = [
            {"name": "Life Node", "count": 80, "percentage": 80.0, "zone": "mandatory"},
        ]
        mock_atlas_cls.return_value = mock_atlas

        client = MagicMock(no_cache=False)
        mock_ninja_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_ninja_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = invoke_cli(app, ["ninja", "builds", "heatmap"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json

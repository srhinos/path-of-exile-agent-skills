from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from poe.app import app
from poe.exceptions import BuildNotFoundError
from poe.models.build.build import (
    BuildComparison,
    BuildMetadata,
    MutationResult,
    ValidationResult,
)
from poe.models.build.stats import StatBlock
from poe.services.build.xml.codec import encode_build
from tests.conftest import MINIMAL_BUILD_XML, invoke_cli

_PATCH_BUILDS = "poe.paths.get_builds_path"
_PATCH_SVC = "poe.commands.build.commands._svc"


class TestEncodeNonexistent:
    def test_encode_nonexistent_build(self, tmp_path):
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "encode", "nonexistent_build_xyz"])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)


class TestOpenNonexistent:
    @pytest.mark.skipif(sys.platform != "win32", reason="poe build open requires Windows")
    def test_open_nonexistent_build(self, tmp_path):
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "open", "nonexistent_build_xyz"])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)


class TestConfigOptionsInterface:
    def test_accepts_build_name_without_error(self):
        result = invoke_cli(app, ["build", "config", "options", "SomeBuild"])
        assert "Unused Tokens" not in result.output


class TestDeleteJson:
    def test_delete_json(self):
        mock_svc = MagicMock()
        mock_svc.delete.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "delete", "test", "--confirm", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


class TestRenameJson:
    def test_rename_json(self):
        mock_svc = MagicMock()
        mock_svc.rename.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "rename", "old", "new", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


class TestDuplicateJson:
    def test_duplicate_json(self):
        mock_svc = MagicMock()
        mock_svc.duplicate.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "duplicate", "src", "dst", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


class TestImportBuild:
    @patch("poe.commands.build.commands.get_claude_builds_path")
    @patch("poe.commands.build.commands.fetch_build_code")
    @patch("poe.commands.build.commands.decode_build")
    def test_import_from_code(self, mock_decode, mock_fetch, mock_claude_dir, tmp_path):
        mock_decode.return_value = MINIMAL_BUILD_XML
        mock_claude_dir.return_value = tmp_path
        result = invoke_cli(app, ["build", "import", "eNp9UVEK", "--name", "imported", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["name"] == "imported"
        mock_fetch.assert_not_called()

    @patch("poe.commands.build.commands.get_claude_builds_path")
    @patch("poe.commands.build.commands.fetch_build_code")
    @patch("poe.commands.build.commands.decode_build")
    def test_import_from_url(self, mock_decode, mock_fetch, mock_claude_dir, tmp_path):
        mock_fetch.return_value = "eNp9UVEK"
        mock_decode.return_value = MINIMAL_BUILD_XML
        mock_claude_dir.return_value = tmp_path
        result = invoke_cli(
            app,
            ["build", "import", "https://pobb.in/abc", "--name", "imported", "--json"],
        )
        assert result.exit_code == 0
        mock_fetch.assert_called_once()


class TestSetLevel:
    def test_set_level(self):
        mock_svc = MagicMock()
        mock_svc.set_level.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-level", "test", "--level", "95", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        mock_svc.set_level.assert_called_once_with("test", 95, file_path=None)


class TestSetClass:
    def test_set_class(self):
        mock_svc = MagicMock()
        mock_svc.set_class.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                app,
                ["build", "set-class", "test", "--class", "Witch", "--ascendancy", "Necromancer"],
            )
        assert result.exit_code == 0


class TestSetBandit:
    def test_set_bandit(self):
        mock_svc = MagicMock()
        mock_svc.set_bandit.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-bandit", "test", "--bandit", "Alira"])
        assert result.exit_code == 0


class TestSetPantheon:
    def test_set_pantheon(self):
        mock_svc = MagicMock()
        mock_svc.set_pantheon.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                app,
                [
                    "build",
                    "set-pantheon",
                    "test",
                    "--major",
                    "The Brine King",
                    "--minor",
                    "Shakari",
                ],
            )
        assert result.exit_code == 0


class TestSetMainSkill:
    def test_set_main_skill(self):
        mock_svc = MagicMock()
        mock_svc.set_main_skill.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-main-skill", "test", "--index", "2"])
        assert result.exit_code == 0
        mock_svc.set_main_skill.assert_called_once_with("test", 2, file_path=None)


class TestBatchSetLevel:
    def test_batch_set_level(self):
        mock_svc = MagicMock()
        mock_svc.set_level.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                app,
                ["build", "batch-set-level", "--level", "100", "--build", "a", "--build", "b"],
            )
        assert result.exit_code == 0
        assert mock_svc.set_level.call_count == 2

    def test_batch_set_level_partial_failure(self):
        mock_svc = MagicMock()
        mock_svc.set_level.side_effect = [
            MutationResult(status="ok"),
            BuildNotFoundError("not found"),
        ]
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                app,
                [
                    "build",
                    "batch-set-level",
                    "--level",
                    "100",
                    "--build",
                    "a",
                    "--build",
                    "b",
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["status"] == "ok"
        assert data[1]["status"] == "error"


class TestCompare:
    def test_compare(self):
        mock_svc = MagicMock()
        mock_svc.compare.return_value = BuildComparison(
            build1=BuildMetadata(name="a", class_name="Witch", level=90),
            build2=BuildMetadata(name="b", class_name="Ranger", level=95),
        )
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "compare", "a", "b", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["build1"]["name"] == "a"
        assert data["build2"]["name"] == "b"


class TestValidate:
    def test_validate(self):
        mock_svc = MagicMock()
        mock_svc.validate.return_value = ValidationResult(build="test", issues=[], issue_count=0)
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "validate", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["build"] == "test"
        assert data["issue_count"] == 0


class TestEncode:
    def test_encode_existing_build(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "encode", "test", "--file", str(f), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert "code" in data


class TestDecode:
    def test_decode_from_code(self):
        code = encode_build(MINIMAL_BUILD_XML)
        result = invoke_cli(app, ["build", "decode", code, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "xml" in data

    @patch("poe.commands.build.commands.get_claude_builds_path")
    def test_decode_with_save(self, mock_claude_dir, tmp_path):
        mock_claude_dir.return_value = tmp_path
        code = encode_build(MINIMAL_BUILD_XML)
        result = invoke_cli(app, ["build", "decode", code, "--save", "decoded", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "saved_to" in data
        assert (tmp_path / "decoded.xml").exists()

    def test_decode_from_file(self, tmp_path):
        code = encode_build(MINIMAL_BUILD_XML)
        code_file = tmp_path / "code.txt"
        code_file.write_text(code, encoding="utf-8")
        result = invoke_cli(app, ["build", "decode", "--file", str(code_file), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "xml" in data


class TestShare:
    def test_share(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "share", "test", "--file", str(f), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert "code" in data

    def test_share_not_found(self, tmp_path):
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "share", "nonexistent"])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)


class TestOpen:
    @pytest.mark.skipif(sys.platform != "win32", reason="poe build open requires Windows")
    @patch("poe.commands.build.commands.os.startfile")
    def test_open_success(self, mock_startfile, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "open", "test", "--file", str(f)])
        assert result.exit_code == 0
        mock_startfile.assert_called_once()


class TestAnalyzeJson:
    def test_analyze_json(self):
        mock_svc = MagicMock()
        mock_svc.analyze.return_value = {"class_name": "Witch", "level": 90}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "analyze", "test", "--json"])
        assert result.exit_code == 0


class TestStatsJson:
    def test_stats_json(self):
        mock_svc = MagicMock()
        mock_svc.stats.return_value = StatBlock(
            category="all",
            stats={"Life": 5000, "TotalDPS": 100000},
        )
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "stats", "test", "--json"])
        assert result.exit_code == 0


class TestListJson:
    def test_list_json(self):
        mock_svc = MagicMock()
        mock_svc.list_builds.return_value = []
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "list", "--json"])
        assert result.exit_code == 0


class TestExportJson:
    def test_export_json(self, tmp_path):
        mock_svc = MagicMock()
        mock_svc.export.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(
                app, ["build", "export", "test", str(tmp_path / "out.xml"), "--json"]
            )
        assert result.exit_code == 0


class TestSummaryJson:
    def test_summary_json(self):
        mock_svc = MagicMock()
        mock_svc.summary.return_value = {"class_name": "Witch", "level": 90}
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "summary", "test", "--json"])
        assert result.exit_code == 0


class TestDecodeNoCode:
    def test_decode_empty_code_errors(self):
        result = invoke_cli(app, ["build", "decode", ""])
        assert result.exit_code == 1
        from poe.exceptions import CodecError

        assert isinstance(result.exception, CodecError)


class TestDecodeInvalidCode:
    def test_decode_invalid_code_errors(self):
        result = invoke_cli(app, ["build", "decode", "!!!NOT_VALID_BASE64!!!"])
        assert result.exit_code == 1
        from poe.exceptions import CodecError

        assert isinstance(result.exception, CodecError)


class TestDecodeSaveInvalidXml:
    @patch("poe.commands.build.commands.get_claude_builds_path")
    @patch("poe.commands.build.commands.decode_build")
    def test_decode_save_invalid_xml(self, mock_decode, mock_claude_dir, tmp_path):
        mock_decode.return_value = "not valid xml <><>"
        mock_claude_dir.return_value = tmp_path
        result = invoke_cli(app, ["build", "decode", "somecode", "--save", "test"])
        assert result.exit_code == 1
        from poe.exceptions import CodecError

        assert isinstance(result.exception, CodecError)


class TestOpenNonWindows:
    @pytest.mark.skipif(sys.platform == "win32", reason="only runs on non-Windows")
    def test_open_non_windows(self):
        from poe.exceptions import PoeError

        result = invoke_cli(app, ["build", "open", "test"])
        assert result.exit_code == 1
        assert isinstance(result.exception, PoeError)


class TestImportInvalidDecode:
    @patch("poe.commands.build.commands.get_claude_builds_path")
    @patch("poe.commands.build.commands.decode_build")
    def test_import_invalid_decode(self, mock_decode, mock_claude_dir, tmp_path):
        mock_decode.side_effect = ValueError("bad code")
        mock_claude_dir.return_value = tmp_path
        result = invoke_cli(app, ["build", "import", "badcode", "--name", "test"])
        assert result.exit_code == 1
        from poe.exceptions import CodecError

        assert isinstance(result.exception, CodecError)

    @patch("poe.commands.build.commands.get_claude_builds_path")
    @patch("poe.commands.build.commands.decode_build")
    def test_import_invalid_xml(self, mock_decode, mock_claude_dir, tmp_path):
        mock_decode.return_value = "not xml <><>"
        mock_claude_dir.return_value = tmp_path
        result = invoke_cli(app, ["build", "import", "somecode", "--name", "test"])
        assert result.exit_code == 1
        from poe.exceptions import CodecError

        assert isinstance(result.exception, CodecError)


# ── set-class negative paths ─────────────────────────────────────────────────


class TestSetClassNegative:
    def test_set_class_mismatched_class_and_ascendancy(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            [
                "build",
                "set-class",
                "test",
                "--class",
                "Witch",
                "--ascendancy",
                "Slayer",
                "--file",
                str(f),
            ],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)
        assert "does not belong" in str(result.exception)

    def test_set_class_missing_both_args(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "set-class", "test", "--file", str(f)])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)

    def test_set_class_unknown_class(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "set-class", "test", "--class", "Wizard", "--file", str(f)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)
        assert "Unknown class" in str(result.exception)

    def test_set_class_unknown_ascendancy(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "set-class", "test", "--ascendancy", "TimeMage", "--file", str(f)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)
        assert "Unknown ascendancy" in str(result.exception)


# ── set-class full enum coverage ─────────────────────────────────────────────


_VALID_CLASS_ASCENDANCY_PAIRS = [
    ("Scion", "Ascendant"),
    ("Marauder", "Juggernaut"),
    ("Marauder", "Berserker"),
    ("Marauder", "Chieftain"),
    ("Ranger", "Raider"),
    ("Ranger", "Deadeye"),
    ("Ranger", "Pathfinder"),
    ("Ranger", "Warden"),
    ("Witch", "Necromancer"),
    ("Witch", "Elementalist"),
    ("Witch", "Occultist"),
    ("Witch", "Reliquarian"),
    ("Duelist", "Slayer"),
    ("Duelist", "Gladiator"),
    ("Duelist", "Champion"),
    ("Templar", "Inquisitor"),
    ("Templar", "Hierophant"),
    ("Templar", "Guardian"),
    ("Shadow", "Assassin"),
    ("Shadow", "Trickster"),
    ("Shadow", "Saboteur"),
]


class TestSetClassFullEnum:
    @pytest.mark.parametrize(("cls", "asc"), _VALID_CLASS_ASCENDANCY_PAIRS)
    def test_every_class_ascendancy_pair_is_accepted(self, cls, asc, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            [
                "build",
                "set-class",
                "test",
                "--class",
                cls,
                "--ascendancy",
                asc,
                "--file",
                str(f),
            ],
        )
        assert result.exit_code == 0


# ── set-bandit negative + full enum ──────────────────────────────────────────


class TestSetBanditNegative:
    def test_set_bandit_invalid(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app, ["build", "set-bandit", "test", "--bandit", "Eramir", "--file", str(f)]
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)
        assert "Unknown bandit" in str(result.exception)


class TestSetBanditFullEnum:
    @pytest.mark.parametrize("bandit", ["None", "Alira", "Kraityn", "Oak"])
    def test_every_bandit_value_is_accepted(self, bandit, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app, ["build", "set-bandit", "test", "--bandit", bandit, "--file", str(f)]
        )
        assert result.exit_code == 0


# ── set-pantheon negative + full enum ────────────────────────────────────────


class TestSetPantheonNegative:
    def test_set_pantheon_invalid_major(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "set-pantheon", "test", "--major", "Bogus God", "--file", str(f)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)
        assert "Unknown major pantheon" in str(result.exception)

    def test_set_pantheon_invalid_minor(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "set-pantheon", "test", "--minor", "Bogus Soul", "--file", str(f)],
        )
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)
        assert "Unknown minor pantheon" in str(result.exception)


_PANTHEON_MAJORS = [
    "Brine King",
    "Lunaris",
    "Solaris",
    "Arakaali",
    "Soul of the Brine King",
    "Soul of Lunaris",
    "Soul of Solaris",
    "Soul of Arakaali",
]

_PANTHEON_MINORS = [
    "Abberath",
    "Garukhan",
    "Gruthkul",
    "Yugul",
    "Shakari",
    "Tukohama",
    "Ralakesh",
    "Ryslatha",
    "Soul of Abberath",
    "Soul of Garukhan",
    "Soul of Gruthkul",
    "Soul of Yugul",
    "Soul of Shakari",
    "Soul of Tukohama",
    "Soul of Ralakesh",
    "Soul of Ryslatha",
]


class TestSetPantheonFullEnum:
    @pytest.mark.parametrize("major", _PANTHEON_MAJORS)
    def test_every_major_pantheon_is_accepted(self, major, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "set-pantheon", "test", "--major", major, "--file", str(f)],
        )
        assert result.exit_code == 0

    @pytest.mark.parametrize("minor", _PANTHEON_MINORS)
    def test_every_minor_pantheon_is_accepted(self, minor, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "set-pantheon", "test", "--minor", minor, "--file", str(f)],
        )
        assert result.exit_code == 0


# ── decode/encode/share round-trip preservation ──────────────────────────────


class TestEncodeShareRoundTrip:
    def test_encode_then_decode_preserves_xml(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "encode", "test", "--file", str(f), "--json"])
        assert result.exit_code == 0
        code = json.loads(result.output)["code"]
        decode_result = invoke_cli(app, ["build", "decode", code, "--json"])
        assert decode_result.exit_code == 0
        decoded_xml = json.loads(decode_result.output)["xml"]
        assert decoded_xml == MINIMAL_BUILD_XML

    def test_share_then_decode_preserves_xml(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        share_result = invoke_cli(app, ["build", "share", "test", "--file", str(f), "--json"])
        assert share_result.exit_code == 0
        code = json.loads(share_result.output)["code"]
        decode_result = invoke_cli(app, ["build", "decode", code, "--json"])
        assert decode_result.exit_code == 0
        decoded_xml = json.loads(decode_result.output)["xml"]
        assert decoded_xml == MINIMAL_BUILD_XML

    def test_share_and_encode_produce_same_code(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        share_result = invoke_cli(app, ["build", "share", "test", "--file", str(f), "--json"])
        encode_result = invoke_cli(app, ["build", "encode", "test", "--file", str(f), "--json"])
        assert share_result.exit_code == 0
        assert encode_result.exit_code == 0
        share_code = json.loads(share_result.output)["code"]
        encode_code = json.loads(encode_result.output)["code"]
        assert share_code == encode_code


# ── decode --save name validation ────────────────────────────────────────────


class TestDecodeSaveNameValidation:
    def test_decode_save_rejects_path_traversal_name(self, tmp_path):
        code = encode_build(MINIMAL_BUILD_XML)
        result = invoke_cli(app, ["build", "decode", code, "--save", "../escape"])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)

    def test_decode_save_rejects_slash_in_name(self, tmp_path):
        code = encode_build(MINIMAL_BUILD_XML)
        result = invoke_cli(app, ["build", "decode", code, "--save", "foo/bar"])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)


# ── import name validation ───────────────────────────────────────────────────


class TestImportNameValidation:
    def test_import_rejects_path_traversal_name(self):
        result = invoke_cli(app, ["build", "import", "anycode", "--name", "../etc/passwd"])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)

    def test_import_rejects_empty_name(self):
        result = invoke_cli(app, ["build", "import", "anycode", "--name", "  "])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)


# ── import URL fetch errors ──────────────────────────────────────────────────


class TestImportFetchErrors:
    @patch("poe.commands.build.commands.fetch_build_code")
    def test_import_url_fetch_error_propagates(self, mock_fetch):
        import httpx

        mock_fetch.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        result = invoke_cli(app, ["build", "import", "https://pobb.in/abc", "--name", "imported"])
        # httpx exceptions are not caught by import handler, so they propagate uncaught.
        assert result.exit_code == 1


# ── --json flag handling on mutation commands ────────────────────────────────


class TestDeleteHumanOutput:
    def test_delete_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.delete.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "delete", "test", "--confirm"])
        assert result.exit_code == 0
        assert "status: ok" in result.output


class TestRenameHumanOutput:
    def test_rename_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.rename.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "rename", "old", "new"])
        assert result.exit_code == 0
        assert "status: ok" in result.output


class TestDuplicateHumanOutput:
    def test_duplicate_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.duplicate.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "duplicate", "src", "dst"])
        assert result.exit_code == 0
        assert "status: ok" in result.output


class TestSetLevelHumanOutput:
    def test_set_level_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.set_level.return_value = MutationResult(status="ok")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-level", "test", "--level", "95"])
        assert result.exit_code == 0
        assert "status: ok" in result.output


class TestSetBanditHumanOutput:
    def test_set_bandit_without_json_prints_human(self):
        mock_svc = MagicMock()
        mock_svc.set_bandit.return_value = MutationResult(status="ok", bandit="Alira")
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-bandit", "test", "--bandit", "Alira"])
        assert result.exit_code == 0
        assert "status: ok" in result.output


# ── MutationResult JSON shape with cloned_from ───────────────────────────────


class TestMutationResultCloneShape:
    def test_set_level_json_includes_clone_fields(self):
        mock_svc = MagicMock()
        mock_svc.set_level.return_value = MutationResult(
            status="ok",
            level=95,
            cloned_from="/orig/path.xml",
            working_copy="/Claude/path.xml",
        )
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-level", "test", "--level", "95", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cloned_from"] == "/orig/path.xml"
        assert data["working_copy"] == "/Claude/path.xml"
        assert data["status"] == "ok"

    def test_set_level_no_clone_omits_clone_fields(self):
        mock_svc = MagicMock()
        mock_svc.set_level.return_value = MutationResult(status="ok", level=95)
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "set-level", "test", "--level", "95", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "cloned_from" not in data
        assert "working_copy" not in data


# ── Build-name prefix matching ───────────────────────────────────────────────


class TestPrefixMatching:
    def test_exact_match_wins_over_prefix(self, tmp_path):
        (tmp_path / "fire.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        (tmp_path / "fireball.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "encode", "fire", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_unique_prefix_resolves(self, tmp_path):
        (tmp_path / "lightning_arrow.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "encode", "lightning", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_ambiguous_prefix_raises_with_match_list(self, tmp_path):
        (tmp_path / "fireball.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        (tmp_path / "firewall.xml").write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "analyze", "fire"])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)
        msg = str(result.exception)
        assert "Ambiguous prefix" in msg
        assert "fireball" in msg
        assert "firewall" in msg

    def test_no_match_raises_not_found(self, tmp_path):
        with patch(_PATCH_BUILDS, return_value=tmp_path):
            result = invoke_cli(app, ["build", "analyze", "missing"])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)


# ── Hardcoded json_mode=True bug-catchers ────────────────────────────────────


class TestHardcodedJsonModeBugs:
    """Some mutation commands hardcode json_mode=True and ignore the lack of --json.

    Per CLAUDE.md, all commands should default to human output and only switch to
    JSON when --json is set. These tests document the gap.
    """

    @pytest.mark.xfail(strict=True, reason="tree set hardcodes json_mode=True")
    def test_tree_set_outputs_human_by_default(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            ["build", "tree", "set", "test", "--add-nodes", "999", "--file", str(f)],
        )
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    @pytest.mark.xfail(strict=True, reason="items add hardcodes json_mode=True")
    def test_items_add_outputs_human_by_default(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
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
                str(f),
            ],
        )
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    @pytest.mark.xfail(strict=True, reason="items edit hardcodes json_mode=True")
    def test_items_edit_outputs_human_by_default(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            [
                "build",
                "items",
                "edit",
                "test",
                "--slot",
                "Helmet",
                "--set-quality",
                "30",
                "--file",
                str(f),
            ],
        )
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    @pytest.mark.xfail(strict=True, reason="gems add hardcodes json_mode=True")
    def test_gems_add_outputs_human_by_default(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            [
                "build",
                "gems",
                "add",
                "test",
                "--gem",
                "Fireball",
                "--file",
                str(f),
            ],
        )
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    @pytest.mark.xfail(strict=True, reason="gems edit hardcodes json_mode=True")
    def test_gems_edit_outputs_human_by_default(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            [
                "build",
                "gems",
                "edit",
                "test",
                "--group",
                "0",
                "--toggle",
                "Fireball",
                "--file",
                str(f),
            ],
        )
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    @pytest.mark.xfail(strict=True, reason="config set hardcodes json_mode=True")
    def test_config_set_outputs_human_by_default(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(
            app,
            [
                "build",
                "config",
                "set",
                "test",
                "--boolean",
                "usePowerCharges=true",
                "--file",
                str(f),
            ],
        )
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)


# ── --file path traversal bug-catcher ────────────────────────────────────────


class TestFilePathTraversalUnvalidated:
    def test_file_path_traversal_should_raise_validation_error(self, tmp_path):
        from poe.exceptions import BuildValidationError

        result = invoke_cli(
            app,
            [
                "build",
                "set-level",
                "test",
                "--level",
                "95",
                "--file",
                "../../etc/passwd",
            ],
        )
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)


# ── CLI argument coverage: name+rarity normalization ─────────────────────────


class TestSetLevelInvalidLevel:
    def test_set_level_zero_rejected(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "set-level", "test", "--level", "0", "--file", str(f)])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)

    def test_set_level_above_max_rejected(self, tmp_path):
        f = tmp_path / "test.xml"
        f.write_text(MINIMAL_BUILD_XML, encoding="utf-8")
        result = invoke_cli(app, ["build", "set-level", "test", "--level", "101", "--file", str(f)])
        from poe.exceptions import BuildValidationError

        assert result.exit_code == 1
        assert isinstance(result.exception, BuildValidationError)


# ── Compare invariant ────────────────────────────────────────────────────────


class TestCompareInvariants:
    def test_compare_json_contains_both_build_metadata_keys(self):
        mock_svc = MagicMock()
        mock_svc.compare.return_value = BuildComparison(
            build1=BuildMetadata(name="a", class_name="Witch", level=90),
            build2=BuildMetadata(name="b", class_name="Ranger", level=95),
        )
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "compare", "a", "b", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert set(data["build1"].keys()) >= {"name", "class_name", "level"}
        assert set(data["build2"].keys()) >= {"name", "class_name", "level"}


# ── Stats JSON invariant: numeric field types ────────────────────────────────


class TestStatsJsonInvariants:
    def test_stats_json_returns_dict_with_stats_field(self):
        mock_svc = MagicMock()
        mock_svc.stats.return_value = StatBlock(
            category="all",
            stats={"Life": 5000, "TotalDPS": 100000},
        )
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "stats", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "stats" in data
        assert data["stats"]["Life"] == 5000
        assert data["stats"]["TotalDPS"] == 100000


# ── Validate output invariant: issue_count agrees with len(issues) ──────────


class TestValidateInvariants:
    def test_validate_issue_count_matches_issues_length(self):
        from poe.models.build.build import ValidationIssue

        mock_svc = MagicMock()
        issues = [
            ValidationIssue(severity="critical", category="resists", message="missing fire"),
            ValidationIssue(severity="medium", category="life_pool", message="low hp"),
        ]
        mock_svc.validate.return_value = ValidationResult(
            build="test", issues=issues, issue_count=len(issues)
        )
        with patch(_PATCH_SVC, return_value=mock_svc):
            result = invoke_cli(app, ["build", "validate", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["issue_count"] == len(data["issues"])


# ── Encode --file nonexistent ────────────────────────────────────────────────


class TestEncodeFileNonexistent:
    def test_encode_file_not_found(self, tmp_path):
        result = invoke_cli(app, ["build", "encode", "test", "--file", str(tmp_path / "nope.xml")])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)


class TestShareFileNonexistent:
    def test_share_file_not_found(self, tmp_path):
        result = invoke_cli(app, ["build", "share", "test", "--file", str(tmp_path / "nope.xml")])
        assert result.exit_code == 1
        assert isinstance(result.exception, BuildNotFoundError)


# ── Decode --save round-trip preserves content ───────────────────────────────


class TestDecodeSaveRoundTrip:
    @patch("poe.commands.build.commands.get_claude_builds_path")
    def test_decode_save_preserves_xml_content(self, mock_claude_dir, tmp_path):
        mock_claude_dir.return_value = tmp_path
        code = encode_build(MINIMAL_BUILD_XML)
        result = invoke_cli(app, ["build", "decode", code, "--save", "rt", "--json"])
        assert result.exit_code == 0
        saved = (tmp_path / "rt.xml").read_text(encoding="utf-8")
        assert saved == MINIMAL_BUILD_XML

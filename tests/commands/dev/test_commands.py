from __future__ import annotations

import json
from unittest.mock import patch

from poe.app import app as cli
from tests.conftest import invoke_cli

_PATCH_PIPELINE = "poe.commands.dev.commands.RepoEPipeline"


_PATCH_VENDOR_DIR = "poe.commands.dev.commands.VENDOR_DIR"


class TestBuildData:
    def test_success(self, tmp_path):
        mock_results = {"base_items": 1024, "mods": 5000}
        with (
            patch(_PATCH_VENDOR_DIR, tmp_path),
            patch(_PATCH_PIPELINE) as mock_cls,
        ):
            mock_cls.return_value.build.return_value = mock_results
            result = invoke_cli(cli, ["dev", "build-data", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "built"
        assert "base_items" in data["files"]

    def test_exception(self, tmp_path):
        with (
            patch(_PATCH_VENDOR_DIR, tmp_path),
            patch(_PATCH_PIPELINE) as mock_cls,
        ):
            mock_cls.return_value.build.side_effect = FileNotFoundError("no vendor dir")
            result = invoke_cli(cli, ["dev", "build-data"])
        assert result.exit_code != 0

    def test_missing_vendor_dir(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with patch(_PATCH_VENDOR_DIR, missing):
            result = invoke_cli(cli, ["dev", "build-data"])
        assert result.exit_code != 0
        assert isinstance(result.exception, FileNotFoundError)
        assert "Vendor data not found" in str(result.exception)


class TestBuildDataJsonStructure:
    def test_json_output_has_status_field(self, tmp_path):
        with (
            patch(_PATCH_VENDOR_DIR, tmp_path),
            patch(_PATCH_PIPELINE) as mock_cls,
        ):
            mock_cls.return_value.build.return_value = {}
            result = invoke_cli(cli, ["dev", "build-data", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "built"
        assert "files" in data

    def test_json_output_files_have_byte_format(self, tmp_path):
        with (
            patch(_PATCH_VENDOR_DIR, tmp_path),
            patch(_PATCH_PIPELINE) as mock_cls,
        ):
            mock_cls.return_value.build.return_value = {"mods": 1234567}
            result = invoke_cli(cli, ["dev", "build-data", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["files"]["mods"] == "1,234,567 bytes"

    def test_human_output_no_json(self, tmp_path):
        with (
            patch(_PATCH_VENDOR_DIR, tmp_path),
            patch(_PATCH_PIPELINE) as mock_cls,
        ):
            mock_cls.return_value.build.return_value = {"mods": 100}
            result = invoke_cli(cli, ["dev", "build-data"])
        assert result.exit_code == 0
        assert "built" in result.output

    def test_help_works(self):
        result = invoke_cli(cli, ["dev", "build-data", "--help"])
        assert result.exit_code == 0

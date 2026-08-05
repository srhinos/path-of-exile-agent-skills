from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from poe.services.build.xml.codec import decode_build, encode_build, fetch_build_code


class TestEncodeDecode:
    def test_encode_decode_roundtrip(self):
        xml = "<PathOfBuilding><BuildDocument level='1'/></PathOfBuilding>"
        code = encode_build(xml)
        assert isinstance(code, str)
        assert len(code) > 0
        decoded = decode_build(code)
        assert decoded == xml

    def test_decode_handles_url_safe_chars(self):
        xml = "<PathOfBuilding><BuildDocument level='90'/></PathOfBuilding>"
        code = encode_build(xml)
        assert "+" not in code
        assert "/" not in code
        assert not code.endswith("=")
        decoded = decode_build(code)
        assert decoded == xml

    def test_decode_invalid_code(self):
        # decode_build can raise binascii.Error, zlib.error, or UnicodeDecodeError
        # depending on the failure mode. Tightening from raises(Exception) so a
        # refactor that switches to e.g. KeyError doesn't silently pass.
        import binascii
        import zlib

        with pytest.raises((binascii.Error, zlib.error, UnicodeDecodeError, ValueError)):
            decode_build("not-a-valid-code!!!")


class TestFetchBuildCode:
    def test_fetch_build_code_success(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "  some-code-here  "
            mock_get.return_value.raise_for_status = lambda: None
            result = fetch_build_code("https://pobb.in/abc123")
            assert result == "some-code-here"
            mock_get.assert_called_once_with(
                "https://pobb.in/raw/abc123",
                timeout=30,
                follow_redirects=True,
            )

    def test_fetch_build_code_extracts_id_from_url(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "code"
            mock_get.return_value.raise_for_status = lambda: None
            fetch_build_code("https://pobb.in/some/deep/path/XYZ123")
            mock_get.assert_called_once_with(
                "https://pobb.in/raw/XYZ123",
                timeout=30,
                follow_redirects=True,
            )

    def test_fetch_build_code_strips_trailing_slash(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "code"
            mock_get.return_value.raise_for_status = lambda: None
            fetch_build_code("https://pobb.in/ABC/")
            mock_get.assert_called_once_with(
                "https://pobb.in/raw/ABC",
                timeout=30,
                follow_redirects=True,
            )

    def test_fetch_build_code_custom_timeout(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "code"
            mock_get.return_value.raise_for_status = lambda: None
            fetch_build_code("https://pobb.in/X", timeout=5)
            mock_get.assert_called_once_with(
                "https://pobb.in/raw/X",
                timeout=5,
                follow_redirects=True,
            )


class TestDecodeBuildErrorPaths:
    @pytest.mark.parametrize(
        "bad_input",
        [
            "!!@#$%^",
            "not_base64$$$",
            "########",
            chr(0),
        ],
    )
    def test_decode_invalid_base64_raises(self, bad_input):
        import binascii
        import zlib

        with pytest.raises((binascii.Error, zlib.error, UnicodeDecodeError, ValueError)):
            decode_build(bad_input)

    def test_decode_truncated_input_raises(self):
        import binascii
        import zlib

        xml = "<PathOfBuilding/>"
        full = encode_build(xml)
        truncated = full[: len(full) // 2]
        with pytest.raises((binascii.Error, zlib.error, UnicodeDecodeError)):
            decode_build(truncated)

    def test_decode_valid_base64_invalid_zlib_raises(self):
        import base64
        import zlib

        garbage = base64.b64encode(b"this is not valid zlib data at all").decode("ascii")
        garbage = garbage.replace("+", "-").replace("/", "_").rstrip("=")
        with pytest.raises(zlib.error):
            decode_build(garbage)

    def test_decode_empty_string_raises(self):
        import binascii
        import zlib

        with pytest.raises((binascii.Error, zlib.error, UnicodeDecodeError, ValueError)):
            decode_build("")

    def test_decode_zlib_format_succeeds(self):
        import base64
        import zlib

        xml = "<PathOfBuilding level='1'/>"
        zlib_data = zlib.compress(xml.encode("utf-8"))
        code = base64.b64encode(zlib_data).decode("ascii")
        code = code.replace("+", "-").replace("/", "_").rstrip("=")
        result = decode_build(code)
        assert result == xml


class TestEncodeDecodeInvariants:
    @pytest.mark.parametrize(
        "xml",
        [
            "<PathOfBuilding/>",
            "<PathOfBuilding><Build level='1'/></PathOfBuilding>",
            "<PathOfBuilding><Build level='100' className='Witch'/></PathOfBuilding>",
            "<root>" + ("x" * 10000) + "</root>",
            "<root>unicode: éèê 中文 \U0001f600</root>",
        ],
    )
    def test_roundtrip_preserves_payload(self, xml):
        assert decode_build(encode_build(xml)) == xml

    def test_encoded_output_is_url_safe(self):
        xml = "<PathOfBuilding>" + ("a" * 1000) + "</PathOfBuilding>"
        code = encode_build(xml)
        assert "+" not in code
        assert "/" not in code
        assert not code.endswith("=")

    def test_encoded_output_is_ascii_only(self):
        xml = "<root>unicode 中文 payload</root>"
        code = encode_build(xml)
        assert code.isascii()


class TestFetchBuildCodePastebin:
    def test_pastebin_url_uses_raw_endpoint(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "abc"
            mock_get.return_value.raise_for_status = lambda: None
            fetch_build_code("https://pastebin.com/abc123")
            mock_get.assert_called_once_with(
                "https://pastebin.com/raw/abc123",
                timeout=30,
                follow_redirects=True,
            )

    def test_unknown_url_used_verbatim(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "code"
            mock_get.return_value.raise_for_status = lambda: None
            fetch_build_code("https://example.com/foo")
            mock_get.assert_called_once_with(
                "https://example.com/foo",
                timeout=30,
                follow_redirects=True,
            )

    def test_raises_on_http_error(self):
        with patch.object(httpx, "get") as mock_get:
            mock_get.return_value.text = "code"

            def boom():
                raise httpx.HTTPStatusError("404", request=None, response=None)

            mock_get.return_value.raise_for_status = boom
            with pytest.raises(httpx.HTTPStatusError):
                fetch_build_code("https://pobb.in/abc")

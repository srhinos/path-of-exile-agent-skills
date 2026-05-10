from __future__ import annotations

import pytest

from poe.exceptions import PoeError
from poe.services.ninja.errors import (
    ApiSchemaError,
    NetworkError,
    NinjaError,
    ProtobufDecodeError,
    RateLimitError,
    StaleDataError,
)


class TestErrorHierarchy:
    def test_ninja_error_is_poe_error(self):
        assert issubclass(NinjaError, PoeError)

    def test_all_errors_inherit_from_ninja_error(self):
        all_errors = [
            RateLimitError,
            StaleDataError,
            ProtobufDecodeError,
            ApiSchemaError,
            NetworkError,
        ]
        for cls in all_errors:
            assert issubclass(cls, NinjaError)
            assert issubclass(cls, PoeError)

    def test_catch_as_poe_error(self):
        with pytest.raises(PoeError):
            raise RateLimitError("too many requests")

    def test_catch_as_ninja_error(self):
        with pytest.raises(NinjaError):
            raise NetworkError("connection refused")

    def test_error_message(self):
        err = ApiSchemaError("unexpected format")
        assert str(err) == "unexpected format"


class TestNinjaErrorEnumCoverage:
    @pytest.mark.parametrize(
        "cls",
        [
            NinjaError,
            RateLimitError,
            StaleDataError,
            ProtobufDecodeError,
            ApiSchemaError,
            NetworkError,
        ],
    )
    def test_each_subclass_constructible_with_message(self, cls):
        err = cls("a message")
        assert str(err) == "a message"
        assert isinstance(err, NinjaError)

    @pytest.mark.parametrize(
        "cls",
        [RateLimitError, StaleDataError, ProtobufDecodeError, ApiSchemaError, NetworkError],
    )
    def test_each_subclass_can_be_raised_and_caught(self, cls):
        with pytest.raises(cls):
            raise cls("boom")

    @pytest.mark.parametrize(
        "cls",
        [RateLimitError, StaleDataError, ProtobufDecodeError, ApiSchemaError, NetworkError],
    )
    def test_each_subclass_caught_as_ninja_error(self, cls):
        with pytest.raises(NinjaError):
            raise cls("boom")


class TestNinjaErrorRaisedInProduction:
    def test_rate_limit_error_raised_in_client(self):
        # Verifies RateLimitError is reachable from production code.
        import httpx
        import respx

        from poe.services.ninja.client import NinjaClient, RateLimiter

        with respx.mock:
            respx.get("https://poe.ninja/x").mock(
                return_value=httpx.Response(429, text="rl"),
            )
            with NinjaClient(
                rate_limiter=RateLimiter(max_requests=100, window=1.0),
            ) as c:
                # Patch sleep to keep test fast.
                import poe.services.ninja.client as client_mod

                orig = client_mod.time.sleep
                client_mod.time.sleep = lambda _s: None
                try:
                    with pytest.raises(RateLimitError):
                        c.get_json("/x")
                finally:
                    client_mod.time.sleep = orig

    def test_api_schema_error_raised_in_client(self):
        import httpx
        import respx

        from poe.services.ninja.client import NinjaClient, RateLimiter

        with respx.mock:
            respx.get("https://poe.ninja/y").mock(
                return_value=httpx.Response(
                    200,
                    text="bad",
                    headers={"content-type": "application/octet-stream"},
                ),
            )
            with NinjaClient(
                rate_limiter=RateLimiter(max_requests=100, window=1.0),
            ) as c:
                with pytest.raises(ApiSchemaError):
                    c.get_json("/y")

    def test_network_error_raised_in_client(self):
        import httpx
        import respx

        from poe.services.ninja.client import NinjaClient, RateLimiter

        with respx.mock:
            respx.get("https://poe.ninja/z").mock(
                return_value=httpx.Response(500, text="boom"),
            )
            with NinjaClient(
                rate_limiter=RateLimiter(max_requests=100, window=1.0),
            ) as c:
                with pytest.raises(NetworkError):
                    c.get_json("/z")


class TestNinjaErrorDeadCode:
    def test_stale_data_error_is_not_raised_anywhere_in_production(self):
        # Documents that StaleDataError is currently dead code:
        # no production module raises it. If a future change starts using it,
        # this test should be updated to assert the new raise path is exercised.
        import re
        from pathlib import Path

        poe_dir = Path(__file__).resolve().parents[3] / "poe"
        offenders: list[str] = []
        for py in poe_dir.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            if re.search(r"\braise\s+StaleDataError\b", text):
                offenders.append(str(py))
        assert offenders == [], (
            "StaleDataError used to be dead code — production now raises it: "
            f"{offenders}. Update tests to assert the raise path."
        )

    def test_protobuf_decode_error_is_raised_on_truncated_payloads(self):
        """ProtobufDecodeError is now raised by decode_fields/decode_varint
        when a payload is truncated or has unknown wire types. This replaces
        the previous silent-break behavior that let garbage partially decode."""
        from poe.services.ninja.protobuf import (
            ProtobufDecodeError,
            decode_fields,
            decode_varint,
        )

        # Truncated varint mid-byte sequence (high bit set with no continuation).
        with pytest.raises(ProtobufDecodeError, match="truncated"):
            decode_varint(b"\xff", 0)

        # Length-delimited field whose declared length exceeds remaining bytes.
        with pytest.raises(ProtobufDecodeError, match="truncated"):
            decode_fields(b"\x0a\xff\x01" + b"too-short")


class TestNinjaErrorChaining:
    def test_chained_from_value_error(self):
        def _raise_root() -> None:
            raise ValueError("root cause")

        try:
            try:
                _raise_root()
            except ValueError as e:
                raise ApiSchemaError("schema mismatch") from e
        except ApiSchemaError as exc:
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)

    @pytest.mark.parametrize(
        "cls",
        [
            RateLimitError,
            StaleDataError,
            ProtobufDecodeError,
            ApiSchemaError,
            NetworkError,
        ],
    )
    def test_no_args_default_message(self, cls):
        err = cls()
        assert str(err) == ""

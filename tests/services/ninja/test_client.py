from __future__ import annotations

import httpx
import pytest
import respx

from poe.services.ninja.client import NinjaClient, RateLimiter
from poe.services.ninja.errors import ApiSchemaError, NetworkError, RateLimitError


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start
        self.slept: list[float] = []

    def time(self):
        return self._now

    def advance(self, seconds: float):
        self._now += seconds

    def sleep(self, seconds: float):
        self.slept.append(seconds)
        self._now += seconds


class TestRateLimiter:
    def test_allows_requests_under_limit(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=3, window=60.0, clock=clock)

        rl.acquire()
        rl.acquire()
        rl.acquire()
        assert len(clock.slept) == 0

    def test_blocks_when_limit_reached(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=2, window=60.0, clock=clock)

        rl.acquire()
        clock.advance(1.0)
        rl.acquire()
        clock.advance(1.0)
        rl.acquire()

        assert len(clock.slept) == 1
        assert clock.slept[0] > 0

    def test_window_expires(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=2, window=10.0, clock=clock)

        rl.acquire()
        clock.advance(1.0)
        rl.acquire()
        clock.advance(11.0)
        rl.acquire()

        assert len(clock.slept) == 0

    def test_callable_clock(self):
        calls = [0.0, 1.0, 2.0, 3.0, 4.0]
        idx = [0]

        def clock_fn():
            val = calls[idx[0]]
            idx[0] += 1
            return val

        rl = RateLimiter(max_requests=10, window=60.0, clock=clock_fn)
        rl.acquire()
        rl.acquire()


class TestNinjaClient:
    @respx.mock
    def test_get_json_success(self):
        respx.get("https://poe.ninja/test").mock(
            return_value=httpx.Response(
                200,
                json={"key": "value"},
                headers={"content-type": "application/json"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            result = c.get_json("/test")
        assert result == {"key": "value"}

    @respx.mock
    def test_get_json_text_content_type(self):
        respx.get("https://poe.ninja/test").mock(
            return_value=httpx.Response(
                200,
                text='{"key": "value"}',
                headers={"content-type": "text/plain"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            result = c.get_json("/test")
        assert result == {"key": "value"}

    @respx.mock
    def test_get_json_wrong_content_type(self):
        respx.get("https://poe.ninja/test").mock(
            return_value=httpx.Response(
                200,
                content=b"binary data",
                headers={"content-type": "application/x-protobuf"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match="Expected JSON"):
                c.get_json("/test")

    @respx.mock
    def test_get_protobuf_returns_bytes(self):
        respx.get("https://poe.ninja/proto").mock(
            return_value=httpx.Response(
                200,
                content=b"\x08\x01",
                headers={"content-type": "application/x-protobuf"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            result = c.get_protobuf("/proto")
        assert result == b"\x08\x01"

    @respx.mock
    def test_http_error_wraps_as_network_error(self):
        respx.get("https://poe.ninja/fail").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(NetworkError, match="HTTP 500"):
                c.get_json("/fail")

    @respx.mock
    def test_timeout_wraps_as_network_error(self):
        respx.get("https://poe.ninja/slow").mock(side_effect=httpx.ReadTimeout("timed out"))
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(NetworkError, match="timed out"):
                c.get_json("/slow")

    @respx.mock
    def test_connection_error_wraps(self):
        respx.get("https://poe.ninja/down").mock(
            side_effect=httpx.ConnectError("refused"),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(NetworkError, match="refused"):
                c.get_json("/down")

    @respx.mock
    def test_429_retries_then_succeeds(self):
        route = respx.get("https://poe.ninja/limited")
        route.side_effect = [
            httpx.Response(429, text="Rate limited"),
            httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"}),
        ]
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            result = c.get_json("/limited")
        assert result == {"ok": True}

    @respx.mock
    def test_429_exhausts_retries(self):
        respx.get("https://poe.ninja/forever429").mock(
            return_value=httpx.Response(429, text="Rate limited"),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(RateLimitError, match="after 3 retries"):
                c.get_json("/forever429")

    @respx.mock
    def test_oversized_response(self):
        big_data = b"x" * (50 * 1024 * 1024 + 1)
        respx.get("https://poe.ninja/big").mock(
            return_value=httpx.Response(
                200,
                content=big_data,
                headers={"content-type": "application/json"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match="exceeds"):
                c.get_json("/big")

    def test_context_manager(self):
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            assert c is not None

    @respx.mock
    def test_get_json_with_params(self):
        respx.get("https://poe.ninja/api", params={"league": "Mirage"}).mock(
            return_value=httpx.Response(
                200,
                json={"league": "Mirage"},
                headers={"content-type": "application/json"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            result = c.get_json("/api", params={"league": "Mirage"})
        assert result["league"] == "Mirage"

    @respx.mock
    def test_invalid_json_response(self):
        respx.get("https://poe.ninja/bad").mock(
            return_value=httpx.Response(
                200,
                text="not json {{{",
                headers={"content-type": "application/json"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match="Invalid JSON"):
                c.get_json("/bad")

    def test_external_http_client(self):
        ext_client = httpx.Client()
        nc = NinjaClient(
            http_client=ext_client,
            rate_limiter=RateLimiter(max_requests=100, window=1.0),
        )
        nc.close()
        assert not ext_client.is_closed
        ext_client.close()


class TestRateLimiterBoundaries:
    def test_exactly_at_limit_does_not_sleep(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=5, window=60.0, clock=clock)
        for _ in range(5):
            rl.acquire()
        assert clock.slept == []

    def test_one_over_limit_sleeps_exactly_once(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=3, window=60.0, clock=clock)
        for _ in range(3):
            rl.acquire()
        rl.acquire()
        assert len(clock.slept) == 1

    def test_records_correct_number_of_timestamps(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=5, window=60.0, clock=clock)
        for _ in range(5):
            rl.acquire()
        # Internal state invariant: after N acquires under limit, N timestamps tracked.
        assert len(rl._timestamps) == 5

    def test_old_timestamps_pruned_after_window(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=3, window=10.0, clock=clock)
        rl.acquire()
        rl.acquire()
        clock.advance(20.0)
        rl.acquire()
        # Two old timestamps should have been dropped.
        assert len(rl._timestamps) == 1

    def test_just_inside_window_still_counts(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=2, window=10.0, clock=clock)
        rl.acquire()
        # Advance just under the window — the first timestamp must still count.
        clock.advance(9.99)
        rl.acquire()
        clock.advance(0.0)
        rl.acquire()
        # The 3rd acquire should have triggered a sleep.
        assert len(clock.slept) == 1

    def test_just_outside_window_does_not_count(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=2, window=10.0, clock=clock)
        rl.acquire()
        clock.advance(10.01)
        rl.acquire()
        rl.acquire()
        # First timestamp expired before the third acquire — no sleep.
        assert len(clock.slept) == 0

    def test_default_constants_used_when_no_args(self):
        from poe.services.ninja.constants import (
            NINJA_RATE_LIMIT_REQUESTS,
            NINJA_RATE_LIMIT_WINDOW,
        )

        rl = RateLimiter(clock=FakeClock())
        assert rl._max_requests == NINJA_RATE_LIMIT_REQUESTS
        assert rl._window == NINJA_RATE_LIMIT_WINDOW

    def test_window_invariant_no_timestamp_older_than_window_after_acquire(self):
        clock = FakeClock(start=1000.0)
        rl = RateLimiter(max_requests=10, window=5.0, clock=clock)
        for _ in range(5):
            rl.acquire()
            clock.advance(1.5)
        # Triggering one more acquire prunes old timestamps. After it, every
        # remaining timestamp must be within the window of "now".
        rl.acquire()
        now = clock.time()
        for ts in rl._timestamps:
            assert now - ts <= 5.0 + 1e-9


class TestNinjaClientBaseUrlInvariant:
    def test_trailing_slash_stripped(self):
        c = NinjaClient(
            base_url="https://poe.ninja/",
            rate_limiter=RateLimiter(max_requests=100, window=1.0),
        )
        assert c._base_url == "https://poe.ninja"
        c.close()

    def test_no_trailing_slash_preserved(self):
        c = NinjaClient(
            base_url="https://example.com",
            rate_limiter=RateLimiter(max_requests=100, window=1.0),
        )
        assert c._base_url == "https://example.com"
        c.close()


class TestNinjaClientErrorPaths:
    @respx.mock
    def test_http_400_raises_network_error(self):
        respx.get("https://poe.ninja/notfound").mock(
            return_value=httpx.Response(404, text="Not Found"),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(NetworkError, match="HTTP 404"):
                c.get_json("/notfound")

    @respx.mock
    def test_http_400_truncates_body_in_message(self):
        big_text = "x" * 5000
        respx.get("https://poe.ninja/big400").mock(
            return_value=httpx.Response(400, text=big_text),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(NetworkError) as exc_info:
                c.get_json("/big400")
        # Body is truncated to 200 chars in the error message.
        assert len(str(exc_info.value)) < 500

    @respx.mock
    def test_apiscma_error_message_includes_path(self):
        respx.get("https://poe.ninja/wctype").mock(
            return_value=httpx.Response(
                200,
                content=b"data",
                headers={"content-type": "application/octet-stream"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match="/wctype"):
                c.get_json("/wctype")

    @respx.mock
    def test_api_schema_error_invalid_json_includes_path(self):
        respx.get("https://poe.ninja/badjson").mock(
            return_value=httpx.Response(
                200,
                text="garbage",
                headers={"content-type": "application/json"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match="/badjson"):
                c.get_json("/badjson")

    @respx.mock
    def test_oversized_response_message_includes_byte_count(self):
        from poe.services.ninja.constants import NINJA_MAX_RESPONSE_BYTES

        big_data = b"x" * (NINJA_MAX_RESPONSE_BYTES + 1)
        respx.get("https://poe.ninja/big").mock(
            return_value=httpx.Response(
                200,
                content=big_data,
                headers={"content-type": "application/json"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match=str(NINJA_MAX_RESPONSE_BYTES)):
                c.get_json("/big")

    @respx.mock
    def test_oversized_protobuf_also_raises(self):
        from poe.services.ninja.constants import NINJA_MAX_RESPONSE_BYTES

        big_data = b"\x00" * (NINJA_MAX_RESPONSE_BYTES + 1)
        respx.get("https://poe.ninja/bigproto").mock(
            return_value=httpx.Response(
                200,
                content=big_data,
                headers={"content-type": "application/x-protobuf"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(ApiSchemaError, match="exceeds"):
                c.get_protobuf("/bigproto")

    @respx.mock
    def test_429_retry_count_exact(self, monkeypatch):
        monkeypatch.setattr("poe.services.ninja.client.time.sleep", lambda _s: None)
        route = respx.get("https://poe.ninja/limited429")
        route.mock(return_value=httpx.Response(429, text="Rate limited"))
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            with pytest.raises(RateLimitError):
                c.get_json("/limited429")
        # MAX_429_RETRIES = 3, so total request count = 4 (initial + 3 retries).
        assert route.call_count == 4

    @respx.mock
    def test_protobuf_content_type_skips_json_check(self):
        # get_protobuf MUST NOT raise on non-json content types.
        respx.get("https://poe.ninja/proto2").mock(
            return_value=httpx.Response(
                200,
                content=b"\x08\x02",
                headers={"content-type": "application/octet-stream"},
            ),
        )
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            assert c.get_protobuf("/proto2") == b"\x08\x02"


class TestNinjaClientNoCacheFlag:
    def test_no_cache_default_false(self):
        c = NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0))
        assert c.no_cache is False
        c.close()

    def test_no_cache_can_be_set(self):
        c = NinjaClient(no_cache=True, rate_limiter=RateLimiter(max_requests=100, window=1.0))
        assert c.no_cache is True
        c.close()


class TestNinjaClientContextManager:
    def test_close_called_on_exit(self):
        with NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0)) as c:
            assert c._client.is_closed is False
        assert c._client.is_closed is True

    def test_close_idempotent_for_owned_client(self):
        c = NinjaClient(rate_limiter=RateLimiter(max_requests=100, window=1.0))
        c.close()
        # A second close on an already-closed httpx.Client is allowed.
        c.close()

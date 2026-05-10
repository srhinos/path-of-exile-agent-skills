from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from poe.services.ninja import cache as ninja_cache
from poe.services.ninja.constants import (
    NINJA_TTL_BUILDS,
    NINJA_TTL_DICTIONARY,
    NINJA_TTL_ECONOMY,
    NINJA_TTL_HISTORY,
    NINJA_TTL_INDEX_STATE,
)


class TestCacheDir:
    def test_creates_cache_dir(self, tmp_path, monkeypatch, real_cache_dir):
        target = tmp_path / ".cache" / "poe-agent" / "ninja"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = ninja_cache.cache_dir()
        assert result == target
        assert result.exists()


class TestCacheFile:
    def test_cache_file_basic(self, tmp_path):
        cf = ninja_cache.cache_file(tmp_path, "poe1_index_state")
        assert cf == tmp_path / "poe1_index_state.json"

    def test_cache_file_sanitizes_path_chars(self, tmp_path):
        cf = ninja_cache.cache_file(tmp_path, "path/with?special&chars")
        assert "/" not in cf.name
        assert "?" not in cf.name
        assert "&" not in cf.name


class TestMetaPath:
    def test_meta_path(self, tmp_path):
        cf = tmp_path / "test.json"
        mp = ninja_cache.meta_path(cf)
        assert mp == tmp_path / "test.meta"


class TestTtlForCategory:
    def test_known_categories_have_positive_ttl(self, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        for cat in ("index", "economy", "builds", "history"):
            assert ninja_cache.ttl_for_category(cat) > 0

    def test_dictionary_has_zero_ttl(self, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        assert ninja_cache.ttl_for_category("dictionary") == 0

    def test_unknown_defaults_to_positive(self, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        assert ninja_cache.ttl_for_category("unknown") > 0

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "99999")
        assert ninja_cache.ttl_for_category("index") == 99999
        assert ninja_cache.ttl_for_category("economy") == 99999


class TestIsFresh:
    def test_no_meta_file(self, tmp_path):
        assert not ninja_cache.is_fresh(tmp_path, "missing", "index")

    def test_fresh_entry(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "test", {"data": 1})
        assert ninja_cache.is_fresh(tmp_path, "test", "index")

    def test_stale_entry(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        ninja_cache.write_cache(tmp_path, "test", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "test"))
        old_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        mf.write_text(json.dumps({"fetched_at": old_time}))
        assert not ninja_cache.is_fresh(tmp_path, "test", "index")

    def test_dictionary_always_fresh_if_exists(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "dict_abc", {"values": []})
        assert ninja_cache.is_fresh(tmp_path, "dict_abc", "dictionary")

    def test_dictionary_not_fresh_if_missing(self, tmp_path):
        assert not ninja_cache.is_fresh(tmp_path, "dict_abc", "dictionary")

    def test_corrupted_meta(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "bad", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "bad"))
        mf.write_text("not json")
        assert not ninja_cache.is_fresh(tmp_path, "bad", "index")


class TestReadWriteCache:
    def test_write_and_read(self, tmp_path):
        data = {"leagues": ["Mirage", "Standard"]}
        ninja_cache.write_cache(tmp_path, "test", data)
        result = ninja_cache.read_cache(tmp_path, "test")
        assert result == data

    def test_read_missing(self, tmp_path):
        assert ninja_cache.read_cache(tmp_path, "nonexistent") is None

    def test_read_corrupted(self, tmp_path):
        cf = ninja_cache.cache_file(tmp_path, "bad")
        cf.write_text("not json")
        assert ninja_cache.read_cache(tmp_path, "bad") is None


class TestReadWriteCacheBytes:
    def test_write_and_read_bytes(self, tmp_path):
        data = b"\x08\x01\x10\x02"
        ninja_cache.write_cache_bytes(tmp_path, "proto", data)
        result = ninja_cache.read_cache_bytes(tmp_path, "proto")
        assert result == data

    def test_read_missing_bytes(self, tmp_path):
        assert ninja_cache.read_cache_bytes(tmp_path, "nonexistent") is None


class TestGetFreshness:
    def test_no_meta(self, tmp_path):
        f = ninja_cache.get_freshness(tmp_path, "missing", "index")
        assert f["fetched_at"] is None
        assert f["cache_age_seconds"] is None
        assert f["is_stale"] is True

    def test_fresh_entry(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "test", {"data": 1})
        f = ninja_cache.get_freshness(tmp_path, "test", "index")
        assert f["fetched_at"] is not None
        assert f["cache_age_seconds"] < 5
        assert f["is_stale"] is False

    def test_stale_entry(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        ninja_cache.write_cache(tmp_path, "test", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "test"))
        old_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        mf.write_text(json.dumps({"fetched_at": old_time}))
        f = ninja_cache.get_freshness(tmp_path, "test", "index")
        assert f["is_stale"] is True
        assert f["cache_age_seconds"] > 3500

    def test_dictionary_never_stale(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "dict", {"v": 1})
        f = ninja_cache.get_freshness(tmp_path, "dict", "dictionary")
        assert f["is_stale"] is False

    def test_corrupted_meta(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "bad", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "bad"))
        mf.write_text("not json")
        f = ninja_cache.get_freshness(tmp_path, "bad", "index")
        assert f["is_stale"] is True

    def test_clock_skew_clamped_to_zero_with_warning(self, tmp_path, caplog):
        ninja_cache.write_cache(tmp_path, "skewed", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "skewed"))
        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        mf.write_text(json.dumps({"fetched_at": future_time}))
        with caplog.at_level("WARNING", logger="poe.ninja.cache"):
            f = ninja_cache.get_freshness(tmp_path, "skewed", "index")
        assert f["cache_age_seconds"] == 0.0
        assert any("negative" in r.message for r in caplog.records)


class TestInvalidateAll:
    def test_removes_all_files(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "a", {"x": 1})
        ninja_cache.write_cache(tmp_path, "b", {"y": 2})
        assert len(list(tmp_path.iterdir())) > 0
        ninja_cache.invalidate_all(tmp_path)
        assert len(list(tmp_path.iterdir())) == 0

    def test_handles_empty_dir(self, tmp_path):
        ninja_cache.invalidate_all(tmp_path)

    def test_handles_nonexistent_dir(self, tmp_path):
        ninja_cache.invalidate_all(tmp_path / "nonexistent")


class TestAtomicWrite:
    def test_atomic_write_creates_file(self, tmp_path):
        path = tmp_path / "test.json"
        ninja_cache._atomic_write(path, b'{"ok": true}')
        assert path.exists()
        assert path.read_text() == '{"ok": true}'

    def test_atomic_write_replaces_file(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text("old data")
        ninja_cache._atomic_write(path, b"new data")
        assert path.read_text() == "new data"

    def test_atomic_write_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "test.json"
        ninja_cache._atomic_write(path, b"data")
        assert path.exists()


class TestTtlByCategoryFullEnumCoverage:
    @pytest.mark.parametrize(
        ("category", "expected_ttl"),
        [
            ("index", NINJA_TTL_INDEX_STATE),
            ("economy", NINJA_TTL_ECONOMY),
            ("builds", NINJA_TTL_BUILDS),
            ("history", NINJA_TTL_HISTORY),
            ("dictionary", NINJA_TTL_DICTIONARY),
        ],
    )
    def test_every_category_resolves_to_constant(self, monkeypatch, category, expected_ttl):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        assert ninja_cache.ttl_for_category(category) == expected_ttl

    def test_ttl_by_category_table_matches_constants(self):
        assert ninja_cache.TTL_BY_CATEGORY == {
            "index": NINJA_TTL_INDEX_STATE,
            "economy": NINJA_TTL_ECONOMY,
            "builds": NINJA_TTL_BUILDS,
            "history": NINJA_TTL_HISTORY,
            "dictionary": NINJA_TTL_DICTIONARY,
        }

    def test_unknown_category_falls_back_to_economy(self, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        assert ninja_cache.ttl_for_category("totally-unknown") == NINJA_TTL_ECONOMY

    def test_empty_category_falls_back_to_economy(self, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        assert ninja_cache.ttl_for_category("") == NINJA_TTL_ECONOMY


class TestEnvOverrideEdgeCases:
    def test_zero_string_means_never_fresh(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "0")
        ninja_cache.write_cache(tmp_path, "test", {"v": 1})
        assert not ninja_cache.is_fresh(tmp_path, "test", "index")
        assert not ninja_cache.is_fresh(tmp_path, "test", "economy")

    def test_invalid_integer_string_falls_back_to_default(self, monkeypatch, caplog):
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "not-a-number")
        with caplog.at_level("WARNING", logger="poe.ninja.cache"):
            assert ninja_cache.ttl_for_category("index") == NINJA_TTL_INDEX_STATE
        assert any("not-a-number" in r.message for r in caplog.records)

    def test_float_string_falls_back_to_default(self, monkeypatch, caplog):
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "10.5")
        with caplog.at_level("WARNING", logger="poe.ninja.cache"):
            assert ninja_cache.ttl_for_category("index") == NINJA_TTL_INDEX_STATE
        assert any("10.5" in r.message for r in caplog.records)

    def test_empty_string_uses_default(self, monkeypatch):
        # Empty string is falsy; override path is skipped.
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "")
        assert ninja_cache.ttl_for_category("index") == NINJA_TTL_INDEX_STATE

    def test_negative_override_returns_negative(self, monkeypatch):
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "-100")
        assert ninja_cache.ttl_for_category("index") == -100

    def test_zero_override_disables_freshness_for_all_categories(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POE_NINJA_CACHE_TTL", "0")
        ninja_cache.write_cache(tmp_path, "test", {"v": 1})
        assert ninja_cache.is_fresh(tmp_path, "test", "index") is False
        assert ninja_cache.is_fresh(tmp_path, "test", "dictionary") is False


class TestIsFreshDictionaryBoundary:
    def test_zero_ttl_uses_file_existence_check(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        cf = ninja_cache.cache_file(tmp_path, "dict_key")
        cf.write_text("{}")
        assert ninja_cache.is_fresh(tmp_path, "dict_key", "dictionary") is True

    def test_zero_ttl_no_file_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        assert ninja_cache.is_fresh(tmp_path, "dict_key", "dictionary") is False

    def test_zero_ttl_ignores_meta_file_age(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        ninja_cache.write_cache(tmp_path, "dict_key", {"v": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "dict_key"))
        old_time = (datetime.now(UTC) - timedelta(days=365)).isoformat()
        mf.write_text(json.dumps({"fetched_at": old_time}))
        assert ninja_cache.is_fresh(tmp_path, "dict_key", "dictionary") is True


class TestIsFreshMissingFetchedAtKey:
    def test_meta_file_missing_fetched_at(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "broken", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "broken"))
        mf.write_text(json.dumps({"other_key": "value"}))
        assert ninja_cache.is_fresh(tmp_path, "broken", "index") is False

    def test_meta_file_invalid_iso_timestamp(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "broken", {"data": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "broken"))
        mf.write_text(json.dumps({"fetched_at": "not-a-timestamp"}))
        assert ninja_cache.is_fresh(tmp_path, "broken", "index") is False


class TestCacheInvariants:
    def test_round_trip_preserves_dict(self, tmp_path):
        original = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
        ninja_cache.write_cache(tmp_path, "rt", original)
        loaded = ninja_cache.read_cache(tmp_path, "rt")
        assert loaded == original

    def test_round_trip_preserves_list(self, tmp_path):
        original = [1, 2, 3, "four", {"five": 5}]
        ninja_cache.write_cache(tmp_path, "rt_list", original)
        loaded = ninja_cache.read_cache(tmp_path, "rt_list")
        assert loaded == original

    def test_bytes_round_trip_preserves_exact_bytes(self, tmp_path):
        payload = bytes(range(256))
        ninja_cache.write_cache_bytes(tmp_path, "exact", payload)
        loaded = ninja_cache.read_cache_bytes(tmp_path, "exact")
        assert loaded == payload
        assert len(loaded) == 256

    def test_write_creates_meta_file(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "with_meta", {"a": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "with_meta"))
        assert mf.exists()
        info = json.loads(mf.read_text())
        assert "fetched_at" in info
        # Round-trip must produce a valid ISO timestamp.
        datetime.fromisoformat(info["fetched_at"])

    def test_write_bytes_creates_meta_file(self, tmp_path):
        ninja_cache.write_cache_bytes(tmp_path, "bin_meta", b"\x01\x02")
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "bin_meta"))
        assert mf.exists()

    def test_empty_dict_writes_and_reads(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "empty", {})
        assert ninja_cache.read_cache(tmp_path, "empty") == {}

    def test_overwrites_previous_data(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "k", {"v": 1})
        ninja_cache.write_cache(tmp_path, "k", {"v": 2})
        assert ninja_cache.read_cache(tmp_path, "k") == {"v": 2}


class TestGetFreshnessAdditionalBoundaries:
    def test_dictionary_with_zero_age_is_not_stale(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "dictv", {})
        f = ninja_cache.get_freshness(tmp_path, "dictv", "dictionary")
        assert f["is_stale"] is False
        assert f["fetched_at"] is not None

    def test_meta_missing_fetched_at_treated_as_stale(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "x", {"a": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "x"))
        mf.write_text(json.dumps({"unrelated": True}))
        f = ninja_cache.get_freshness(tmp_path, "x", "index")
        assert f["is_stale"] is True
        assert f["fetched_at"] is None

    def test_just_at_ttl_boundary_is_stale(self, tmp_path, monkeypatch):
        monkeypatch.delenv("POE_NINJA_CACHE_TTL", raising=False)
        ninja_cache.write_cache(tmp_path, "edge", {"a": 1})
        mf = ninja_cache.meta_path(ninja_cache.cache_file(tmp_path, "edge"))
        ttl = NINJA_TTL_INDEX_STATE
        old_time = (datetime.now(UTC) - timedelta(seconds=ttl + 5)).isoformat()
        mf.write_text(json.dumps({"fetched_at": old_time}))
        f = ninja_cache.get_freshness(tmp_path, "edge", "index")
        assert f["is_stale"] is True


class TestCacheFileSanitization:
    @pytest.mark.parametrize(
        ("key", "must_not_contain"),
        [
            ("a/b", ["/"]),
            ("a?b", ["?"]),
            ("a&b", ["&"]),
            ("nested/path/with?q=1&x=2", ["/", "?", "&"]),
        ],
    )
    def test_sanitizes_path_chars(self, tmp_path, key, must_not_contain):
        cf = ninja_cache.cache_file(tmp_path, key)
        for ch in must_not_contain:
            assert ch not in cf.name


class TestInvalidateAllAdditional:
    def test_does_not_recurse_into_subdirectories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "preserved.json").write_text("{}")
        ninja_cache.write_cache(tmp_path, "topfile", {})
        ninja_cache.invalidate_all(tmp_path)
        # Subdirectory and its contents survive.
        assert sub.exists()
        assert (sub / "preserved.json").exists()

    def test_removes_meta_files_too(self, tmp_path):
        ninja_cache.write_cache(tmp_path, "k", {"v": 1})
        ninja_cache.invalidate_all(tmp_path)
        files = list(tmp_path.iterdir())
        assert files == []

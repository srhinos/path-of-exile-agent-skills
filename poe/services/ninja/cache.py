from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poe.services.ninja.constants import (
    NINJA_TTL_BUILDS,
    NINJA_TTL_DICTIONARY,
    NINJA_TTL_ECONOMY,
    NINJA_TTL_HISTORY,
    NINJA_TTL_INDEX_STATE,
)

_logger = logging.getLogger("poe.ninja.cache")

TTL_BY_CATEGORY: dict[str, int] = {
    "index": NINJA_TTL_INDEX_STATE,
    "economy": NINJA_TTL_ECONOMY,
    "builds": NINJA_TTL_BUILDS,
    "history": NINJA_TTL_HISTORY,
    "dictionary": NINJA_TTL_DICTIONARY,
}


def cache_dir() -> Path:
    path = Path.home() / ".cache" / "poe-agent" / "ninja"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_file(base_dir: Path, key: str) -> Path:
    safe_key = key.replace("/", "_").replace("?", "_").replace("&", "_")
    return base_dir / f"{safe_key}.json"


def meta_path(cf: Path) -> Path:
    return cf.with_suffix(".meta")


def ttl_for_category(category: str) -> int:
    override = os.environ.get("POE_NINJA_CACHE_TTL")
    if override:
        try:
            return int(override)
        except ValueError:
            _logger.warning(
                "POE_NINJA_CACHE_TTL=%r is not an integer, using category default for %r",
                override,
                category,
            )
    return TTL_BY_CATEGORY.get(category, NINJA_TTL_ECONOMY)


def is_fresh(base_dir: Path, key: str, category: str) -> bool:
    ttl = ttl_for_category(category)
    override = os.environ.get("POE_NINJA_CACHE_TTL")
    if override is None and category == "dictionary":
        cf = cache_file(base_dir, key)
        return cf.exists()
    if ttl <= 0:
        return False

    mf = meta_path(cache_file(base_dir, key))
    if not mf.exists():
        return False
    try:
        info = json.loads(mf.read_text())
        fetched = datetime.fromisoformat(info["fetched_at"])
        age = (datetime.now(UTC) - fetched).total_seconds()
    except (KeyError, ValueError, json.JSONDecodeError):
        return False
    return age < ttl


def read_cache(base_dir: Path, key: str) -> Any | None:
    cf = cache_file(base_dir, key)
    if not cf.exists():
        return None
    try:
        return json.loads(cf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_cache_bytes(base_dir: Path, key: str) -> bytes | None:
    cf = cache_file(base_dir, key)
    bin_path = cf.with_suffix(".bin")
    if bin_path.exists():
        return bin_path.read_bytes()
    return None


def write_cache(base_dir: Path, key: str, data: Any) -> None:
    cf = cache_file(base_dir, key)
    _atomic_write_text(cf, json.dumps(data))
    _write_meta(cf)


def write_cache_bytes(base_dir: Path, key: str, data: bytes) -> None:
    cf = cache_file(base_dir, key)
    bin_path = cf.with_suffix(".bin")
    _atomic_write_bytes(bin_path, data)
    _write_meta(cf)


def _write_meta(cf: Path) -> None:
    mf = meta_path(cf)
    meta_info = {"fetched_at": datetime.now(UTC).isoformat()}
    _atomic_write_text(mf, json.dumps(meta_info))


def get_freshness(base_dir: Path, key: str, category: str) -> dict[str, Any]:
    mf = meta_path(cache_file(base_dir, key))
    if not mf.exists():
        return {"fetched_at": None, "cache_age_seconds": None, "is_stale": True}
    try:
        info = json.loads(mf.read_text())
        fetched = datetime.fromisoformat(info["fetched_at"])
        age = (datetime.now(UTC) - fetched).total_seconds()
        if age < 0:
            _logger.warning(
                "cache age for key=%r is negative (%.1fs), clamping to 0 (clock skew?)",
                key,
                age,
            )
            age = 0.0
        ttl = ttl_for_category(category)
        is_stale = age >= ttl if ttl > 0 else False
        return {
            "fetched_at": info["fetched_at"],
            "cache_age_seconds": round(age, 1),
            "is_stale": is_stale,
        }
    except (KeyError, ValueError, json.JSONDecodeError):
        return {"fetched_at": None, "cache_age_seconds": None, "is_stale": True}


def invalidate_all(base_dir: Path) -> None:
    if base_dir.exists():
        for f in base_dir.iterdir():
            if f.is_file():
                f.unlink()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    closed = False
    try:
        os.write(fd, content)
        os.close(fd)
        closed = True
        Path(tmp).replace(path)
    except BaseException:
        if not closed:
            os.close(fd)
        Path(tmp).unlink(missing_ok=True)
        raise


def _atomic_write_text(path: Path, content: str) -> None:
    _atomic_write(path, content.encode("utf-8"))


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    _atomic_write(path, content)

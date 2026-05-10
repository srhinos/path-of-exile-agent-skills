from __future__ import annotations

import json
from typing import TYPE_CHECKING

from poe.services.repoe.constants import (
    BASE_ITEM_DOMAINS,
    CURRENCY_PATH_NAMES,
    DEFAULT_MAX_PREFIXES,
    DEFAULT_MAX_SUFFIXES,
    FOSSIL_WEIGHT_DIVISOR,
    INFLUENCE_SUFFIXES,
    INFLUENCE_TAG_MAP,
    MAX_PREFIXES_BY_CLASS,
    MAX_SUFFIXES_BY_CLASS,
    MOD_DOMAIN_FOR_BASE_DOMAIN,
    PLAYER_ITEM_DOMAINS,
    WEAPON_CLASS_DERIVED_TAGS,
)

if TYPE_CHECKING:
    from pathlib import Path

REPOE_BUILD_STEPS: tuple[tuple[str, str, str], ...] = (
    ("base_items", "base_items.json", "_process_base_items"),
    ("mods", "mods.json", "_process_mods"),
    ("fossils", "fossils.json", "_process_fossils"),
    ("essences", "essences.json", "_process_essences"),
    ("bench_crafts", "crafting_bench_options.json", "_process_bench_crafts"),
    ("stat_translations", "stat_translations.json", "_process_stat_translations"),
)


def _process_base_items(raw: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for meta_path, entry in raw.items():
        if entry.get("domain") not in BASE_ITEM_DOMAINS:
            continue
        if entry.get("release_state") != "released":
            continue
        name = entry.get("name", "")
        if not name:
            continue
        item_class = entry.get("item_class", "")
        if entry.get("domain") == "misc" and item_class != "Jewel":
            continue
        tags = list(entry.get("tags", []))
        for derived in WEAPON_CLASS_DERIVED_TAGS.get(item_class, ()):
            if derived not in tags:
                tags.append(derived)
        result[name] = {
            "id": meta_path,
            "domain": entry.get("domain", "item"),
            "item_class": item_class,
            "drop_level": entry.get("drop_level", 0),
            "tags": tags,
            "properties": entry.get("properties", {}),
            "implicits": entry.get("implicits", []),
            "max_prefixes": MAX_PREFIXES_BY_CLASS.get(item_class, DEFAULT_MAX_PREFIXES),
            "max_suffixes": MAX_SUFFIXES_BY_CLASS.get(item_class, DEFAULT_MAX_SUFFIXES),
        }
    return result


def _detect_influence(spawn_weights: list[dict]) -> str | None:
    for sw in spawn_weights:
        tag = sw["tag"]
        for inf_tag, inf_name in INFLUENCE_TAG_MAP.items():
            if tag.endswith(f"_{inf_tag}") and sw["weight"] > 0:
                return inf_name
    return None


def _process_mods(raw: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for mod_id, entry in raw.items():
        domain = entry.get("domain", "")
        if domain not in PLAYER_ITEM_DOMAINS:
            continue
        gen_type = entry.get("generation_type", "")
        if gen_type not in ("prefix", "suffix"):
            continue
        groups = entry.get("groups", [])
        spawn_weights = entry.get("spawn_weights", [])
        result[mod_id] = {
            "name": entry.get("name", ""),
            "group": groups[0] if groups else "",
            "domain": domain,
            "affix": gen_type,
            "required_level": entry.get("required_level", 0),
            "implicit_tags": entry.get("implicit_tags", []),
            "stats": entry.get("stats", []),
            "spawn_weights": spawn_weights,
            "influence": _detect_influence(spawn_weights),
            "is_essence_only": entry.get("is_essence_only", False),
        }
    return result


def _build_mod_pool(base_items: dict[str, dict], mods: dict[str, dict]) -> dict[str, list[str]]:
    pool: dict[str, list[str]] = {}
    for base in base_items.values():
        base_tags = set(base["tags"])
        base_id = base["id"]
        base_domain = base.get("domain", "item")
        default_domains = frozenset({"item", "crafted"})
        allowed_mod_domains = MOD_DOMAIN_FOR_BASE_DOMAIN.get(base_domain, default_domains)
        matching: list[str] = []
        for mod_id, mod in mods.items():
            if mod["is_essence_only"]:
                continue
            if mod.get("domain", "item") not in allowed_mod_domains:
                continue
            for sw in mod["spawn_weights"]:
                tag = sw["tag"]
                if tag in base_tags:
                    if sw["weight"] > 0:
                        matching.append(mod_id)
                    break
                base_tag, _, suffix = tag.rpartition("_")
                if base_tag and suffix in INFLUENCE_SUFFIXES and base_tag in base_tags:
                    if sw["weight"] > 0:
                        matching.append(mod_id)
                    break
        pool[base_id] = matching
    return pool


def _process_fossils(raw: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for entry in raw.values():
        name = entry.get("name", "")
        if not name:
            continue
        positive: dict[str, float] = {}
        for pw in entry.get("positive_mod_weights", []):
            positive[pw["tag"]] = pw["weight"] / FOSSIL_WEIGHT_DIVISOR
        negative: dict[str, float] = {}
        blocked: list[str] = []
        for nw in entry.get("negative_mod_weights", []):
            val = nw["weight"] / FOSSIL_WEIGHT_DIVISOR
            negative[nw["tag"]] = val
            if nw["weight"] == 0:
                blocked.append(nw["tag"])
        result[name] = {
            "positive_weights": positive,
            "negative_weights": negative,
            "forced_mods": entry.get("forced_mods", []),
            "added_mods": entry.get("added_mods", []),
            "blocked_tags": blocked,
        }
    return result


def _process_essences(raw: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for entry in raw.values():
        name = entry.get("name", "")
        if not name:
            continue
        ess_type = entry.get("type", {})
        result[name] = {
            "tier": ess_type.get("tier", 0),
            "level_restriction": entry.get("item_level_restriction"),
            "mods": entry.get("mods", {}),
            "is_corruption_only": ess_type.get("is_corruption_only", False),
        }
    return result


def _process_bench_crafts(raw: list) -> list[dict]:
    result: list[dict] = []
    for entry in raw:
        actions = entry.get("actions", {})
        mod_id = actions.get("add_explicit_mod")
        if not mod_id:
            continue
        cost_raw = entry.get("cost", {})
        cost: dict[str, int] = {}
        for currency_path, amount in cost_raw.items():
            currency_name = CURRENCY_PATH_NAMES.get(currency_path, currency_path)
            cost[currency_name] = amount
        result.append(
            {
                "mod_id": mod_id,
                "item_classes": entry.get("item_classes", []),
                "cost": cost,
                "bench_tier": entry.get("bench_tier", 0),
            }
        )
    return result


def _process_stat_translations(raw: list) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw:
        ids = entry.get("ids", [])
        english = entry.get("English", [])
        if not english:
            continue
        template = english[0].get("string", "")
        for stat_id in ids:
            if stat_id and stat_id not in result:
                result[stat_id] = template
    return result


class RepoEPipeline:
    def __init__(self, vendor_dir: Path) -> None:
        self._vendor_dir = vendor_dir

    def _read_raw(self, filename: str) -> dict | list:
        path = self._vendor_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def build(self, output_dir: Path) -> dict[str, int]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results: dict[str, int] = {}

        transforms = {
            "_process_base_items": _process_base_items,
            "_process_mods": _process_mods,
            "_process_fossils": _process_fossils,
            "_process_essences": _process_essences,
            "_process_bench_crafts": _process_bench_crafts,
            "_process_stat_translations": _process_stat_translations,
        }

        processed: dict[str, dict | list] = {}
        for output_name, source_file, transform_name in REPOE_BUILD_STEPS:
            raw = self._read_raw(source_file)
            data = transforms[transform_name](raw)
            processed[output_name] = data
            out_path = output_dir / f"{output_name}.json"
            out_path.write_text(json.dumps(data), encoding="utf-8")
            results[output_name] = out_path.stat().st_size

        mod_pool = _build_mod_pool(processed["base_items"], processed["mods"])
        out_path = output_dir / "mod_pool.json"
        out_path.write_text(json.dumps(mod_pool), encoding="utf-8")
        results["mod_pool"] = out_path.stat().st_size

        return results

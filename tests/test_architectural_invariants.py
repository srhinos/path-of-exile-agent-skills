from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

from pydantic import BaseModel

import poe
import poe.models
import poe.services

_MODEL_SCAN_PACKAGES = (poe.models, poe.services)


def _all_models() -> list[type[BaseModel]]:
    """Discover every BaseModel subclass under poe.models and poe.services.

    Walking all of poe.* would trigger the cyclopts app() side-effect inside
    poe.app at import time. The two packages we care about are model
    declarations (poe.models) and service-layer response models (poe.services).
    """
    discovered: set[type[BaseModel]] = set()
    for pkg in _MODEL_SCAN_PACKAGES:
        for module_info in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
            try:
                module = importlib.import_module(module_info.name)
            except Exception:
                continue
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseModel) and obj is not BaseModel:
                    discovered.add(obj)
    return sorted(discovered, key=lambda m: f"{m.__module__}.{m.__name__}")


def _own_model_config(cls: type[BaseModel]) -> dict | None:
    """Return model_config declared on this class itself (not inherited).

    Inherited validate_assignment is fine in practice but a future PR that
    strips it from the parent would silently flip the subclass. Requiring
    own-declaration on every concrete BaseModel makes that regression loud.
    """
    return cls.__dict__.get("model_config")


def _is_validator_decorator(d: ast.expr, names: tuple[str, ...]) -> bool:
    if isinstance(d, ast.Call):
        d = d.func
    if isinstance(d, ast.Name):
        return d.id in names
    if isinstance(d, ast.Attribute):
        return d.attr in names
    return False


def _function_body_uses_clamp(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Walk the entire function body for max(...) or min(...) calls.

    Catches the two-statement clamp pattern (`x = max(0, v); return x`)
    that a Return-only walk misses.
    """
    for inner in ast.walk(func):
        if (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id in ("max", "min")
        ):
            return True
    return False


_VALIDATOR_DECORATOR_NAMES = ("field_validator", "model_validator")


def _scan_misplaced_constants() -> list[str]:
    """Find module-level SCREAMING_SNAKE_CASE constants in service/model files.

    Skips files named constants.py (which is exactly where constants belong).
    Returns identifiers in `path::NAME` form for stable comparison against
    the allowlist.
    """
    violations: list[str] = []
    for pkg in _MODEL_SCAN_PACKAGES:
        pkg_root = Path(pkg.__file__).parent
        for py_file in pkg_root.rglob("*.py"):
            if py_file.name == "constants.py":
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue
            for node in tree.body:
                names: list[str] = []
                if isinstance(node, ast.Assign):
                    names.extend(t.id for t in node.targets if isinstance(t, ast.Name))
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    names.append(node.target.id)
                for name in names:
                    if name.lstrip("_").isupper() and len(name.lstrip("_")) > 1:
                        rel = py_file.relative_to(pkg_root.parent.parent).as_posix()
                        violations.append(f"{rel}::{name}")
    return violations


# Pre-existing constants in service/model files. These should be moved into a
# constants.py module over time. Never add to this list — fix it at the source.
CONSTANTS_PLACEMENT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # services/build/items_service.py — text-parsing line indices and prefixes
        "poe/services/build/items_service.py::_ITEM_TEXT_NAME_LINE",
        "poe/services/build/items_service.py::_ITEM_TEXT_BASE_LINE",
        "poe/services/build/items_service.py::_ITEM_TEXT_SKIP_PREFIXES",
        # services/ninja — single-file thresholds and config
        "poe/services/ninja/cache.py::TTL_BY_CATEGORY",
        "poe/services/ninja/client.py::HTTP_TOO_MANY_REQUESTS",
        "poe/services/ninja/client.py::HTTP_CLIENT_ERROR_MIN",
        "poe/services/ninja/client.py::MAX_429_RETRIES",
        "poe/services/ninja/client.py::RETRY_BASE_DELAY",
        "poe/services/ninja/comparison.py::POPULAR_THRESHOLD_PCT",
        "poe/services/ninja/comparison.py::DEFENSIVE_THRESHOLDS",
        "poe/services/ninja/history.py::CHAOS_PAIR_ID",
        "poe/services/ninja/history.py::SPIKE_THRESHOLD",
        "poe/services/ninja/history.py::CRASH_THRESHOLD",
        "poe/services/ninja/history.py::SUSTAINED_TREND_DAYS",
        "poe/services/ninja/history.py::MIN_DATA_POINTS",
        "poe/services/ninja/history.py::MIN_VARIANCE_POINTS",
        "poe/services/ninja/history.py::TREND_DOMINANCE",
        "poe/services/ninja/history.py::WINDOW_7D",
        "poe/services/ninja/history.py::WINDOW_30D",
        "poe/services/ninja/patches.py::SIGNIFICANCE_THRESHOLD",
        # services/build/xml — file-local helper data for parser/writer
        "poe/services/build/xml/parser.py::_GEM_STR_ATTRS",
        "poe/services/build/xml/parser.py::_VARIANT_ALT_ATTRS",
        "poe/services/build/xml/parser.py::_VARIANT_ALT_FIELDS",
        "poe/services/build/xml/parser.py::_BOOL_MARKERS",
        "poe/services/build/xml/parser.py::_PASSTHROUGH_TAGS",
        "poe/services/build/xml/slots.py::CANONICAL_SLOTS",
        "poe/services/build/xml/slots.py::SLOT_CATEGORIES",
        "poe/services/build/xml/slots.py::_SLOT_ALIASES",
        "poe/services/build/xml/writer.py::_GEM_OPTIONAL_STR_ATTRS",
        "poe/services/build/xml/writer.py::_VARIANT_ALT_PAIRS",
        "poe/services/build/xml/writer.py::_ITEM_METADATA_FIELDS",
        "poe/services/build/xml/writer.py::_ITEM_STATE_LINES",
        # services/repoe/pipeline
        "poe/services/repoe/pipeline/pipeline.py::REPOE_BUILD_STEPS",
        # models — enum-derived validation sets (would be circular if in
        # poe/constants.py since constants currently doesn't import from types)
        "poe/models/sim.py::VALID_METHODS",
        "poe/models/sim.py::VALID_MATCH_MODES",
        "poe/models/build/items.py::VALID_INFLUENCES",
        "poe/models/build/items.py::VALID_RARITIES",
        "poe/models/build/items.py::_INFLUENCE_BY_CASEFOLD",
        "poe/models/build/items.py::_RARITY_BY_CASEFOLD",
    }
)


def _scan_validators_for_clamps() -> list[tuple[str, str, int]]:
    """Scan every poe/**/*.py file for validators that clamp.

    Inspecting the whole package (not just poe.models) catches helper
    validators that might live in service modules.
    """
    violations: list[tuple[str, str, int]] = []
    poe_dir = Path(poe.__file__).parent
    for py_file in poe_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(
                _is_validator_decorator(d, _VALIDATOR_DECORATOR_NAMES) for d in node.decorator_list
            ):
                continue
            if _function_body_uses_clamp(node):
                violations.append((py_file.name, node.name, node.lineno))
    return violations


class TestArchitecturalInvariants:
    """Forcing functions for project-wide model conventions.

    These tests lock in the boundary-contract architecture so a future
    PR cannot silently regress it. Failure here means a new model was
    added without the conventions, not that the test is wrong.
    """

    def test_all_models_have_validate_assignment(self):
        offenders = []
        for m in _all_models():
            own = _own_model_config(m)
            if own is None:
                offenders.append(f"{m.__module__}.{m.__name__} (no own model_config)")
                continue
            if not own.get("validate_assignment", False):
                offenders.append(f"{m.__module__}.{m.__name__} (validate_assignment not set)")
        assert not offenders, (
            "Every BaseModel under poe/ must declare its own "
            "model_config = ConfigDict(validate_assignment=True, ...) — inherited "
            "config does not count, since a parent change would silently flip "
            "the subclass. Offenders: " + "; ".join(offenders)
        )

    def test_no_silent_clamping_in_validators(self):
        """Banned in field_validator AND model_validator, in any function position."""
        violations = _scan_validators_for_clamps()
        assert not violations, (
            "field_validator/model_validator methods must not contain max(...) or "
            "min(...) anywhere in their body — that pattern is silent coercion "
            "masquerading as validation. Raise on out-of-range input instead, and "
            "clamp at the boundary (parser, API client, etc.) where a "
            "logger.warning can fire. Offenders: "
            + ", ".join(f"{f}::{name}:{line}" for f, name, line in violations)
        )

    def test_no_new_constants_outside_constants_files(self):
        """Per CLAUDE.md: constants belong in poe/constants.py or a subpackage
        constants.py (e.g. poe/services/build/constants.py). Inline constants
        in service/model files become forgotten and duplicate-prone.

        This test enforces the rule for NEW violations. Pre-existing
        violations are listed in CONSTANTS_PLACEMENT_ALLOWLIST below as
        acknowledged tech debt — shrink the allowlist over time, never add.
        """
        violations = _scan_misplaced_constants()
        unexpected = sorted(set(violations) - CONSTANTS_PLACEMENT_ALLOWLIST)
        assert not unexpected, (
            "New module-level constants must live in a constants.py file, "
            "not inline in services or models. Move these to "
            "poe/constants.py or the relevant subpackage constants.py:\n  "
            + "\n  ".join(unexpected)
        )

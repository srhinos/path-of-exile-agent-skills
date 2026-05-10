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

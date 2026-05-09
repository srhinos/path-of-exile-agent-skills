from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

from pydantic import BaseModel

import poe.models


def _all_models() -> list[type[BaseModel]]:
    discovered: set[type[BaseModel]] = set()
    for module_info in pkgutil.walk_packages(poe.models.__path__, prefix="poe.models."):
        module = importlib.import_module(module_info.name)
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseModel) and obj is not BaseModel:
                discovered.add(obj)
    return sorted(discovered, key=lambda m: f"{m.__module__}.{m.__name__}")


def _is_field_validator_decorator(d: ast.expr) -> bool:
    if isinstance(d, ast.Call):
        d = d.func
    if isinstance(d, ast.Name):
        return d.id == "field_validator"
    if isinstance(d, ast.Attribute):
        return d.attr == "field_validator"
    return False


def _return_uses_clamp(return_value: ast.expr) -> bool:
    for inner in ast.walk(return_value):
        if (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id in ("max", "min")
        ):
            return True
    return False


def _scan_validators_for_clamps() -> list[tuple[str, str, int]]:
    violations: list[tuple[str, str, int]] = []
    models_dir = Path(poe.models.__file__).parent
    for py_file in models_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not any(_is_field_validator_decorator(d) for d in node.decorator_list):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Return)
                    and inner.value is not None
                    and _return_uses_clamp(inner.value)
                ):
                    violations.append((py_file.name, node.name, inner.lineno))
                    break
    return violations


class TestArchitecturalInvariants:
    """Forcing functions for project-wide model conventions.

    These tests lock in the boundary-contract architecture so a future
    PR cannot silently regress it. Failure here means a new model was
    added without the conventions, not that the test is wrong.
    """

    def test_all_models_have_validate_assignment(self):
        offenders = [
            f"{m.__module__}.{m.__name__}"
            for m in _all_models()
            if not m.model_config.get("validate_assignment", False)
        ]
        assert not offenders, (
            "Every BaseModel in poe.models must set "
            "model_config = ConfigDict(validate_assignment=True) so its "
            "field validators fire on setattr (the production path used "
            "by parsers and services). Offenders: " + ", ".join(offenders)
        )

    def test_no_silent_clamping_in_field_validators(self):
        violations = _scan_validators_for_clamps()
        assert not violations, (
            "field_validator methods must not return max(...) or min(...) — "
            "that's silent coercion masquerading as validation. Raise on "
            "out-of-range input instead, and clamp at the boundary "
            "(parser, API client, etc.) where a logger.warning can fire. "
            "Offenders: " + ", ".join(f"{f}::{name}:{line}" for f, name, line in violations)
        )

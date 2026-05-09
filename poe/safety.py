from __future__ import annotations

import shutil
from pathlib import Path

from poe.constants import CLAUDE_SUBFOLDER
from poe.exceptions import BuildValidationError
from poe.paths import (
    get_builds_path,
    resolve_build_file,
    validate_build_name,
    validate_file_path,
)


def get_claude_builds_path() -> Path:
    claude_dir = get_builds_path() / CLAUDE_SUBFOLDER
    claude_dir.mkdir(parents=True, exist_ok=True)
    return claude_dir


def is_inside_claude_folder(path: Path) -> bool:
    try:
        claude_dir = get_builds_path() / CLAUDE_SUBFOLDER
        path.resolve().relative_to(claude_dir.resolve())
    except ValueError:
        return False
    else:
        return True


def resolve_for_write(name: str) -> tuple[Path, str | None]:
    """Resolve a build name to a safe write path inside Claude/.

    Returns ``(path, cloned_from)`` where *cloned_from* is the original
    path string when a copy was made, or ``None`` when no clone was needed.
    """
    validate_build_name(name)
    claude_dir = get_claude_builds_path()
    filename = name if name.endswith(".xml") else name + ".xml"

    claude_path = claude_dir / filename
    if not claude_path.resolve().is_relative_to(claude_dir.resolve()):
        raise BuildValidationError(f"Invalid build name: {name!r}")
    if claude_path.exists():
        return claude_path, None

    original = resolve_build_file(name)

    if is_inside_claude_folder(original):
        return original, None

    shutil.copy2(original, claude_path)
    return claude_path, str(original)


def resolve_or_file_for_write(name: str, file_path: str | None) -> tuple[Path, str | None]:
    """Resolve for a write operation with the Claude/ safety layer.

    Returns (path, cloned_from). When file_path is given, the safety layer is bypassed.
    """
    if file_path:
        validate_file_path(file_path)
        return Path(file_path), None
    return resolve_for_write(name)

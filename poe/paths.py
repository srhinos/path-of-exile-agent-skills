from __future__ import annotations

import os
from pathlib import Path

from poe.constants import CLAUDE_SUBFOLDER, POB_XML_EXTENSION
from poe.exceptions import BuildNotFoundError, BuildValidationError

_WINDOWS_INVALID_CHARS = frozenset(':*?"<>|')
_WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }
)


def validate_build_name(name: str) -> None:
    if not name or not name.strip():
        raise BuildValidationError(f"Invalid build name: {name!r}")
    if ".." in name or "\\" in name or "/" in name:
        raise BuildValidationError(f"Invalid build name: {name!r}")
    stem = name.removesuffix(".xml")
    if any(c in stem for c in _WINDOWS_INVALID_CHARS):
        raise BuildValidationError(f"Build name contains invalid characters: {name!r}")
    if stem.upper() in _WINDOWS_RESERVED:
        raise BuildValidationError(f"Build name uses a reserved word: {name!r}")


def get_pob_path() -> Path:
    # Verify Launch.lua exists rather than just .exists() — a misconfigured
    # POB_PATH pointing at /tmp or an unrelated directory previously slipped
    # past, then PoBEngine.init() crashed mid-Lua-load with a misleading
    # "missing Launch.lua" instead of a clear "POB_PATH is wrong".
    env = os.environ.get("POB_PATH")
    if env:
        p = Path(env)
        if p.is_dir() and (p / "Launch.lua").is_file():
            return p
        if p.exists():
            raise BuildNotFoundError(
                f"POB_PATH={env!r} does not contain Launch.lua. "
                "Set POB_PATH to the Path of Building installation directory "
                "(the folder containing Launch.lua)."
            )

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        p = Path(appdata) / "Path of Building Community"
        if p.is_dir() and (p / "Launch.lua").is_file():
            return p

    raise BuildNotFoundError(
        "Could not find Path of Building Community installation. "
        "Set the POB_PATH environment variable to the installation directory."
    )


def get_builds_path() -> Path:
    env = os.environ.get("POB_BUILDS_PATH")
    if env:
        p = Path(env)
        if p.exists():
            return p

    docs = Path.home() / "Documents" / "Path of Building" / "Builds"
    if docs.exists():
        return docs

    onedrive = Path.home() / "OneDrive" / "Documents" / "Path of Building" / "Builds"
    if onedrive.exists():
        return onedrive

    raise BuildNotFoundError(
        "Could not find builds directory. Set the POB_BUILDS_PATH environment variable."
    )


def list_build_files() -> list[Path]:
    builds_path = get_builds_path()
    return sorted(builds_path.rglob(f"*{POB_XML_EXTENSION}"))


def resolve_build_file(name: str) -> Path:
    """Resolve a build name to a full path.

    Searches recursively through subdirectories.
    Prefers Claude/ copies over originals (read-after-write consistency).
    """
    validate_build_name(name)
    builds_path = get_builds_path()

    if not name.endswith(POB_XML_EXTENSION):
        name = name + POB_XML_EXTENSION

    claude_dir = builds_path / CLAUDE_SUBFOLDER
    claude_path = claude_dir / name
    if claude_path.exists():
        return claude_path

    path = builds_path / name
    if not path.resolve().is_relative_to(builds_path.resolve()):
        raise BuildValidationError(f"Invalid build name: {name!r}")
    if path.exists():
        return path

    for f in builds_path.rglob(f"*{POB_XML_EXTENSION}"):
        if f.name.casefold() == name.casefold():
            return f

    stem = name.removesuffix(POB_XML_EXTENSION).casefold()
    prefix_matches = [
        f for f in builds_path.rglob(f"*{POB_XML_EXTENSION}") if f.stem.casefold().startswith(stem)
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        names = [f.stem for f in prefix_matches]
        raise BuildNotFoundError(f"Ambiguous prefix {name!r}: matches {names}")

    raise BuildNotFoundError(f"Build file not found: {name}")


def validate_file_path(file_path: str) -> None:
    parts = Path(file_path).parts
    if ".." in parts:
        raise BuildValidationError(
            f"Invalid file path: {file_path!r} contains '..' (path traversal)"
        )


def resolve_or_file(name: str, file_path: str | None) -> Path:
    if file_path:
        validate_file_path(file_path)
        return Path(file_path)
    return resolve_build_file(name)

from __future__ import annotations

import shutil
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

from poe.exceptions import PoeError
from poe.output import render as _output


def _find_skill_source() -> Path | None:
    skill_dir = Path(__file__).resolve().parent.parent / "skills" / "poe"
    if (skill_dir / "SKILL.md").exists():
        return skill_dir
    return None


def _get_package_version() -> str | None:
    try:
        return _pkg_version("poe-tools")
    except PackageNotFoundError:
        return None


def install_skill(
    *,
    force: bool = False,
    symlink: bool = False,
    uninstall: bool = False,
    json: bool = False,
) -> None:
    """Install the poe skill into ~/.claude/skills/ for Claude Code discovery.

    Parameters
    ----------
    force
        Overwrite existing skill installation.
    symlink
        Symlink instead of copy (for development).
    uninstall
        Remove the installed skill.
    json
        Output raw JSON.
    """
    target = Path.home() / ".claude" / "skills" / "poe"

    result = {"status": "ok"}

    try:
        if uninstall:
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            else:
                raise PoeError("No skill installation found")
            result["action"] = "uninstalled"
            result["removed"] = str(target)
            _output(result, json_mode=json)
            return

        source = _find_skill_source()
        if not source:
            raise PoeError("Could not locate skill files in the poe package")

        if target.exists() or target.is_symlink():
            if not force:
                raise PoeError(f"Already installed at {target}. Use --force to overwrite.")
            if target.is_symlink():
                target.unlink()
            else:
                shutil.rmtree(target)

        target.parent.mkdir(parents=True, exist_ok=True)

        if symlink:
            try:
                target.symlink_to(source, target_is_directory=True)
            except OSError as e:
                raise PoeError(
                    f"Cannot create symlink: {e}. "
                    "On Windows, symlinks require admin privileges or Developer Mode. "
                    "Run without --symlink to copy instead."
                ) from e
            result["action"] = "symlinked"
        else:
            shutil.copytree(source, target)
            result["action"] = "copied"
            pkg_version = _get_package_version()
            if pkg_version:
                (target / "version.md").write_text(pkg_version, encoding="utf-8")
    except (OSError, shutil.Error) as e:
        # rmtree, copytree, mkdir, write_text all raise OSError on permission
        # / disk-full / encoding errors. Translate to PoeError so app.run()'s
        # top-level handler emits a clean stderr envelope instead of a raw
        # traceback.
        raise PoeError(f"install-skill failed: {e}") from e

    result["source"] = str(source)
    result["target"] = str(target)
    _output(result, json_mode=json)

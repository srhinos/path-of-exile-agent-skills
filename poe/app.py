from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import cyclopts
from pydantic import ValidationError

from poe.commands.build.commands import build_app
from poe.commands.dev.commands import dev_app
from poe.commands.ninja.commands import ninja_app
from poe.commands.root import install_skill
from poe.commands.sim.commands import sim_app
from poe.exceptions import PoeError
from poe.formatters import register_formatters

try:
    _version = _pkg_version("poe-tools")
except PackageNotFoundError:
    _version = "0.0.0"

app = cyclopts.App(name="poe", help="Path of Exile CLI toolkit.", version=_version)

app.command(build_app)
app.command(dev_app)
app.command(sim_app)
app.command(ninja_app)
app.command(install_skill, name="install-skill")
register_formatters()


def _check_skill_version() -> None:
    version_file = Path.home() / ".claude" / "skills" / "poe" / "version.md"
    if not version_file.exists():
        return
    try:
        installed_skill = version_file.read_text().strip()
        current = _pkg_version("poe-tools")
        if installed_skill != current:
            print(
                f"Skill outdated ({installed_skill} → {current}). Run: poe install-skill --force",
                file=sys.stderr,
            )
    except PackageNotFoundError:
        pass


def run() -> None:
    _check_skill_version()
    try:
        app()
    except PoeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        raise SystemExit(1) from None
    except ValidationError as e:
        message = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        print(json.dumps({"error": f"Invalid data: {message}"}), file=sys.stderr)
        raise SystemExit(1) from None

from __future__ import annotations

import os
import sys
import zlib
from pathlib import Path
from typing import Annotated
from xml.etree.ElementTree import ParseError as XMLParseError

import cyclopts
import httpx
from defusedxml import ElementTree as SafeET

from poe.commands.build.config import config_app
from poe.commands.build.engine import engine_app
from poe.commands.build.flasks import flasks_app
from poe.commands.build.gems import gems_app
from poe.commands.build.items import items_app
from poe.commands.build.jewels import jewels_app
from poe.commands.build.tree import tree_app
from poe.exceptions import BuildNotFoundError, CodecError, PoeError
from poe.output import render as _output
from poe.paths import resolve_build_file, validate_build_name, validate_file_path
from poe.safety import get_claude_builds_path
from poe.services.build.build_service import BuildService
from poe.services.build.xml.codec import decode_build, encode_build, fetch_build_code

build_app = cyclopts.App(name="build", help="Build file operations.")

build_app.command(tree_app)
build_app.command(items_app)
build_app.command(gems_app)
build_app.command(config_app)
build_app.command(engine_app)
build_app.command(flasks_app)
build_app.command(jewels_app)


def _svc() -> BuildService:
    return BuildService()


@build_app.command(name="list")
def builds_list(*, json: bool = False) -> None:
    """List all .xml build files with class/level metadata.

    Parameters
    ----------
    json
        Output raw JSON.
    """
    _output(_svc().list_builds(), json_mode=json)


@build_app.command(name="create")
def builds_create(
    name: str,
    *,
    cls: Annotated[str, cyclopts.Parameter(name="--class")] = "Scion",
    ascendancy: str = "",
    level: int = 1,
    tree_version: str | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Create a new minimal build file.

    Parameters
    ----------
    name
        Build name.
    cls
        Character class.
    ascendancy
        Ascendancy class.
    level
        Character level.
    tree_version
        Tree version.
    file
        Explicit output file path.
    json
        Output raw JSON.
    """
    validate_build_name(name)
    result = _svc().create(
        name,
        class_name=cls,
        ascendancy=ascendancy,
        level=level,
        tree_version=tree_version,
        file_path=file,
    )
    _output(result, json_mode=json)


@build_app.command(name="delete")
def builds_delete(
    name: str, *, confirm: bool = False, file: str | None = None, json: bool = False
) -> None:
    """Delete a build file.

    Parameters
    ----------
    name
        Build name or unique prefix.
    confirm
        Confirm deletion.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().delete(name, file_path=file, confirm=confirm), json_mode=json)


@build_app.command(name="analyze")
def builds_analyze(name: str, *, json: bool = False) -> None:
    """Full build analysis.

    Parameters
    ----------
    name
        Build name or unique prefix.
    json
        Output raw JSON.
    """
    _output(_svc().analyze(name), json_mode=json)


@build_app.command(name="stats")
def builds_stats(name: str, *, category: str = "all", json: bool = False) -> None:
    """Extract stats from a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    category
        Stat category (off/def/all).
    json
        Output raw JSON.
    """
    _output(_svc().stats(name, category=category), json_mode=json)


@build_app.command(name="compare")
def builds_compare(name1: str, name2: str, *, json: bool = False) -> None:
    """Compare two builds side by side.

    Parameters
    ----------
    name1
        First build name.
    name2
        Second build name.
    json
        Output raw JSON.
    """
    _output(_svc().compare(name1, name2), json_mode=json)


@build_app.command(name="notes")
def builds_notes(
    name: str,
    *,
    set_notes: Annotated[str | None, cyclopts.Parameter(name="--set")] = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Get or set build notes.

    Parameters
    ----------
    name
        Build name or unique prefix.
    set_notes
        Set notes text.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    if set_notes is not None:
        _output(_svc().notes_set(name, set_notes, file_path=file), json_mode=json)
    else:
        _output(_svc().notes_get(name, file_path=file), json_mode=json)


@build_app.command(name="validate")
def builds_validate(name: str, *, json: bool = False) -> None:
    """Validate build for common issues.

    Parameters
    ----------
    name
        Build name or unique prefix.
    json
        Output raw JSON.
    """
    _output(_svc().validate(name), json_mode=json)


@build_app.command(name="export")
def builds_export(name: str, dest: str, *, json: bool = False) -> None:
    """Export a copy of a build file.

    Parameters
    ----------
    name
        Build name or unique prefix.
    dest
        Destination path.
    json
        Output raw JSON.
    """
    _output(_svc().export(name, dest), json_mode=json)


@build_app.command(name="set-main-skill")
def set_main_skill(name: str, *, index: int, file: str | None = None, json: bool = False) -> None:
    """Set the main skill group for a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    index
        Main socket group index (1-based).
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().set_main_skill(name, index, file_path=file), json_mode=json)


@build_app.command(name="decode")
def builds_decode(
    code: str = "",
    *,
    file: str | None = None,
    save: str | None = None,
    json: bool = False,
) -> None:
    """Decode a PoB build sharing code to XML.

    Parameters
    ----------
    code
        Build sharing code (positional or use --file).
    file
        Read build code from a file instead of CLI argument.
    save
        Save decoded build.
    json
        Output raw JSON.
    """
    if file:
        validate_file_path(file)
        try:
            code = Path(file).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as e:
            raise CodecError(f"Could not read code file {file!r}: {e}") from e
    if not code:
        raise CodecError("Provide a build code as argument or via --file")
    try:
        xml_str = decode_build(code)
    except (ValueError, zlib.error) as e:
        raise CodecError(f"Failed to decode build code: {e}") from e
    result: dict = {"xml": xml_str}
    if save:
        validate_build_name(save)
        try:
            SafeET.fromstring(xml_str)
        except (XMLParseError, ValueError) as e:
            raise CodecError("Decoded content is not valid XML") from e
        claude_dir = get_claude_builds_path()
        filename = save if save.endswith(".xml") else save + ".xml"
        save_path = claude_dir / filename
        try:
            save_path.write_text(xml_str, encoding="utf-8")
        except OSError as e:
            raise CodecError(f"Could not write decoded build to {save_path}: {e}") from e
        result["saved_to"] = str(save_path)
    _output(result, json_mode=json)


@build_app.command(name="encode")
def builds_encode(name: str, *, file: str | None = None, json: bool = False) -> None:
    """Encode a build to a PoB sharing code.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    if file:
        validate_file_path(file)
    try:
        path = Path(file) if file else resolve_build_file(name)
        xml_str = path.read_text(encoding="utf-8")
    except (FileNotFoundError, BuildNotFoundError):
        raise BuildNotFoundError(f"Build file not found: {file or name}") from None
    except (OSError, UnicodeDecodeError) as e:
        raise PoeError(f"Could not read build file {file or name}: {e}") from e
    _output({"status": "ok", "code": encode_build(xml_str)}, json_mode=json)


@build_app.command(name="open")
def builds_open(name: str, *, file: str | None = None, json: bool = False) -> None:
    """Open a build in Path of Building via pob:// protocol.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    if sys.platform != "win32":
        raise PoeError("pob:// protocol requires Windows with PoB installed")
    if file:
        validate_file_path(file)
    try:
        path = Path(file) if file else resolve_build_file(name)
        xml_str = path.read_text(encoding="utf-8")
    except (FileNotFoundError, BuildNotFoundError):
        raise BuildNotFoundError(f"Build file not found: {file or name}") from None
    except (OSError, UnicodeDecodeError) as e:
        raise PoeError(f"Could not read build file {file or name}: {e}") from e
    code = encode_build(xml_str)
    os.startfile(f"pob://{code}")
    _output({"status": "ok", "code": code}, json_mode=json)


@build_app.command(name="rename")
def builds_rename(name: str, new_name: str, *, json: bool = False) -> None:
    """Rename a build file.

    Parameters
    ----------
    name
        Current build name.
    new_name
        New build name.
    json
        Output raw JSON.
    """
    _output(_svc().rename(name, new_name), json_mode=json)


@build_app.command(name="duplicate")
def builds_duplicate(
    name: str, new_name: str, *, file: str | None = None, json: bool = False
) -> None:
    """Duplicate/clone a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    new_name
        Name for the clone.
    file
        Source file path.
    json
        Output raw JSON.
    """
    _output(_svc().duplicate(name, new_name, file_path=file), json_mode=json)


@build_app.command(name="set-level")
def builds_set_level(name: str, *, level: int, file: str | None = None, json: bool = False) -> None:
    """Set the character level.

    Parameters
    ----------
    name
        Build name or unique prefix.
    level
        Character level (1-100).
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().set_level(name, level, file_path=file), json_mode=json)


@build_app.command(name="set-class")
def builds_set_class(
    name: str,
    *,
    class_name: Annotated[str | None, cyclopts.Parameter(name="--class")] = None,
    ascendancy: str | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Set class and/or ascendancy by name.

    Parameters
    ----------
    name
        Build name or unique prefix.
    class_name
        Class name.
    ascendancy
        Ascendancy name.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(
        _svc().set_class(name, class_name=class_name, ascendancy=ascendancy, file_path=file),
        json_mode=json,
    )


@build_app.command(name="set-bandit")
def builds_set_bandit(
    name: str, *, bandit: str, file: str | None = None, json: bool = False
) -> None:
    """Set the bandit choice.

    Parameters
    ----------
    name
        Build name or unique prefix.
    bandit
        Bandit choice (None, Alira, Kraityn, Oak).
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().set_bandit(name, bandit, file_path=file), json_mode=json)


@build_app.command(name="set-pantheon")
def builds_set_pantheon(
    name: str,
    *,
    major: str | None = None,
    minor: str | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Set pantheon choices.

    Parameters
    ----------
    name
        Build name or unique prefix.
    major
        Major pantheon god.
    minor
        Minor pantheon god.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().set_pantheon(name, major=major, minor=minor, file_path=file), json_mode=json)


@build_app.command(name="summary")
def builds_summary(name: str, *, file: str | None = None, json: bool = False) -> None:
    """Concise build dashboard (class/level/DPS/life/resists).

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().summary(name, file_path=file), json_mode=json)


@build_app.command(name="share")
def builds_share(name: str, *, file: str | None = None, json: bool = False) -> None:
    """Export build as a PoB sharing code.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    if file:
        validate_file_path(file)
    try:
        path = Path(file) if file else resolve_build_file(name)
        xml_str = path.read_text(encoding="utf-8")
    except (FileNotFoundError, BuildNotFoundError):
        raise BuildNotFoundError(f"Build file not found: {file or name}") from None
    except (OSError, UnicodeDecodeError) as e:
        raise PoeError(f"Could not read build file {file or name}: {e}") from e
    code = encode_build(xml_str)
    _output({"status": "ok", "code": code}, json_mode=json)


@build_app.command(name="batch-set-level")
def builds_batch_set_level(
    *,
    level: int,
    builds: Annotated[list[str], cyclopts.Parameter(name="--build")],
    json: bool = False,
) -> None:
    """Set level on multiple builds at once.

    Parameters
    ----------
    level
        Level to set on all builds.
    builds
        Build name(s).
    json
        Output raw JSON.
    """
    svc = _svc()
    results = []
    for name in builds:
        try:
            svc.set_level(name, level)
            results.append({"build": name, "status": "ok"})
        except PoeError as e:
            results.append({"build": name, "status": "error", "error": str(e)})
    _output(results, json_mode=json)


@build_app.command(name="import")
def builds_import(url_or_code: str, *, name: str, json: bool = False) -> None:
    """Import a build from a pobb.in URL or raw build code.

    Parameters
    ----------
    url_or_code
        URL or build code.
    name
        Build name to save as.
    json
        Output raw JSON.
    """
    validate_build_name(name)
    try:
        xml_str = decode_build(
            fetch_build_code(url_or_code) if url_or_code.startswith("http") else url_or_code,
        )
    except (ValueError, zlib.error, OSError, UnicodeDecodeError) as e:
        raise CodecError(f"Failed to import build: {e}") from e
    except httpx.HTTPError as e:
        # Network failures fetching from pobb.in (404 / timeout / connect)
        # bubble as raw httpx exceptions otherwise.
        raise CodecError(f"Failed to fetch {url_or_code!r}: {e}") from e
    try:
        SafeET.fromstring(xml_str)
    except (XMLParseError, ValueError) as e:
        raise CodecError("Decoded content is not valid XML") from e
    claude_dir = get_claude_builds_path()
    filename = name if name.endswith(".xml") else name + ".xml"
    save_path = claude_dir / filename
    try:
        save_path.write_text(xml_str, encoding="utf-8")
    except OSError as e:
        raise CodecError(f"Could not write imported build to {save_path}: {e}") from e
    _output({"status": "ok", "name": name, "saved_to": str(save_path)}, json_mode=json)

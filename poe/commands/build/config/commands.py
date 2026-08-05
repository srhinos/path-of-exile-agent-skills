from __future__ import annotations

import cyclopts

from poe.output import render as _output
from poe.services.build.config_service import ConfigService

config_app = cyclopts.App(name="config", help="Build configuration operations.")


def _svc() -> ConfigService:
    return ConfigService()


@config_app.command(name="get")
def config_get(name: str, *, file: str | None = None, json: bool = False) -> None:
    """Show build configuration (charges, conditions, enemy stats).

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().get(name, file_path=file), json_mode=json)


@config_app.command(name="options")
def config_options(_name: str = "", *, query: str | None = None, json: bool = False) -> None:
    """List available PoB config keys.

    Parameters
    ----------
    query
        Search query.
    json
        Output raw JSON.
    """
    _output(_svc().list_options(query=query), json_mode=json)


@config_app.command(name="sets")
def config_sets(name: str, *, file: str | None = None, json: bool = False) -> None:
    """List config sets.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().list_sets(name, file_path=file), json_mode=json)


@config_app.command(name="add-set")
def config_add_set(name: str, *, title: str = "New Config", file: str | None = None) -> None:
    """Add a new config set.

    Parameters
    ----------
    name
        Build name or unique prefix.
    title
        Config set title.
    file
        Explicit file path.
    """
    _output(_svc().add_set(name, title=title, file_path=file))


@config_app.command(name="remove-set")
def config_remove_set(name: str, *, config_set: str, file: str | None = None) -> None:
    """Remove a config set.

    Parameters
    ----------
    name
        Build name or unique prefix.
    config_set
        Config set ID.
    file
        Explicit file path.
    """
    _output(_svc().remove_set(name, config_set, file_path=file))


@config_app.command(name="switch-set")
def config_switch_set(name: str, *, config_set: str, file: str | None = None) -> None:
    """Switch active config set.

    Parameters
    ----------
    name
        Build name or unique prefix.
    config_set
        Config set ID.
    file
        Explicit file path.
    """
    _output(_svc().switch_set(name, config_set, file_path=file))


@config_app.command(name="preset")
def config_preset(name: str, *, preset: str, file: str | None = None) -> None:
    """Apply a common config preset.

    Parameters
    ----------
    name
        Build name or unique prefix.
    preset
        Preset name (mapping, boss, sirus, shaper).
    file
        Explicit file path.
    """
    _output(_svc().apply_preset(name, preset, file_path=file))


@config_app.command(name="set")
def config_set_values(
    name: str,
    *,
    boolean: list[str] | None = None,
    number: list[str] | None = None,
    string: list[str] | None = None,
    remove: list[str] | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Set configuration values on a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    boolean
        Boolean config: key=true/false.
    number
        Number config: key=value.
    string
        String config: key=value.
    remove
        Remove config key(s).
    file
        Explicit file path.
    """
    result = _svc().set(
        name,
        boolean=boolean,
        number=number,
        string=string,
        remove=remove,
        file_path=file,
    )
    _output(result, json_mode=json)

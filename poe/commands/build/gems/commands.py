from __future__ import annotations

import cyclopts

from poe.output import render as _output
from poe.services.build.gems_service import GemsService

gems_app = cyclopts.App(name="gems", help="Skill gem operations.")


def _svc() -> GemsService:
    return GemsService()


@gems_app.command(name="sets")
def gems_sets(name: str, *, json: bool = False) -> None:
    """List all skill sets in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    json
        Output raw JSON.
    """
    _output(_svc().list_sets(name), json_mode=json)


@gems_app.command(name="list")
def gems_list(name: str, *, skill_set: int | None = None, json: bool = False) -> None:
    """List skill gem setups in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    skill_set
        Skill set ID.
    json
        Output raw JSON.
    """
    _output(_svc().list_gems(name, skill_set=skill_set), json_mode=json)


@gems_app.command(name="add")
def gems_add(
    name: str,
    *,
    slot: str = "",
    gem: list[str],
    level: int = 20,
    quality: int = 0,
    quality_id: str = "Default",
    include_full_dps: bool = False,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Add a skill group with gems to a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Equipment slot.
    gem
        Gem name(s).
    level
        Gem level.
    quality
        Gem quality.
    quality_id
        Alternate quality type.
    include_full_dps
        Include in Full DPS.
    file
        Explicit file path.
    """
    result = _svc().add_group(
        name,
        gems=gem,
        slot=slot,
        level=level,
        quality=quality,
        quality_id=quality_id,
        include_full_dps=include_full_dps,
        file_path=file,
    )
    _output(result, json_mode=json)


@gems_app.command(name="remove")
def gems_remove(name: str, *, index: int, file: str | None = None) -> None:
    """Remove a skill group by index.

    Parameters
    ----------
    name
        Build name or unique prefix.
    index
        Skill group index (0-based).
    file
        Explicit file path.
    """
    _output(_svc().remove_group(name, index, file_path=file))


@gems_app.command(name="edit")
def gems_edit(
    name: str,
    *,
    group: int,
    swap: list[str] | None = None,
    set_level: list[str] | None = None,
    set_quality: list[str] | None = None,
    set_quality_id: list[str] | None = None,
    toggle: list[str] | None = None,
    set_slot: str | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Edit a skill group's gems in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    group
        Skill group index (0-based).
    swap
        Swap gem: OLD,NEW.
    set_level
        Set level: GEM,LEVEL.
    set_quality
        Set quality: GEM,QUALITY.
    toggle
        Toggle gem enabled/disabled.
    set_slot
        Set skill group slot.
    file
        Explicit file path.
    """
    result = _svc().edit_group(
        name,
        group,
        swap=swap,
        set_level=set_level,
        set_quality=set_quality,
        set_quality_id=set_quality_id,
        toggle=toggle,
        set_slot=set_slot,
        file_path=file,
    )
    _output(result, json_mode=json)


@gems_app.command(name="add-to-group")
def gems_add_to_group(
    name: str,
    *,
    group: int,
    gem: str,
    level: int = 20,
    quality: int = 0,
    quality_id: str = "Default",
    file: str | None = None,
) -> None:
    """Add a gem to an existing skill group.

    Parameters
    ----------
    name
        Build name or unique prefix.
    group
        Skill group index (0-based).
    gem
        Gem name to add.
    level
        Gem level.
    quality
        Gem quality.
    quality_id
        Alternate quality type (Default, Anomalous, Divergent, Phantasmal).
    file
        Explicit file path.
    """
    _output(
        _svc().add_gem_to_group(
            name,
            group,
            gem_name=gem,
            level=level,
            quality=quality,
            quality_id=quality_id,
            file_path=file,
        )
    )


@gems_app.command(name="remove-from-group")
def gems_remove_from_group(
    name: str,
    *,
    group: int,
    gem: str,
    file: str | None = None,
) -> None:
    """Remove a gem from a skill group.

    Parameters
    ----------
    name
        Build name or unique prefix.
    group
        Skill group index (0-based).
    gem
        Gem name to remove.
    file
        Explicit file path.
    """
    _output(_svc().remove_gem_from_group(name, group, gem_name=gem, file_path=file))


@gems_app.command(name="add-set")
def gems_add_set(name: str, *, file: str | None = None) -> None:
    """Add a new skill set.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    """
    _output(_svc().add_set(name, file_path=file))


@gems_app.command(name="remove-set")
def gems_remove_set(name: str, *, skill_set: int, file: str | None = None) -> None:
    """Remove a skill set by ID.

    Parameters
    ----------
    name
        Build name or unique prefix.
    skill_set
        Skill set ID to remove.
    file
        Explicit file path.
    """
    _output(_svc().remove_set(name, skill_set, file_path=file))


@gems_app.command(name="set-active")
def gems_set_active(name: str, *, skill_set: int, file: str | None = None) -> None:
    """Set the active skill set.

    Parameters
    ----------
    name
        Build name or unique prefix.
    skill_set
        Skill set ID.
    file
        Explicit file path.
    """
    _output(_svc().set_active(name, skill_set, file_path=file))

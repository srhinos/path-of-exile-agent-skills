from __future__ import annotations

import cyclopts

from poe.output import render as _output
from poe.services.build.flasks_service import FlasksService

flasks_app = cyclopts.App(name="flasks", help="Flask operations.")


def _svc() -> FlasksService:
    return FlasksService()


@flasks_app.command(name="list")
def flasks_list(name: str, *, file: str | None = None, json: bool = False) -> None:
    """List equipped flasks.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().list_flasks(name, file_path=file), json_mode=json)


@flasks_app.command(name="add")
def flasks_add(
    name: str,
    *,
    base: str,
    slot: str | None = None,
    flask_name: str = "New Flask",
    rarity: str = "MAGIC",
    quality: int = 0,
    explicit: list[str] | None = None,
    file: str | None = None,
) -> None:
    """Add a flask to a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    base
        Flask base type.
    slot
        Flask slot (Flask 1-5).
    flask_name
        Flask name.
    rarity
        Flask rarity.
    quality
        Flask quality.
    file
        Explicit file path.
    """
    _output(
        _svc().add_flask(
            name,
            base=base,
            slot=slot,
            flask_name=flask_name,
            rarity=rarity,
            quality=quality,
            explicits=explicit,
            file_path=file,
        )
    )


@flasks_app.command(name="remove")
def flasks_remove(name: str, *, slot: str, file: str | None = None) -> None:
    """Remove a flask from a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Flask slot to remove.
    file
        Explicit file path.
    """
    _output(_svc().remove_flask(name, slot=slot, file_path=file))


@flasks_app.command(name="edit")
def flasks_edit(
    name: str,
    *,
    slot: str,
    set_name: str | None = None,
    set_base: str | None = None,
    set_quality: int | None = None,
    add_explicit: list[str] | None = None,
    remove_explicit: list[int] | None = None,
    file: str | None = None,
) -> None:
    """Edit a flask.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Flask slot to edit.
    set_name
        Set flask name.
    set_base
        Set base type.
    set_quality
        Set quality.
    file
        Explicit file path.
    """
    _output(
        _svc().edit_flask(
            name,
            slot=slot,
            set_name=set_name,
            set_base=set_base,
            set_quality=set_quality,
            add_explicit=add_explicit,
            remove_explicit=remove_explicit,
            file_path=file,
        )
    )


@flasks_app.command(name="reorder")
def flasks_reorder(
    name: str,
    *,
    order: list[str],
    file: str | None = None,
) -> None:
    """Reorder flasks across slots.

    Parameters
    ----------
    name
        Build name or unique prefix.
    order
        Flask slot order (e.g. Flask 1, Flask 3, Flask 2).
    file
        Explicit file path.
    """
    _output(_svc().reorder_flasks(name, order=order, file_path=file))

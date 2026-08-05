from __future__ import annotations

from typing import Annotated

import cyclopts

from poe.output import render as _output
from poe.services.build.jewels_service import JewelsService

jewels_app = cyclopts.App(name="jewels", help="Jewel operations.")


def _svc() -> JewelsService:
    return JewelsService()


@jewels_app.command(name="list")
def jewels_list(name: str, *, file: str | None = None, json: bool = False) -> None:
    """List jewels with tree socket cross-reference.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().list_jewels(name, file_path=file), json_mode=json)


@jewels_app.command(name="add")
def jewels_add(
    name: str,
    *,
    base: str,
    slot: str,
    jewel_name: str = "New Jewel",
    rarity: str = "RARE",
    explicit: list[str] | None = None,
    file: str | None = None,
) -> None:
    """Add a jewel to a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    base
        Jewel base type.
    slot
        Jewel slot name.
    jewel_name
        Jewel name.
    rarity
        Jewel rarity.
    file
        Explicit file path.
    """
    _output(
        _svc().add_jewel(
            name,
            base=base,
            slot=slot,
            jewel_name=jewel_name,
            rarity=rarity,
            explicits=explicit,
            file_path=file,
        )
    )


@jewels_app.command(name="remove")
def jewels_remove(
    name: str,
    *,
    slot: str | None = None,
    item_id: Annotated[int | None, cyclopts.Parameter(name="--id")] = None,
    file: str | None = None,
) -> None:
    """Remove a jewel from a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Remove jewel by slot.
    item_id
        Remove jewel by ID.
    file
        Explicit file path.
    """
    _output(_svc().remove_jewel(name, slot=slot, item_id=item_id, file_path=file))


@jewels_app.command(name="socket")
def jewels_socket(
    name: str,
    *,
    item_id: Annotated[int, cyclopts.Parameter(name="--id")],
    node_id: Annotated[int, cyclopts.Parameter(name="--node")],
    file: str | None = None,
) -> None:
    """Socket a jewel into a tree node.

    Parameters
    ----------
    name
        Build name or unique prefix.
    item_id
        Jewel item ID.
    node_id
        Tree node ID.
    file
        Explicit file path.
    """
    _output(_svc().socket_jewel(name, item_id=item_id, node_id=node_id, file_path=file))


@jewels_app.command(name="unsocket")
def jewels_unsocket(
    name: str,
    *,
    item_id: Annotated[int | None, cyclopts.Parameter(name="--id")] = None,
    node_id: Annotated[int | None, cyclopts.Parameter(name="--node")] = None,
    file: str | None = None,
) -> None:
    """Unsocket a jewel from a tree node.

    Parameters
    ----------
    name
        Build name or unique prefix.
    item_id
        Jewel item ID.
    node_id
        Tree node ID.
    file
        Explicit file path.
    """
    _output(_svc().unsocket_jewel(name, item_id=item_id, node_id=node_id, file_path=file))

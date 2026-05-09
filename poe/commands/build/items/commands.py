from __future__ import annotations

from typing import Annotated

import cyclopts

from poe.output import render as _output
from poe.services.build.items_service import ItemsService

items_app = cyclopts.App(name="items", help="Item operations.")


def _svc() -> ItemsService:
    return ItemsService()


@items_app.command(name="sets")
def items_sets(name: str, *, json: bool = False) -> None:
    """List all item sets in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    json
        Output raw JSON.
    """
    _output(_svc().list_sets(name), json_mode=json)


@items_app.command(name="list")
def items_list(
    name: str, *, item_set: str | None = None, file: str | None = None, json: bool = False
) -> None:
    """List equipped items in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    item_set
        Item set ID.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().list_items(name, item_set=item_set, file_path=file), json_mode=json)


@items_app.command(name="add")
def items_add(
    name: str,
    *,
    slot: str,
    base: str,
    rarity: str = "RARE",
    item_name: str = "New Item",
    armour: int = 0,
    evasion: int = 0,
    energy_shield: int = 0,
    quality: int = 0,
    sockets: str = "",
    level_req: int = 0,
    influence: list[str] | None = None,
    implicit: list[str] | None = None,
    explicit: list[str] | None = None,
    crafted_mod: list[str] | None = None,
    fractured_mod: list[str] | None = None,
    synthesised: bool = False,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Add an item to a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Equipment slot.
    base
        Base type.
    rarity
        Item rarity.
    item_name
        Item name.
    armour
        Base armour.
    evasion
        Base evasion.
    energy_shield
        Base energy shield.
    quality
        Quality.
    sockets
        Socket string.
    level_req
        Level requirement.
    influence
        Influence(s).
    implicit
        Implicit mod(s).
    explicit
        Explicit mod(s).
    crafted_mod
        Crafted mod(s).
    fractured_mod
        Fractured mod(s).
    synthesised
        Mark as synthesised.
    file
        Explicit file path.
    """
    result = _svc().add_item(
        name,
        slot=slot,
        base=base,
        rarity=rarity,
        item_name=item_name,
        armour=armour,
        evasion=evasion,
        energy_shield=energy_shield,
        quality=quality,
        sockets=sockets,
        level_req=level_req,
        influences=influence,
        implicits=implicit,
        explicits=explicit,
        crafted_mods=crafted_mod,
        fractured_mods=fractured_mod,
        synthesised=synthesised,
        file_path=file,
    )
    _output(result, json_mode=json)


@items_app.command(name="remove")
def items_remove(
    name: str,
    *,
    slot: str | None = None,
    item_id: Annotated[int | None, cyclopts.Parameter(name="--id")] = None,
    file: str | None = None,
) -> None:
    """Remove an item from a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Remove item by slot name.
    item_id
        Remove item by ID.
    file
        Explicit file path.
    """
    _output(_svc().remove_item(name, slot=slot, item_id=item_id, file_path=file))


@items_app.command(name="edit")
def items_edit(
    name: str,
    *,
    slot: str,
    add_explicit: list[str] | None = None,
    remove_explicit: list[int] | None = None,
    add_implicit: list[str] | None = None,
    remove_implicit: list[int] | None = None,
    set_name: str | None = None,
    set_base: str | None = None,
    set_rarity: str | None = None,
    set_quality: int | None = None,
    set_sockets: str | None = None,
    set_influences: list[str] | None = None,
    set_armour: int | None = None,
    set_evasion: int | None = None,
    set_energy_shield: int | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Edit an existing item in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Equipment slot of the item to edit.
    add_explicit
        Add explicit mod.
    remove_explicit
        Remove explicit by index.
    add_implicit
        Add implicit mod.
    remove_implicit
        Remove implicit by index.
    set_name
        Set item name.
    set_base
        Set base type.
    set_rarity
        Set rarity.
    set_quality
        Set quality.
    file
        Explicit file path.
    """
    result = _svc().edit_item(
        name,
        slot=slot,
        add_explicit=add_explicit,
        remove_explicit=remove_explicit,
        add_implicit=add_implicit,
        remove_implicit=remove_implicit,
        set_name=set_name,
        set_base=set_base,
        set_rarity=set_rarity,
        set_quality=set_quality,
        set_sockets=set_sockets,
        set_influences=set_influences,
        set_armour=set_armour,
        set_evasion=set_evasion,
        set_energy_shield=set_energy_shield,
        file_path=file,
    )
    _output(result, json_mode=json)


@items_app.command(name="set-active")
def items_set_active(name: str, *, item_set: str, file: str | None = None) -> None:
    """Set the active item set.

    Parameters
    ----------
    name
        Build name or unique prefix.
    item_set
        Item set ID.
    file
        Explicit file path.
    """
    _output(_svc().set_active(name, item_set, file_path=file))


@items_app.command(name="add-set")
def items_add_set(name: str, *, file: str | None = None) -> None:
    """Add a new empty item set to a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    file
        Explicit file path.
    """
    _output(_svc().add_set(name, file_path=file))


@items_app.command(name="remove-set")
def items_remove_set(name: str, *, item_set: str, file: str | None = None) -> None:
    """Remove an item set by ID.

    Parameters
    ----------
    name
        Build name or unique prefix.
    item_set
        Item set ID to remove.
    file
        Explicit file path.
    """
    _output(_svc().remove_set(name, item_set, file_path=file))


@items_app.command(name="import")
def items_import(name: str, *, slot: str, text: str, file: str | None = None) -> None:
    """Import an item from pasted text into a slot.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Equipment slot.
    text
        Pasted item text.
    file
        Explicit file path.
    """
    _output(_svc().import_item_text(name, slot=slot, item_text=text, file_path=file))


@items_app.command(name="move")
def items_move(
    name: str,
    *,
    from_slot: Annotated[str, cyclopts.Parameter(name="--from")],
    to_slot: Annotated[str, cyclopts.Parameter(name="--to")],
    file: str | None = None,
) -> None:
    """Move an item between slots.

    Parameters
    ----------
    name
        Build name or unique prefix.
    from_slot
        Source slot.
    to_slot
        Destination slot.
    file
        Explicit file path.
    """
    _output(_svc().move_item(name, from_slot=from_slot, to_slot=to_slot, file_path=file))


@items_app.command(name="swap")
def items_swap(name: str, *, slot1: str, slot2: str, file: str | None = None) -> None:
    """Swap items between two slots.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot1
        First slot.
    slot2
        Second slot.
    file
        Explicit file path.
    """
    _output(_svc().swap_items(name, slot1=slot1, slot2=slot2, file_path=file))


@items_app.command(name="compare")
def items_compare(
    name: str,
    *,
    slot: str,
    name2: Annotated[str | None, cyclopts.Parameter(name="--build2")] = None,
    file: str | None = None,
    file2: str | None = None,
    json: bool = False,
) -> None:
    """Compare items in a slot between builds or item sets.

    Parameters
    ----------
    name
        Build name or unique prefix.
    slot
        Slot to compare.
    name2
        Second build name.
    file
        Explicit file path.
    file2
        Explicit file path for second build.
    json
        Output raw JSON.
    """
    _output(
        _svc().compare_items(name, slot, name2=name2, file_path=file, file_path2=file2),
        json_mode=json,
    )


@items_app.command(name="search")
def items_search(
    name: str,
    *,
    mod: str | None = None,
    slot: str | None = None,
    influence: str | None = None,
    rarity: str | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Search equipped items with filters.

    Parameters
    ----------
    name
        Build name or unique prefix.
    mod
        Substring match on mod text.
    slot
        Filter by slot type.
    influence
        Filter by influence.
    rarity
        Filter by rarity.
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    result = _svc().search(
        name,
        mod=mod,
        slot=slot,
        influence=influence,
        rarity=rarity,
        file_path=file,
    )
    _output(result, json_mode=json)

from __future__ import annotations

import cyclopts

from poe.output import render as _output
from poe.services.build.tree_service import TreeService

tree_app = cyclopts.App(name="tree", help="Passive tree operations.")


def _svc() -> TreeService:
    return TreeService()


@tree_app.command(name="specs")
def tree_specs(name: str, *, json: bool = False) -> None:
    """List all tree specs in a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    json
        Output raw JSON.
    """
    _output(_svc().get_specs(name), json_mode=json)


@tree_app.command(name="get")
def tree_get(name: str, *, spec: int | None = None, json: bool = False) -> None:
    """Get tree allocation for a spec.

    Parameters
    ----------
    name
        Build name or unique prefix.
    spec
        Spec index (1-based).
    json
        Output raw JSON.
    """
    _output(_svc().get_tree(name, spec_index=spec), json_mode=json)


@tree_app.command(name="compare")
def tree_compare(name1: str, name2: str, *, json: bool = False) -> None:
    """Compare tree allocations between two builds.

    Parameters
    ----------
    name1
        First build name.
    name2
        Second build name.
    json
        Output raw JSON.
    """
    _output(_svc().compare_trees(name1, name2), json_mode=json)


@tree_app.command(name="set")
def tree_set(
    name: str,
    *,
    nodes: str | None = None,
    add_nodes: str | None = None,
    remove_nodes: str | None = None,
    mastery: list[str] | None = None,
    add_mastery: list[str] | None = None,
    remove_mastery: list[str] | None = None,
    class_id: int | None = None,
    ascend_class_id: int | None = None,
    tree_version: str | None = None,
    spec: int | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Set or modify tree allocation for a spec.

    Parameters
    ----------
    name
        Build name or unique prefix.
    nodes
        Comma-separated node IDs (replaces all).
    add_nodes
        Comma-separated node IDs to add.
    remove_nodes
        Comma-separated node IDs to remove.
    mastery
        Mastery as nodeId:effectId.
    class_id
        Class ID.
    ascend_class_id
        Ascendancy class ID.
    tree_version
        Tree version.
    spec
        Spec index (1-based).
    file
        Explicit file path.
    """
    result = _svc().set_tree(
        name,
        nodes=nodes,
        add_nodes=add_nodes,
        remove_nodes=remove_nodes,
        mastery=mastery or [],
        add_mastery=add_mastery,
        remove_mastery=remove_mastery,
        class_id=class_id,
        ascend_class_id=ascend_class_id,
        tree_version=tree_version,
        spec_index=spec,
        file_path=file,
    )
    _output(result, json_mode=json)


@tree_app.command(name="search")
def tree_search(
    name: str,
    query: str,
    *,
    spec: int | None = None,
    file: str | None = None,
    json: bool = False,
) -> None:
    """Search allocated tree nodes by node ID or override name.

    Matches node IDs as substrings and cluster/timeless jewel override
    names and descriptions. Normal passive nodes cannot be searched by
    name (PoB builds only store node IDs, not names).

    Parameters
    ----------
    name
        Build name or unique prefix.
    query
        Search query (node ID substring or override name).
    spec
        Tree spec index (1-based).
    file
        Explicit file path.
    json
        Output raw JSON.
    """
    _output(_svc().search_nodes(name, query, spec_index=spec, file_path=file), json_mode=json)


@tree_app.command(name="set-active")
def tree_set_active(name: str, *, spec: int, file: str | None = None) -> None:
    """Set the active tree spec.

    Parameters
    ----------
    name
        Build name or unique prefix.
    spec
        Spec index (1-based).
    file
        Explicit file path.
    """
    _output(_svc().set_active(name, spec, file_path=file))


@tree_app.command(name="add-spec")
def tree_add_spec(name: str, *, title: str = "", file: str | None = None) -> None:
    """Add a new empty tree spec to a build.

    Parameters
    ----------
    name
        Build name or unique prefix.
    title
        Title for the new spec.
    file
        Explicit file path.
    """
    _output(_svc().add_spec(name, title=title, file_path=file))


@tree_app.command(name="remove-spec")
def tree_remove_spec(name: str, *, spec: int, file: str | None = None) -> None:
    """Remove a tree spec by index.

    Parameters
    ----------
    name
        Build name or unique prefix.
    spec
        Spec index (1-based).
    file
        Explicit file path.
    """
    _output(_svc().remove_spec(name, spec, file_path=file))

from __future__ import annotations

import contextlib
import math
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from poe.services.build.constants import INFLUENCE_TO_LINE

if TYPE_CHECKING:
    from poe.models.build.build import BuildDocument
    from poe.models.build.config import ConfigEntry
    from poe.models.build.gems import Gem, GemGroup
    from poe.models.build.items import Item, ItemMod
    from poe.models.build.tree import MasteryMapping


def _rotate_backups(path: Path) -> None:
    """Rotate .bak.1 → .bak.2 → .bak.3, then current → .bak.1."""
    bak3 = path.with_suffix(".xml.bak.3")
    bak2 = path.with_suffix(".xml.bak.2")
    bak1 = path.with_suffix(".xml.bak.1")
    with contextlib.suppress(OSError):
        bak3.unlink()
    with contextlib.suppress(OSError):
        bak2.rename(bak3)
    with contextlib.suppress(OSError):
        bak1.rename(bak2)
    shutil.copy2(path, bak1)


def write_build_file(build: BuildDocument, path: Path) -> None:
    """Write a Build to a PoB .xml file. Atomic write with rotating backups."""
    if path.exists():
        _rotate_backups(path)

    root = build_to_xml(build)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".xml.tmp")
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as f:
            tree.write(f, encoding="UTF-8", xml_declaration=True)
        tmp_path.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def build_to_xml(build: BuildDocument) -> ET.Element:
    """Convert Build to XML Element tree."""
    root = ET.Element("PathOfBuilding")
    _write_build_section(root, build)
    _write_tree_section(root, build)
    _write_skills_section(root, build)
    _write_items_section(root, build)
    _write_config_section(root, build)
    _write_notes(root, build)
    _write_import(root, build)
    _write_passthrough_sections(root, build)
    return root


def build_to_string(build: BuildDocument) -> str:
    """Convert Build to XML string."""
    root = build_to_xml(build)
    ET.indent(root, space="\t")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _write_build_section(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Build> section."""
    el = ET.SubElement(root, "Build")
    el.set("level", str(build.level))
    el.set("className", build.class_name)
    el.set("ascendClassName", build.ascend_class_name)
    el.set("bandit", build.bandit or "None")
    el.set("viewMode", build.view_mode)
    el.set("targetVersion", build.target_version)
    el.set("mainSocketGroup", str(build.main_socket_group))
    el.set("pantheonMajorGod", build.pantheon_major)
    el.set("pantheonMinorGod", build.pantheon_minor)
    if build.character_level_auto_mode:
        el.set("characterLevelAutoMode", "true")

    for stat in build.player_stats:
        stat_el = ET.SubElement(el, "PlayerStat")
        stat_el.set("stat", stat.stat)
        stat_el.set("value", _fmt_number(stat.value))

    for stat in build.minion_stats:
        stat_el = ET.SubElement(el, "MinionStat")
        stat_el.set("stat", stat.stat)
        stat_el.set("value", _fmt_number(stat.value))

    for spectre_id in build.spectres:
        spectre_el = ET.SubElement(el, "Spectre")
        spectre_el.set("id", spectre_id)

    for dps_entry in build.full_dps_skills:
        dps_el = ET.SubElement(el, "FullDPSSkill")
        for k, v in dps_entry.items():
            dps_el.set(k, str(v))

    if build.timeless_data:
        _write_timeless_data(el, build.timeless_data)


def _write_timeless_data(parent: ET.Element, data: dict) -> None:
    """Write <TimelessData> element with attributes and children.

    Parser stores child elements under a "children" subdict so a child
    tag matching an attribute name can't collide. The writer mirrors this:
    attributes live in the top dict, children come from data["children"]
    (a dict[str, list[dict[str, str]]]).
    """
    td_el = ET.SubElement(parent, "TimelessData")
    children = data.get("children") or {}
    for k, v in data.items():
        if k == "children":
            continue
        # Legacy shape: list values at the top dict level were treated as
        # children. Tolerate this on write so old-shape in-memory builds
        # still serialize correctly.
        if isinstance(v, list):
            for child_attrs in v:
                if isinstance(child_attrs, dict):
                    child_el = ET.SubElement(td_el, k)
                    for ck, cv in child_attrs.items():
                        child_el.set(ck, str(cv))
        else:
            td_el.set(k, str(v))
    if isinstance(children, dict):
        for tag, entries in children.items():
            if not isinstance(entries, list):
                continue
            for child_attrs in entries:
                if isinstance(child_attrs, dict):
                    child_el = ET.SubElement(td_el, tag)
                    for ck, cv in child_attrs.items():
                        child_el.set(ck, str(cv))


def _write_tree_section(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Tree> section with specs."""
    tree_el = ET.SubElement(root, "Tree")
    tree_el.set("activeSpec", str(build.active_spec))

    for spec in build.specs:
        spec_el = ET.SubElement(tree_el, "Spec")
        if spec.title:
            spec_el.set("title", spec.title)
        if spec.tree_version:
            spec_el.set("treeVersion", spec.tree_version)
        spec_el.set("classId", str(spec.class_id))
        spec_el.set("ascendClassId", str(spec.ascend_class_id))
        if spec.secondary_ascend_class_id:
            spec_el.set("secondaryAscendClassId", str(spec.secondary_ascend_class_id))

        if spec.nodes:
            spec_el.set("nodes", ",".join(str(n) for n in spec.nodes))

        if spec.mastery_effects:
            spec_el.set("masteryEffects", _mastery_effects_to_str(spec.mastery_effects))

        if spec.url:
            url_el = ET.SubElement(spec_el, "URL")
            url_el.text = spec.url

        if spec.sockets:
            sockets_el = ET.SubElement(spec_el, "Sockets")
            for sock in spec.sockets:
                sock_el = ET.SubElement(sockets_el, "Socket")
                sock_el.set("nodeId", str(sock.node_id))
                sock_el.set("itemId", str(sock.item_id))

        if spec.overrides:
            overrides_el = ET.SubElement(spec_el, "Overrides")
            for ov in spec.overrides:
                ov_el = ET.SubElement(overrides_el, "Override")
                ov_el.set("nodeId", str(ov.node_id))
                ov_el.set("dn", ov.name)
                if ov.icon:
                    ov_el.set("icon", ov.icon)
                if ov.effect_image:
                    ov_el.set("activeEffectImage", ov.effect_image)
                if ov.text:
                    ov_el.text = ov.text


def _mastery_effects_to_str(effects: list[MasteryMapping]) -> str:
    """Serialize mastery effects to '{nodeId,effectId},{nodeId,effectId}' format."""
    return ",".join(f"{{{m.node_id},{m.effect_id}}}" for m in effects)


def _write_skills_section(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Skills> section."""
    skills_el = ET.SubElement(root, "Skills")
    skills_el.set("activeSkillSet", str(build.active_skill_set))
    if build.default_gem_level:
        skills_el.set("defaultGemLevel", str(build.default_gem_level))
    if build.default_gem_quality:
        skills_el.set("defaultGemQuality", str(build.default_gem_quality))
    if build.sort_gems_by_dps:
        skills_el.set("sortGemsByDPS", "true")
    if build.sort_gems_by_dps_field:
        skills_el.set("sortGemsByDPSField", build.sort_gems_by_dps_field)
    if build.show_alt_quality_gems:
        skills_el.set("showAltQualityGems", "true")
    if build.show_support_gem_types:
        skills_el.set("showSupportGemTypes", build.show_support_gem_types)
    if build.show_legacy_gems:
        skills_el.set("showLegacyGems", "true")

    if build.skill_sets:
        for sid in build.skill_set_ids or sorted(build.skill_sets):
            ss_el = ET.SubElement(skills_el, "SkillSet")
            ss_el.set("id", str(sid))
            title = build.skill_set_titles.get(sid, "")
            if title:
                ss_el.set("title", title)
            for sg in build.skill_sets.get(sid, []):
                _write_skill_group(ss_el, sg)
    else:
        skill_set_ids = build.skill_set_ids or [build.active_skill_set]
        for sid in skill_set_ids:
            ss_el = ET.SubElement(skills_el, "SkillSet")
            ss_el.set("id", str(sid))
            if sid == build.active_skill_set:
                for sg in build.skill_groups:
                    _write_skill_group(ss_el, sg)


def _write_skill_group(parent: ET.Element, sg: GemGroup) -> None:
    """Write a <Skill> element (skill group with gems)."""
    skill_el = ET.SubElement(parent, "Skill")
    if sg.slot:
        skill_el.set("slot", sg.slot)
    if sg.label:
        skill_el.set("label", sg.label)
    skill_el.set("enabled", str(sg.enabled).lower())
    if sg.include_in_full_dps:
        skill_el.set("includeInFullDPS", "true")
    skill_el.set("mainActiveSkill", str(sg.main_active_skill))
    if sg.main_active_skill_calcs:
        skill_el.set("mainActiveSkillCalcs", str(sg.main_active_skill_calcs))
    if sg.group_count:
        skill_el.set("groupCount", str(sg.group_count))
    if sg.source:
        skill_el.set("source", sg.source)

    for gem in sg.gems:
        _write_gem(skill_el, gem)


_GEM_OPTIONAL_STR_ATTRS = (
    ("skill_id", "skillId"),
    ("gem_id", "gemId"),
    ("variant_id", "variantId"),
    ("skill_part", "skillPart"),
    ("skill_part_calcs", "skillPartCalcs"),
    ("skill_minion", "skillMinion"),
    ("skill_minion_skill", "skillMinionSkill"),
    ("skill_minion_skill_calcs", "skillMinionSkillCalcs"),
    ("skill_minion_item_set", "skillMinionItemSet"),
    ("skill_minion_item_set_calcs", "skillMinionItemSetCalcs"),
    ("skill_stage_count", "skillStageCount"),
    ("skill_stage_count_calcs", "skillStageCountCalcs"),
    ("skill_mine_count", "skillMineCount"),
    ("skill_mine_count_calcs", "skillMineCountCalcs"),
)


def _write_gem(parent: ET.Element, gem: Gem) -> None:
    """Write a <Gem> element."""
    gem_el = ET.SubElement(parent, "Gem")
    gem_el.set("nameSpec", gem.name_spec)
    gem_el.set("level", str(gem.level))
    gem_el.set("quality", str(gem.quality))
    gem_el.set("qualityId", gem.quality_id)
    gem_el.set("enabled", str(gem.enabled).lower())
    if not gem.enable_global1:
        gem_el.set("enableGlobal1", "false")
    if not gem.enable_global2:
        gem_el.set("enableGlobal2", "false")
    gem_el.set("count", str(gem.count))
    for field, attr in _GEM_OPTIONAL_STR_ATTRS:
        val = getattr(gem, field, "")
        if val:
            gem_el.set(attr, val)


_VARIANT_ALT_PAIRS = (
    ("variant_alt", "variantAlt"),
    ("variant_alt2", "variantAlt2"),
    ("variant_alt3", "variantAlt3"),
    ("variant_alt4", "variantAlt4"),
    ("variant_alt5", "variantAlt5"),
)


def _write_items_section(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Items> section."""
    items_el = ET.SubElement(root, "Items")
    items_el.set("activeItemSet", str(build.active_item_set))
    if build.items_use_second_weapon_set:
        items_el.set("useSecondWeaponSet", "true")
    if build.items_show_stat_differences:
        items_el.set("showStatDifferences", "true")

    for item in build.items:
        item_el = ET.SubElement(items_el, "Item")
        item_el.set("id", str(item.id))
        if item.variant:
            item_el.set("variant", item.variant)
        for field, attr in _VARIANT_ALT_PAIRS:
            val = getattr(item, field, "")
            if val:
                item_el.set(attr, val)
        item_el.text = "\n" + _item_to_text(item) + "\n"
        for mr_id, mr_range in item.mod_ranges.items():
            mr_el = ET.SubElement(item_el, "ModRange")
            mr_el.set("id", mr_id)
            mr_el.set("range", _fmt_number(mr_range))

    for item_set in build.item_sets:
        set_el = ET.SubElement(items_el, "ItemSet")
        set_el.set("id", str(item_set.id))
        if item_set.title:
            set_el.set("title", item_set.title)
        if item_set.use_second_weapon_set:
            set_el.set("useSecondWeaponSet", "true")

        for slot in item_set.slots:
            slot_el = ET.SubElement(set_el, "Slot")
            slot_el.set("name", slot.name)
            slot_el.set("itemId", str(slot.item_id))
            if not slot.active:
                slot_el.set("active", "false")
            if slot.item_pb_url:
                slot_el.set("itemPbURL", slot.item_pb_url)

        for sock in item_set.socket_id_urls:
            sock_el = ET.SubElement(set_el, "SocketIdURL")
            sock_el.set("nodeId", str(sock.node_id))
            sock_el.set("itemId", str(sock.item_id))


def _item_to_text(item: Item) -> str:
    """Reconstruct PoB item text from structured fields.

    If item.text is already set, return it as-is (preserves original formatting).
    """
    if item.text:
        return item.text

    lines: list[str] = []

    if item.rarity:
        lines.append(f"Rarity: {item.rarity}")

    if item.name:
        lines.append(item.name)
    if item.base_type:
        lines.append(item.base_type)

    for inf in item.influences:
        line = INFLUENCE_TO_LINE.get(inf, f"{inf} Item")
        lines.append(line)

    if item.is_synthesised:
        lines.append("Synthesised Item")

    if item.is_fractured:
        lines.append("Fractured Item")

    if item.is_crafted:
        lines.append("Crafted: true")

    _append_item_metadata_lines(item, lines)

    lines.append(f"Implicits: {len(item.implicits)}")
    lines.extend(_mod_to_line(mod) for mod in item.implicits)

    lines.extend(f"Prefix: {s if s is not None else 'None'}" for s in item.prefix_slots)
    lines.extend(f"Suffix: {s if s is not None else 'None'}" for s in item.suffix_slots)

    lines.extend(_mod_to_line(mod) for mod in item.explicits)

    _append_item_state_lines(item, lines)

    return "\n".join(lines)


_ITEM_METADATA_FIELDS = (
    ("unique_id", "Unique ID: "),
    ("item_level", "Item Level: "),
    ("item_class", "Item Class: "),
    ("armour", "Armour: "),
    ("evasion", "Evasion: "),
    ("energy_shield", "Energy Shield: "),
    ("ward", "Ward: "),
    ("quality", "Quality: "),
    ("sockets", "Sockets: "),
    ("level_req", "LevelReq: "),
    ("catalyst_type", "Catalyst: "),
    ("catalyst_quality", "CatalystQuality: "),
    ("talisman_tier", "Talisman Tier: "),
    ("cluster_jewel_skill", "Cluster Jewel Skill: "),
    ("cluster_jewel_node_count", "Cluster Jewel Node Count: "),
    ("jewel_radius", "Radius: "),
    ("limited_to", "Limited to: "),
)


def _append_item_metadata_lines(item: Item, lines: list[str]) -> None:
    """Append item metadata lines (defenses, quality, sockets, etc.) to output."""
    for attr, prefix in _ITEM_METADATA_FIELDS:
        val = getattr(item, attr, None)
        if val:
            lines.append(f"{prefix}{val}")
    if item.foil_type:
        lines.append(item.foil_type)


_ITEM_STATE_LINES = (
    ("is_corrupted", "Corrupted"),
    ("is_mirrored", "Mirrored"),
    ("is_split", "Split"),
    ("has_veiled_prefix", "Has Veiled Prefix"),
    ("has_veiled_suffix", "Has Veiled Suffix"),
)


def _append_item_state_lines(item: Item, lines: list[str]) -> None:
    """Append item state lines (corrupted, mirrored, etc.) to output."""
    for attr, text in _ITEM_STATE_LINES:
        if getattr(item, attr, False):
            lines.append(text)


def _mod_to_line(mod: ItemMod) -> str:
    """Serialize ItemMod to text with markers."""
    parts: list[str] = []

    if mod.is_crafted:
        parts.append("{crafted}")
    if mod.is_custom:
        parts.append("{custom}")
    if mod.is_fractured:
        parts.append("{fractured}")
    if mod.is_exarch:
        parts.append("{exarch}")
    if mod.is_eater:
        parts.append("{eater}")
    if mod.is_enchant:
        parts.append("{enchant}")
    if mod.is_scourge:
        parts.append("{scourge}")
    if mod.is_crucible:
        parts.append("{crucible}")
    if mod.is_synthesis:
        parts.append("{synthesis}")
    if mod.is_mutated:
        parts.append("{mutated}")
    if mod.tags:
        parts.append("{tags:" + ",".join(mod.tags) + "}")
    if mod.range_value is not None:
        parts.append("{range:" + _fmt_range(mod.range_value) + "}")
    if mod.variant:
        parts.append("{variant:" + mod.variant + "}")

    parts.append(mod.text)
    return "".join(parts)


def _write_config_section(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Config> section."""
    config_el = ET.SubElement(root, "Config")
    config_el.set("activeConfigSet", str(build.active_config_set))

    for cs in build.config_sets:
        set_el = ET.SubElement(config_el, "ConfigSet")
        set_el.set("id", str(cs.id))
        set_el.set("title", cs.title)

        for inp in cs.inputs:
            _write_config_input(set_el, "Input", inp)

        for ph in cs.placeholders:
            _write_config_input(set_el, "Placeholder", ph)


def _write_config_input(parent: ET.Element, tag: str, inp: ConfigEntry) -> None:
    """Write an <Input> or <Placeholder> element."""
    el = ET.SubElement(parent, tag)
    el.set("name", inp.name)
    if inp.input_type == "boolean":
        el.set("boolean", str(inp.value).lower())
    elif inp.input_type == "number":
        el.set("number", _fmt_number(inp.value))
    else:
        el.set("string", str(inp.value))


def _write_notes(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Notes> section."""
    notes_el = ET.SubElement(root, "Notes")
    notes_el.text = build.notes


def _write_import(root: ET.Element, build: BuildDocument) -> None:
    """Write the <Import> section."""
    has_import = (
        build.import_link
        or build.import_last_realm
        or build.import_last_character_hash
        or build.import_last_account_hash
        or build.import_export_party
    )
    if has_import:
        import_el = ET.SubElement(root, "Import")
        if build.import_link:
            import_el.set("importLink", build.import_link)
        if build.import_last_realm:
            import_el.set("lastRealm", build.import_last_realm)
        if build.import_last_character_hash:
            import_el.set("lastCharacterHash", build.import_last_character_hash)
        if build.import_last_account_hash:
            import_el.set("lastAccountHash", build.import_last_account_hash)
        if build.import_export_party:
            import_el.set("exportParty", build.import_export_party)


def _write_passthrough_sections(root: ET.Element, build: BuildDocument) -> None:
    """Write back preserved XML sections verbatim."""
    for xml_str in build.passthrough_sections.values():
        el = ET.fromstring(xml_str)
        root.append(el)


def _fmt_number(value) -> str:
    """Format a number: use int form for whole numbers, otherwise float."""
    if isinstance(value, float):
        if not math.isfinite(value):
            return "0"
        if value == int(value):
            return str(int(value))
    return str(value)


def _fmt_range(value: float) -> str:
    """Format range value: 0.5 → '0.5', 1.0 → '1'."""
    if not math.isfinite(value):
        return "0"
    if value == int(value):
        return str(int(value))
    return str(value)

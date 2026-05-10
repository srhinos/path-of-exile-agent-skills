from __future__ import annotations

import contextlib
import functools
import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree as SafeET

from poe.constants import ITEM_INT_FIELD_BOUNDS, VERSION_PATTERN
from poe.models.build.build import BuildDocument
from poe.models.build.config import BuildConfig, ConfigEntry
from poe.models.build.gems import Gem, GemGroup
from poe.models.build.items import Item, ItemMod, ItemSet, ItemSlot
from poe.models.build.stats import StatEntry
from poe.models.build.tree import MasteryMapping, TreeOverride, TreeSocket, TreeSpec
from poe.services.build.constants import (
    AFFIX_NO_MATCH,
    FLASK_BASE_RE,
    INFLUENCE_LINES,
    MAGIC_SUFFIX_RE,
    METADATA_PREFIXES,
    MIN_KEYWORD_LENGTH,
    MOD_KEYWORD_NOISE,
    PREFIX_RE,
    SLOT_MOD_RE,
    SUFFIX_RE,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

_logger = logging.getLogger("poe.parser")


def _safe_int(val: str, default: int = 0) -> int:
    """Parse an int, returning default for non-numeric values like 'nil'."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _clamp_int(val: int, *, lo: int, hi: int | None, field: str, context: str) -> int:
    """Clamp val to [lo, hi]. Logs a warning when clamped. hi=None means no upper bound."""
    if val < lo:
        _logger.warning("%s: %s=%d below minimum %d, clamping", context, field, val, lo)
        return lo
    if hi is not None and val > hi:
        _logger.warning("%s: %s=%d above maximum %d, clamping", context, field, val, hi)
        return hi
    return val


def parse_build_file(path: Path, *, skill_set_id: int | None = None) -> BuildDocument:
    """Parse a PoB .xml build file into a Build object.

    If skill_set_id is given, parse that specific skill set instead of the active one.
    """
    tree = SafeET.parse(str(path))
    root = tree.getroot()
    if root is None:
        raise ValueError(f"Empty or invalid XML: {path}")
    build = BuildDocument()

    _parse_build_section(root, build)
    _parse_tree_section(root, build)
    _parse_skills_section(root, build, skill_set_id=skill_set_id)
    _parse_items_section(root, build)
    _parse_config_section(root, build)
    _parse_notes(root, build)
    _parse_import(root, build)
    _parse_passthrough_sections(root, build)

    return build


def _parse_build_section(root: Element, build: BuildDocument) -> None:
    """Parse the <Build> section."""
    el = root.find("Build")
    if el is None:
        return

    build.class_name = el.get("className", "")
    build.ascend_class_name = el.get("ascendClassName", "")
    raw_level = _safe_int(el.get("level", "1"), 1)
    build.level = _clamp_int(raw_level, lo=1, hi=100, field="level", context="build")
    raw_bandit = el.get("bandit", "")
    build.bandit = raw_bandit if raw_bandit and raw_bandit != "None" else None
    build.view_mode = el.get("viewMode", "TREE")
    raw_target = el.get("targetVersion", "3_0")
    if raw_target and not VERSION_PATTERN.match(raw_target):
        _logger.warning(
            "targetVersion=%r does not match X_Y format, defaulting to '3_0'", raw_target
        )
        raw_target = "3_0"
    build.target_version = raw_target or "3_0"
    build.main_socket_group = _safe_int(el.get("mainSocketGroup", "1"), 1)
    build.pantheon_major = el.get("pantheonMajorGod", "")
    build.pantheon_minor = el.get("pantheonMinorGod", "")
    build.character_level_auto_mode = el.get("characterLevelAutoMode", "false").casefold() == "true"

    for stat_el in el.findall("PlayerStat"):
        stat = _parse_stat_element(stat_el)
        if stat is not None:
            build.player_stats.append(stat)

    for stat_el in el.findall("MinionStat"):
        stat = _parse_stat_element(stat_el)
        if stat is not None:
            build.minion_stats.append(stat)

    for spectre_el in el.findall("Spectre"):
        spectre_id = spectre_el.get("id", "")
        if spectre_id:
            build.spectres.append(spectre_id)

    for dps_el in el.findall("FullDPSSkill"):
        entry = dict(dps_el.attrib.items())
        if entry:
            if "value" in entry:
                with contextlib.suppress(ValueError):
                    entry["value"] = float(entry["value"])
            build.full_dps_skills.append(entry)

    timeless_el = el.find("TimelessData")
    if timeless_el is not None:
        build.timeless_data = dict(timeless_el.attrib.items())
        for child in timeless_el:
            tag = child.tag
            if tag not in build.timeless_data:
                build.timeless_data[tag] = []
            if isinstance(build.timeless_data[tag], list):
                build.timeless_data[tag].append(dict(child.attrib.items()))


def _parse_stat_element(stat_el: Element) -> StatEntry | None:
    """Parse a <PlayerStat>/<MinionStat>. Returns None on empty stat or non-finite value.

    PoB writes inf for capped stats (over-cap, infinite recoup) and nan for
    divide-by-zero. Both cases warn and skip rather than crashing the parse.
    """
    name = stat_el.get("stat", "")
    if not name:
        _logger.warning("stat element missing 'stat' attribute, skipping")
        return None
    val_str = stat_el.get("value", "0")
    try:
        val = float(val_str)
    except ValueError:
        _logger.warning("stat %r: non-numeric value %r, skipping", name, val_str)
        return None
    if not math.isfinite(val):
        _logger.warning("stat %r: non-finite value %r, skipping", name, val_str)
        return None
    return StatEntry(stat=name, value=val)


def _parse_tree_section(root: Element, build: BuildDocument) -> None:
    """Parse the <Tree> section with specs."""
    tree_el = root.find("Tree")
    if tree_el is None:
        return

    raw_active = _safe_int(tree_el.get("activeSpec", "1"), 1)
    build.active_spec = _clamp_int(raw_active, lo=1, hi=None, field="activeSpec", context="tree")

    for spec_el in tree_el.findall("Spec"):
        spec = TreeSpec()
        spec.title = spec_el.get("title", "")
        spec.tree_version = spec_el.get("treeVersion", "")
        raw_class = _safe_int(spec_el.get("classId", "0"), 0)
        spec.class_id = _clamp_int(
            raw_class, lo=0, hi=None, field="classId", context=f"spec {spec.title!r}"
        )
        raw_ascend = _safe_int(spec_el.get("ascendClassId", "0"), 0)
        spec.ascend_class_id = _clamp_int(
            raw_ascend, lo=0, hi=None, field="ascendClassId", context=f"spec {spec.title!r}"
        )
        spec.secondary_ascend_class_id = _safe_int(spec_el.get("secondaryAscendClassId", "0"))

        nodes_str = spec_el.get("nodes", "")
        if nodes_str:
            raw_nodes = [_safe_int(n, 0) for n in nodes_str.split(",") if n.strip()]
            seen: set[int] = set()
            deduped: list[int] = []
            for n in raw_nodes:
                if n in seen:
                    _logger.warning(
                        "spec %r: duplicate node id %d, dropping duplicate",
                        spec.title,
                        n,
                    )
                    continue
                seen.add(n)
                deduped.append(n)
            spec.nodes = deduped

        # Parse mastery effects: "{nodeId,effectId},{nodeId,effectId}"
        mastery_str = spec_el.get("masteryEffects", "")
        if mastery_str:
            spec.mastery_effects = _parse_mastery_effects(mastery_str)

        url_el = spec_el.find("URL")
        if url_el is not None and url_el.text:
            spec.url = url_el.text.strip()

        sockets_el = spec_el.find("Sockets")
        if sockets_el is not None:
            for sock_el in sockets_el.findall("Socket"):
                spec.sockets.append(
                    TreeSocket(
                        node_id=int(sock_el.get("nodeId", "0")),
                        item_id=int(sock_el.get("itemId", "0")),
                    )
                )

        overrides_el = spec_el.find("Overrides")
        if overrides_el is not None:
            for ov_el in overrides_el.findall("Override"):
                spec.overrides.append(
                    TreeOverride(
                        node_id=int(ov_el.get("nodeId", "0")),
                        name=ov_el.get("dn", ""),
                        icon=ov_el.get("icon", ""),
                        text=" / ".join(
                            part.strip() for part in (ov_el.text or "").split("\t") if part.strip()
                        ),
                        effect_image=ov_el.get("activeEffectImage", ""),
                    )
                )

        build.specs.append(spec)


def _parse_mastery_effects(raw: str) -> list[MasteryMapping]:
    """Parse mastery effects string like '{53188,64875},{53738,29161}'."""
    effects = []
    raw = raw.strip()
    if not raw:
        return effects
    normalized = raw.replace(" ", "").replace("},{", "}|{")
    parts = normalized.split("|")
    for part in parts:
        cleaned = part.strip().strip("{}")
        if "," in cleaned:
            pieces = cleaned.split(",", 1)
            try:
                effects.append(
                    MasteryMapping(node_id=int(pieces[0].strip()), effect_id=int(pieces[1].strip()))
                )
            except ValueError:
                continue
    return effects


def _parse_skills_section(
    root: Element,
    build: BuildDocument,
    skill_set_id: int | None = None,
) -> None:
    """Parse the <Skills> section.

    If skill_set_id is given, parse that specific set. Otherwise parse the active set.
    """
    skills_el = root.find("Skills")
    if skills_el is None:
        return

    build.active_skill_set = _safe_int(skills_el.get("activeSkillSet", "1"), 1)
    build.default_gem_level = _safe_int(skills_el.get("defaultGemLevel", "0"))
    build.default_gem_quality = _safe_int(skills_el.get("defaultGemQuality", "0"))
    build.sort_gems_by_dps = skills_el.get("sortGemsByDPS", "false").casefold() == "true"
    build.sort_gems_by_dps_field = skills_el.get("sortGemsByDPSField", "")
    build.show_alt_quality_gems = skills_el.get("showAltQualityGems", "false").casefold() == "true"
    build.show_support_gem_types = skills_el.get("showSupportGemTypes", "")
    build.show_legacy_gems = skills_el.get("showLegacyGems", "false").casefold() == "true"

    skill_sets = skills_el.findall("SkillSet")
    build.skill_set_ids = [_safe_int(ss.get("id", "0"), 0) for ss in skill_sets]

    for ss in skill_sets:
        sid = _safe_int(ss.get("id", "0"), 0)
        title = ss.get("title", "")
        if title:
            build.skill_set_titles[sid] = title
        build.skill_sets[sid] = _parse_skill_elements(ss)

    target_id = skill_set_id if skill_set_id is not None else build.active_skill_set
    # NOTE: skill_groups is intentionally an alias (reference) to the list
    # in skill_sets[target_id]. This means mutations to skill_groups are
    # reflected in skill_sets and vice versa. Do not reassign skill_groups
    # to a new list — only mutate in place or the alias breaks.
    if target_id in build.skill_sets:
        build.skill_groups = build.skill_sets[target_id]
    elif build.skill_sets:
        first_id = next(iter(build.skill_sets))
        build.skill_groups = build.skill_sets[first_id]
    elif not skill_sets:
        # No SkillSet wrapper — skills are direct children
        build.skill_groups = _parse_skill_elements(skills_el)
    else:
        build.skill_groups = []


def _parse_skill_elements(parent) -> list[GemGroup]:
    """Parse <Skill> elements from a parent element."""
    groups = []
    for skill_el in parent.findall("Skill"):
        raw_main = _safe_int(skill_el.get("mainActiveSkill", "1"), 1)
        main_active_skill = _clamp_int(
            raw_main, lo=1, hi=None, field="main_active_skill", context="skill group"
        )
        group = GemGroup(
            slot=skill_el.get("slot", ""),
            label=skill_el.get("label", ""),
            enabled=skill_el.get("enabled", "true").casefold() == "true",
            include_in_full_dps=skill_el.get("includeInFullDPS", "false").casefold() == "true",
            main_active_skill=main_active_skill,
            main_active_skill_calcs=_safe_int(skill_el.get("mainActiveSkillCalcs", "0")),
            group_count=_safe_int(skill_el.get("groupCount", "0")),
            source=skill_el.get("source", ""),
        )

        for gem_el in skill_el.findall("Gem"):
            gem = _parse_gem_element(gem_el)
            if gem is not None:
                group.gems.append(gem)

        groups.append(group)
    return groups


_GEM_STR_ATTRS = (
    ("skillId", "skill_id"),
    ("gemId", "gem_id"),
    ("variantId", "variant_id"),
    ("qualityId", "quality_id"),
    ("skillPart", "skill_part"),
    ("skillPartCalcs", "skill_part_calcs"),
    ("skillMinion", "skill_minion"),
    ("skillMinionSkill", "skill_minion_skill"),
    ("skillMinionSkillCalcs", "skill_minion_skill_calcs"),
    ("skillMinionItemSet", "skill_minion_item_set"),
    ("skillMinionItemSetCalcs", "skill_minion_item_set_calcs"),
    ("skillStageCount", "skill_stage_count"),
    ("skillStageCountCalcs", "skill_stage_count_calcs"),
    ("skillMineCount", "skill_mine_count"),
    ("skillMineCountCalcs", "skill_mine_count_calcs"),
)


def _parse_gem_element(gem_el: Element) -> Gem | None:
    """Parse a single <Gem>. Returns None and warns if nameSpec is empty."""
    name_spec = gem_el.get("nameSpec", "Unknown")
    if not name_spec:
        _logger.warning("gem element has empty nameSpec, skipping")
        return None

    str_fields = {}
    for xml_attr, field in _GEM_STR_ATTRS:
        val = gem_el.get(xml_attr, "")
        if val:
            str_fields[field] = val

    raw_level = _safe_int(gem_el.get("level", "20"), 20)
    level = _clamp_int(raw_level, lo=1, hi=40, field="gem level", context=f"gem {name_spec!r}")
    raw_quality = _safe_int(gem_el.get("quality", "0"), 0)
    quality = _clamp_int(
        raw_quality, lo=0, hi=30, field="gem quality", context=f"gem {name_spec!r}"
    )
    raw_count = _safe_int(gem_el.get("count", "1"), 1)
    count = _clamp_int(raw_count, lo=1, hi=None, field="gem count", context=f"gem {name_spec!r}")

    return Gem(
        name_spec=name_spec,
        level=level,
        quality=quality,
        enabled=gem_el.get("enabled", "true").casefold() == "true",
        enable_global1=gem_el.get("enableGlobal1", "true").casefold() != "false",
        enable_global2=gem_el.get("enableGlobal2", "true").casefold() != "false",
        count=count,
        **str_fields,
    )


def _parse_items_section(root: Element, build: BuildDocument) -> None:
    """Parse the <Items> section."""
    items_el = root.find("Items")
    if items_el is None:
        return

    build.active_item_set = items_el.get("activeItemSet", "1")
    build.items_use_second_weapon_set = (
        items_el.get("useSecondWeaponSet", "false").casefold() == "true"
    )
    build.items_show_stat_differences = (
        items_el.get("showStatDifferences", "false").casefold() == "true"
    )

    for item_el in items_el.findall("Item"):
        item = _parse_item_element(item_el)
        if item is not None:
            build.items.append(item)

    for set_el in items_el.findall("ItemSet"):
        raw_id = set_el.get("id", "1")
        if not raw_id:
            _logger.warning("item set missing 'id' attribute, defaulting to '1'")
            raw_id = "1"
        item_set = ItemSet(
            id=raw_id,
            title=set_el.get("title", ""),
            use_second_weapon_set=set_el.get("useSecondWeaponSet", "false").casefold() == "true",
        )

        for slot_el in set_el.findall("Slot"):
            item_id = _safe_int(slot_el.get("itemId", "0"), 0)
            slot_name = slot_el.get("name", "")
            if item_id <= 0:
                continue
            if not slot_name:
                _logger.warning(
                    "slot with item_id=%d has empty name, skipping",
                    item_id,
                )
                continue
            item_set.slots.append(
                ItemSlot(
                    name=slot_name,
                    item_id=item_id,
                    active=slot_el.get("active", "true").casefold() != "false",
                    item_pb_url=slot_el.get("itemPbURL", ""),
                )
            )

        for sock_el in set_el.findall("SocketIdURL"):
            item_set.socket_id_urls.append(
                TreeSocket(
                    node_id=int(sock_el.get("nodeId", "0")),
                    item_id=int(sock_el.get("itemId", "0") if sock_el.get("itemId") else "0"),
                )
            )

        build.item_sets.append(item_set)


_VARIANT_ALT_ATTRS = ("variantAlt", "variantAlt2", "variantAlt3", "variantAlt4", "variantAlt5")
_VARIANT_ALT_FIELDS = (
    "variant_alt",
    "variant_alt2",
    "variant_alt3",
    "variant_alt4",
    "variant_alt5",
)


def _parse_item_element(item_el: Element) -> Item | None:
    """Parse one <Item>. Returns None + warns when 'id' is missing or non-positive."""
    item_id = _safe_int(item_el.get("id", "0"), 0)
    if item_id <= 0:
        _logger.warning("item element has missing or non-positive id=%d, skipping", item_id)
        return None
    text = (item_el.text or "").strip()
    variant = item_el.get("variant", "")

    variant_alts = {}
    for attr, field in zip(_VARIANT_ALT_ATTRS, _VARIANT_ALT_FIELDS, strict=True):
        val = item_el.get(attr, "")
        if val:
            variant_alts[field] = val

    mod_ranges: dict[str, float] = {}
    for mr_el in item_el.findall("ModRange"):
        mr_id = mr_el.get("id", "")
        mr_range = mr_el.get("range", "")
        if mr_id and mr_range:
            with contextlib.suppress(ValueError):
                mod_ranges[mr_id] = float(mr_range)

    item = Item(id=item_id, text=text, variant=variant, mod_ranges=mod_ranges, **variant_alts)
    _parse_item_text(item)
    return item


def _parse_affix_slot(line: str, pattern: re.Pattern[str]) -> str | None | object:
    """Parse a Prefix:/Suffix: line. Returns AFFIX_NO_MATCH if not a match, None for empty slot."""
    match = pattern.match(line)
    if not match:
        return AFFIX_NO_MATCH
    slot_val = match.group(1).strip()
    if slot_val == "None":
        return None
    slot_mod = SLOT_MOD_RE.match(slot_val)
    return slot_mod.group(2) if slot_mod else slot_val


def _parse_metadata_line(item: Item, line: str) -> bool:
    """Parse a single metadata line (defenses, quality, sockets, etc.). Returns True if handled."""
    int_fields = {
        "Armour: ": "armour",
        "Evasion: ": "evasion",
        "Energy Shield: ": "energy_shield",
        "Ward: ": "ward",
        "Quality: ": "quality",
        "LevelReq: ": "level_req",
        "Item Level: ": "item_level",
        "CatalystQuality: ": "catalyst_quality",
        "Talisman Tier: ": "talisman_tier",
        "Cluster Jewel Node Count: ": "cluster_jewel_node_count",
        "Limited to: ": "limited_to",
    }
    for prefix, field in int_fields.items():
        if line.startswith(prefix):
            raw = _safe_int(line.split(prefix, 1)[1])
            bounds = ITEM_INT_FIELD_BOUNDS.get(field)
            if bounds is not None:
                lo, hi = bounds
                raw = _clamp_int(raw, lo=lo, hi=hi, field=field, context=f"item id={item.id}")
            setattr(item, field, raw)
            return True

    str_fields = {
        "Sockets: ": "sockets",
        "Catalyst: ": "catalyst_type",
        "Unique ID: ": "unique_id",
        "Cluster Jewel Skill: ": "cluster_jewel_skill",
        "Radius: ": "jewel_radius",
        "Item Class: ": "item_class",
    }
    for prefix, field in str_fields.items():
        if line.startswith(prefix):
            setattr(item, field, line.split(prefix, 1)[1].strip())
            return True

    if line.startswith("Selected Variant: "):
        item.selected_variant = _safe_int(line.split("Selected Variant: ", 1)[1])
        return True
    if line.startswith("Foil Unique"):
        item.foil_type = line.strip()
        return True
    return (
        line.startswith(
            (
                "Variant: ",
                "League: ",
                "Has Variant: ",
                "Has Alt Variant",
                "Selected Alt Variant",
                "AltVariant: ",
                "Source: ",
            )
        )
        or "BasePercentile:" in line
    )


def _is_content_line(line: str) -> bool:
    """Check if a line is item content (not metadata/influence/markers)."""
    return not any(line.startswith(p) for p in METADATA_PREFIXES) and line not in INFLUENCE_LINES


def _strip_magic_affixes(name: str) -> str:
    """Strip prefix and 'of ...' suffix from a magic flask name to get the base type."""
    match = FLASK_BASE_RE.search(name)
    if match:
        return match.group(1)
    return MAGIC_SUFFIX_RE.sub("", name)


def _parse_header_line(item: Item, line: str, lines: list[str], index: int) -> bool:
    """Parse rarity, influence, synthesised, and crafted lines. Returns True if handled."""
    if line.startswith("Rarity: "):
        item.rarity = line.split("Rarity: ", 1)[1].strip()
        if index + 1 < len(lines) and _is_content_line(lines[index + 1]):
            item.name = lines[index + 1]
        if index + 2 < len(lines) and _is_content_line(lines[index + 2]):
            item.base_type = lines[index + 2]
        elif item.rarity == "MAGIC" and item.name:
            if "Flask" in item.name:
                item.base_type = _strip_magic_affixes(item.name)
            else:
                item.base_type = MAGIC_SUFFIX_RE.sub("", item.name)
        elif item.rarity == "NORMAL" and item.name:
            item.base_type = item.name
        return True
    if line in INFLUENCE_LINES:
        item.influences.append(INFLUENCE_LINES[line])
        return True
    state_lines = {
        "Synthesised Item": "is_synthesised",
        "Fractured Item": "is_fractured",
        "Crafted: true": "is_crafted",
        "Corrupted": "is_corrupted",
        "Mirrored": "is_mirrored",
        "Split": "is_split",
        "Has Veiled Prefix": "has_veiled_prefix",
        "Has Veiled Suffix": "has_veiled_suffix",
    }
    if line in state_lines:
        setattr(item, state_lines[line], True)
        return True
    return False


def _parse_item_text(item: Item) -> None:
    """Extract structured data from PoB item text."""
    lines = [line.strip() for line in item.text.split("\n") if line.strip()]
    implicit_count = 0
    in_implicits = False
    implicits_seen = 0

    for i, line in enumerate(lines):
        if _parse_header_line(item, line, lines, i):
            continue

        prefix_slot = _parse_affix_slot(line, PREFIX_RE)
        if prefix_slot is not AFFIX_NO_MATCH:
            item.prefix_slots.append(prefix_slot)
            continue
        suffix_slot = _parse_affix_slot(line, SUFFIX_RE)
        if suffix_slot is not AFFIX_NO_MATCH:
            item.suffix_slots.append(suffix_slot)
            continue

        if _parse_metadata_line(item, line):
            continue
        if line.startswith("Implicits: "):
            implicit_count = _safe_int(line.split("Implicits: ", 1)[1])
            in_implicits = True
            implicits_seen = 0
            continue
        if line in (item.name, item.base_type):
            continue

        mod = _parse_mod_line(line)
        if mod is None:
            continue

        if mod.variant and mod.text in (item.name, item.base_type):
            continue

        if in_implicits and implicits_seen < implicit_count:
            mod.is_implicit = True
            item.implicits.append(mod)
            implicits_seen += 1
            if implicits_seen >= implicit_count:
                in_implicits = False
        else:
            item.explicits.append(mod)

    if item.name == "New Item" and item.base_type:
        item.name = item.base_type

    _assign_affix_metadata(item)


@functools.cache
def _get_mod_keywords() -> dict[str, list[str]]:
    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "repoe"
    mods_path = data_dir / "mods.json"
    trans_path = data_dir / "stat_translations.json"
    if not mods_path.exists():
        return {}

    mods = json.loads(mods_path.read_text(encoding="utf-8"))
    translations: dict[str, str] = {}
    if trans_path.exists():
        translations = json.loads(trans_path.read_text(encoding="utf-8"))

    cache: dict[str, list[str]] = {}
    for mod_id, entry in mods.items():
        keywords: list[str] = []
        for stat in entry.get("stats", []):
            stat_id = stat.get("id", "")
            template = translations.get(stat_id, "")
            if template:
                words = re.findall(r"[a-zA-Z]{3,}", template.lower())
                keywords.extend(words)
            else:
                parts = stat_id.replace("+", "").replace("%", "").split("_")
                keywords.extend(
                    p.lower()
                    for p in parts
                    if len(p) >= MIN_KEYWORD_LENGTH and p.lower() not in MOD_KEYWORD_NOISE
                )
        cache[mod_id] = keywords
    return cache


def _score_mod_match(mod_text: str, keywords: list[str]) -> int:
    text_lower = mod_text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


def _assign_affix_metadata(item: Item) -> None:
    """Tag explicits as prefix/suffix and assign mod_ids from slot data.

    Uses keyword matching from stat translations to correctly pair
    slot mod_ids with their corresponding explicit text lines.
    """
    filled_prefixes = [s for s in item.prefix_slots if s is not None]
    filled_suffixes = [s for s in item.suffix_slots if s is not None]
    if not filled_prefixes and not filled_suffixes:
        return

    regular = [
        m for m in item.explicits if not m.is_crafted and not m.is_fractured and not m.is_custom
    ]
    if not regular:
        return

    kw_cache = _get_mod_keywords()
    slots: list[tuple[str, bool]] = [(s, True) for s in filled_prefixes] + [
        (s, False) for s in filled_suffixes
    ]

    has_keywords = any(kw_cache.get(mod_id) for mod_id, _ in slots)
    if not has_keywords:
        prefix_count = len(filled_prefixes)
        for i, mod in enumerate(regular):
            if i < prefix_count:
                _set_affix(mod, is_prefix=True)
                mod.mod_id = filled_prefixes[i]
            elif i - prefix_count < len(filled_suffixes):
                _set_affix(mod, is_prefix=False)
                mod.mod_id = filled_suffixes[i - prefix_count]
        return

    claimed_mods: set[int] = set()
    for mod_id, is_prefix in slots:
        keywords = kw_cache.get(mod_id, [])
        if not keywords:
            continue
        best_score = 0
        best_idx = -1
        for i, mod in enumerate(regular):
            if i in claimed_mods:
                continue
            score = _score_mod_match(mod.text, keywords)
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx >= 0:
            claimed_mods.add(best_idx)
            regular[best_idx].mod_id = mod_id
            _set_affix(regular[best_idx], is_prefix=is_prefix)


def _set_affix(mod: ItemMod, *, is_prefix: bool) -> None:
    """Atomically assign prefix/suffix flag.

    Clears both first to avoid the transient (True, True) state that
    `_check_affix_exclusive` would reject if a mod is being reassigned
    from suffix to prefix or vice versa. Today no caller does that, but
    setattr ordering is one logic edit away from triggering the validator.
    """
    mod.is_suffix = False
    mod.is_prefix = is_prefix
    mod.is_suffix = not is_prefix


_BOOL_MARKERS = frozenset(
    {
        "crafted",
        "custom",
        "fractured",
        "exarch",
        "eater",
        "enchant",
        "scourge",
        "crucible",
        "synthesis",
        "mutated",
    }
)


def _parse_mod_line(line: str) -> ItemMod | None:
    """Parse a mod line with its markers."""
    flags: dict[str, bool] = {}
    tags: list[str] = []
    range_value: float | None = None
    variant = ""

    while line.startswith("{"):
        marker_end = line.find("}")
        if marker_end == -1:
            break
        marker_end += 1
        marker_content = line[1 : marker_end - 1]

        if marker_content in _BOOL_MARKERS:
            flags[f"is_{marker_content}"] = True
        elif marker_content.startswith("tags:"):
            tags = [t.strip() for t in marker_content[5:].split(",") if t.strip()]
        elif marker_content.startswith("range:"):
            try:
                raw_range = float(marker_content[6:])
            except ValueError:
                pass
            else:
                if raw_range < 0.0:
                    _logger.warning("mod range %r below 0.0, clamping", raw_range)
                    range_value = 0.0
                elif raw_range > 1.0:
                    _logger.warning("mod range %r above 1.0, clamping", raw_range)
                    range_value = 1.0
                else:
                    range_value = raw_range
        elif marker_content.startswith("variant:"):
            variant = marker_content[8:]
        line = line[marker_end:]

    text = line.strip()
    if not text:
        return None

    return ItemMod(
        text=text,
        tags=tags,
        range_value=range_value,
        variant=variant,
        **flags,
    )


def _parse_config_section(root: Element, build: BuildDocument) -> None:
    """Parse the <Config> section."""
    config_el = root.find("Config")
    if config_el is None:
        return

    build.active_config_set = config_el.get("activeConfigSet", "1")

    config_set_elements = config_el.findall("ConfigSet")
    if config_set_elements:
        for set_el in config_set_elements:
            raw_id = set_el.get("id", "1")
            if not raw_id:
                _logger.warning("config set missing 'id' attribute, defaulting to '1'")
                raw_id = "1"
            config_set = BuildConfig(
                id=raw_id,
                title=set_el.get("title", "Default"),
            )
            for input_el in set_el.findall("Input"):
                entry = _parse_config_input(input_el)
                if entry is not None:
                    config_set.inputs.append(entry)
            for ph_el in set_el.findall("Placeholder"):
                entry = _parse_config_input(ph_el)
                if entry is not None:
                    config_set.placeholders.append(entry)
            build.config_sets.append(config_set)
    else:
        legacy = BuildConfig(id="1", title="Default")
        for input_el in config_el.findall("Input"):
            entry = _parse_config_input(input_el)
            if entry is not None:
                legacy.inputs.append(entry)
        for ph_el in config_el.findall("Placeholder"):
            entry = _parse_config_input(ph_el)
            if entry is not None:
                legacy.placeholders.append(entry)
        if legacy.inputs or legacy.placeholders:
            build.config_sets.append(legacy)


def _parse_config_input(el) -> ConfigEntry | None:
    """Parse an <Input> or <Placeholder>. Returns None and warns on empty name."""
    name = el.get("name", "")
    if not name:
        _logger.warning("config input missing 'name' attribute, skipping")
        return None
    if el.get("boolean") is not None:
        return ConfigEntry(name=name, value=el.get("boolean") == "true", input_type="boolean")
    if el.get("number") is not None:
        try:
            val = float(el.get("number", "0"))
        except ValueError:
            val = 0.0
        return ConfigEntry(name=name, value=val, input_type="number")
    if el.get("string") is not None:
        return ConfigEntry(name=name, value=el.get("string", ""), input_type="string")
    return ConfigEntry(name=name, value="", input_type="string")


def _parse_notes(root: Element, build: BuildDocument) -> None:
    """Parse the <Notes> section, preserving PoB color codes and whitespace.

    Both stripping color codes and stripping whitespace at parse time were
    silent data loss on round-trip (parse → write → parse). PoB writes notes
    wrapped in newline/tab framing; trimming destroys that. notes_get() is
    the consumer that strips for display; the writer round-trips raw bytes.
    """
    notes_el = root.find("Notes")
    if notes_el is not None:
        build.notes = notes_el.text or ""


def _parse_import(root: Element, build: BuildDocument) -> None:
    """Parse the <Import> section."""
    import_el = root.find("Import")
    if import_el is not None:
        build.import_link = import_el.get("importLink", "")
        build.import_last_realm = import_el.get("lastRealm", "")
        build.import_last_character_hash = import_el.get("lastCharacterHash", "")
        build.import_last_account_hash = import_el.get("lastAccountHash", "")
        build.import_export_party = import_el.get("exportParty", "")


_PASSTHROUGH_TAGS = frozenset({"Party", "Calcs", "TreeView", "TradeSearchWeights"})


def _parse_passthrough_sections(root: Element, build: BuildDocument) -> None:
    """Preserve unparsed XML sections verbatim for roundtrip fidelity."""
    for tag in _PASSTHROUGH_TAGS:
        el = root.find(tag)
        if el is not None:
            build.passthrough_sections[tag] = ET.tostring(el, encoding="unicode")

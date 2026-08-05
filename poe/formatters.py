from __future__ import annotations

from poe.models.build.build import (
    BuildComparison,
    BuildMetadata,
    MutationResult,
    ValidationResult,
)
from poe.models.build.config import BuildConfig
from poe.models.build.gems import GemGroup
from poe.models.build.items import EquippedItem
from poe.models.build.jewels import JewelListResult
from poe.models.build.stats import StatBlock
from poe.models.build.tree import TreeSpecList
from poe.models.ninja.economy import PriceResult
from poe.output import human_formatter


def register_formatters() -> None:
    pass


@human_formatter(BuildMetadata)
def _fmt_build_metadata(m: BuildMetadata) -> str:
    parts = [m.name]
    if m.class_name:
        cls = f"{m.ascendancy} ({m.class_name})" if m.ascendancy else m.class_name
        parts.append(cls)
    if m.level > 1:
        parts.append(f"Lv{m.level}")
    if m.version:
        parts.append(f"v{m.version}")
    if m.file_path:
        parts.append(m.file_path)
    return " | ".join(parts)


@human_formatter(StatBlock)
def _fmt_stat_block(s: StatBlock) -> str:
    lines = [f"Stats ({s.category}):"]
    for k, v in s.stats.items():
        if isinstance(v, float):
            lines.append(f"  {k}: {v:,.1f}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


@human_formatter(MutationResult)
def _fmt_mutation(m: MutationResult) -> str:
    parts = []
    for field, value in m.model_dump(exclude_none=True).items():
        if field == "warning":
            continue
        parts.append(f"{field}: {value}")
    if m.warning:
        parts.append(f"[{m.warning}]")
    return "\n".join(parts)


@human_formatter(EquippedItem)
def _fmt_equipped_item(item: EquippedItem) -> str:
    header = f"[{item.slot}] {item.name}"
    if item.base_type and item.base_type != item.name:
        header += f" ({item.base_type})"
    lines = [header]
    if item.rarity:
        lines.append(f"  rarity: {item.rarity}")
    if item.influences:
        lines.append(f"  influences: {', '.join(item.influences)}")
    if item.sockets:
        lines.append(f"  sockets: {item.sockets}")
    if item.quality:
        lines.append(f"  quality: {item.quality}")
    if item.item_level:
        lines.append(f"  item_level: {item.item_level}")
    if item.armour or item.evasion or item.energy_shield or item.ward:
        defenses = []
        if item.armour:
            defenses.append(f"armour={item.armour}")
        if item.evasion:
            defenses.append(f"evasion={item.evasion}")
        if item.energy_shield:
            defenses.append(f"es={item.energy_shield}")
        if item.ward:
            defenses.append(f"ward={item.ward}")
        lines.append(f"  defenses: {', '.join(defenses)}")
    if item.implicits:
        lines.append("  implicits:")
        lines.extend(f"    {m.text}" for m in item.implicits)
    if item.explicits:
        lines.append("  explicits:")
        for m in item.explicits:
            prefix = "(crafted) " if m.is_crafted else "(fractured) " if m.is_fractured else ""
            lines.append(f"    {prefix}{m.text}")
    if item.open_prefixes or item.open_suffixes:
        lines.append(f"  open: {item.open_prefixes}P / {item.open_suffixes}S")
    return "\n".join(lines)


@human_formatter(PriceResult)
def _fmt_price(p: PriceResult) -> str:
    header = p.name
    qualifiers = []
    if p.variant:
        qualifiers.append(p.variant)
    if p.gem_level:
        qualifiers.append(f"Lv{p.gem_level}")
    if p.gem_quality:
        qualifiers.append(f"Q{p.gem_quality}")
    if p.links:
        qualifiers.append(f"{p.links}L")
    if p.corrupted:
        qualifiers.append("corrupted")
    if qualifiers:
        header += f" ({', '.join(qualifiers)})"
    lines = [header]
    if p.chaos_value >= 1:
        lines.append(f"  Chaos: {p.chaos_value:,.1f}")
    else:
        lines.append(f"  Chaos: {p.chaos_value:,.4f}")
    if p.divine_value:
        lines.append(f"  Divine: {p.divine_value:,.2f}")
    if p.listing_count is not None:
        lines.append(f"  Listings: {p.listing_count}")
    if p.low_confidence:
        lines.append("  [low confidence]")
    return "\n".join(lines)


@human_formatter(GemGroup)
def _fmt_gem_group(g: GemGroup) -> str:
    header_parts = []
    if g.slot:
        header_parts.append(g.slot)
    if g.label:
        header_parts.append(g.label)
    if not g.enabled:
        header_parts.append("(disabled)")
    header = " | ".join(header_parts) if header_parts else "Unlinked"
    lines = [f"[{header}]"]
    for gem in g.gems:
        parts = [f"  {gem.name_spec} Lv{gem.level}"]
        if gem.quality:
            parts.append(f"Q{gem.quality}")
        if not gem.enabled:
            parts.append("(disabled)")
        lines.append(" ".join(parts))
    return "\n".join(lines)


@human_formatter(ValidationResult)
def _fmt_validation(v: ValidationResult) -> str:
    lines = [f"Build: {v.build}"]
    if not v.issues:
        lines.append("No issues found.")
        return "\n".join(lines)
    lines.append(f"{v.issue_count} issue(s):")
    lines.extend(f"  [{issue.severity}] {issue.category}: {issue.message}" for issue in v.issues)
    return "\n".join(lines)


@human_formatter(BuildComparison)
def _fmt_comparison(c: BuildComparison) -> str:
    lines = [f"{c.build1.name} vs {c.build2.name}", ""]
    significant = {k: v for k, v in c.stat_comparison.items() if v.get("diff", 0) != 0}
    if significant:
        lines.append("Stat differences:")
        for k, v in significant.items():
            diff = v["diff"]
            pct = v.get("pct")
            sign = "+" if diff > 0 else ""
            pct_str = f" ({sign}{pct:.1f}%)" if pct is not None else ""
            lines.append(
                f"  {k}: {v[c.build1.name]:,.1f} -> {v[c.build2.name]:,.1f}"
                f" ({sign}{diff:,.1f}{pct_str})"
            )
    if c.config_diff:
        lines.append("")
        lines.append("Config differences:")
        for k, v in c.config_diff.items():
            lines.append(f"  {k}: {v.get(c.build1.name, '?')} -> {v.get(c.build2.name, '?')}")
    return "\n".join(lines)


@human_formatter(JewelListResult)
def _fmt_jewels(j: JewelListResult) -> str:
    if not j.jewels and not j.cluster_jewels:
        return "No jewels equipped."
    lines = []
    if j.jewels:
        lines.append(f"Jewels ({len(j.jewels)}):")
        for jewel in j.jewels:
            node = f" (node {jewel.tree_node})" if jewel.tree_node else ""
            lines.append(f"  [{jewel.slot}] {jewel.name}{node}")
    if j.cluster_jewels:
        lines.append(f"Cluster Jewels ({len(j.cluster_jewels)}):")
        for jewel in j.cluster_jewels:
            node = f" (node {jewel.tree_node})" if jewel.tree_node else ""
            lines.append(f"  [{jewel.slot}] {jewel.name}{node}")
    return "\n".join(lines)


@human_formatter(TreeSpecList)
def _fmt_tree_specs(t: TreeSpecList) -> str:
    lines = [f"Specs ({len(t.specs)}, active: #{t.active_spec}):"]
    for spec in t.specs:
        active = " *" if spec.active else ""
        lines.append(
            f"  #{spec.index}: {spec.title or '(untitled)'}"
            f" | {spec.node_count} nodes | {spec.tree_version}{active}"
        )
    return "\n".join(lines)


@human_formatter(BuildConfig)
def _fmt_config(c: BuildConfig) -> str:
    lines = [f"Config: {c.title} (id={c.id})"]
    if not c.inputs:
        lines.append("  (no inputs)")
        return "\n".join(lines)
    for entry in c.inputs:
        val = entry.value
        if isinstance(val, bool):
            val = "true" if val else "false"
        lines.append(f"  {entry.name}: {val}")
    return "\n".join(lines)

# poe.ninja Integration

The `poe ninja` CLI provides live economy data, build exploration, and meta analysis from poe.ninja. All commands output human-readable text by default. Add `--json` for machine-readable JSON. Use Bash to run commands.

## Quick Start

| User wants... | Command |
|---|---|
| Price of an item | `poe ninja price check "<item>" <type>` |
| Current meta | `poe ninja meta summary` |
| Available leagues | `poe ninja league-info` |

## Tier 1 — Start Here

Basic price lookups and meta overview. No build context needed.

| Command | Purpose |
|---------|---------|
| `poe ninja price check "<item>" <type>` | Price a single item (e.g. `"Exalted Orb" Currency`) |
| `poe ninja price list <type>` | All items in category sorted by value |
| `poe ninja price convert <amt> "<from>" "<to>"` | Currency conversion |
| `poe ninja meta summary` | Top class/skill combos with trends |
| `poe ninja league-info` | Available leagues and snapshots |
| `poe ninja cache-status` | Cache freshness report |
| `poe ninja cache-clear` | Clear all cached ninja responses |

## Tier 2 — Build Inspection

Character inspection and comparison. Requires account + character name.

| Command | Purpose |
|---------|---------|
| `poe ninja builds inspect <account> <char>` | Full character detail (gear, skills, passives) |
| `poe ninja builds import <account> <char>` | Import to local PoB builds |
| `poe ninja builds compare <account> <char>` | Gap analysis vs meta (missing keystones, percentiles) |
| `poe ninja builds suggest-upgrade <account> <char>` | Budget alternatives for expensive gear |
| `poe ninja price build <account> <char>` | Per-slot cost breakdown |
| `poe ninja tooltip "<name>"` | Fetch mod details for items/passives |

## Tier 3 — Search & Analysis

Advanced queries across the full build/economy dataset.

| Command | Purpose |
|---------|---------|
| `poe ninja builds search --class X --skill Y` | Filter builds by class, skill, item, keystone. Returns character listings with names, accounts, skills, keystones. Works with both PoE1 and PoE2 classes. |
| `poe ninja builds heatmap --class X` | Passive tree allocation frequency |
| `poe ninja price history "<item>" <type>` | 366-day trend with spike/crash detection |
| `poe ninja price craft` | All crafting material prices |
| `poe ninja price fossil-recommend <mod>` | Fossils matching a mod tag, sorted by cost |
| `poe ninja atlas search --mechanics X` | Atlas tree search (also: `--travel`, `--blockers`, `--scarab-specializations`, `--keystones`, `--beacons`) |
| `poe ninja atlas recommend --top-n 10` | Most popular atlas nodes (configurable count) |
| `poe ninja atlas profit` | Scarab spawn chance x price = expected value |
| `poe ninja meta trend` | Build evolution across leagues |

## Tier 4 — Compound Workflows

Multi-step agent workflows that combine services. Call from Python, not CLI.

| Workflow | Purpose |
|----------|---------|
| `fix_my_build(account, char, ...)` | Fetch character → compare to meta → price upgrades → prioritized plan |
| `what_to_farm(atlas, economy, league)` | Atlas strategies × scarab prices → most profitable config |
| `how_should_i_craft(economy, league)` | Crafting material prices sorted by cost |
| `what_build_to_play(builds, ...)` | Meta trends → top characters → gear costs |
| `budget_upgrade(account, char, ..., budget)` | Check each slot → find alternatives within budget |
| `what_changed(builds, ...)` | Diff time machine snapshots → identify meta shifts |

## Type Reference

**PoE1 Stash Currency**: `Currency`, `Fragment`
**PoE1 Stash Items**: `BaseType`, `Beast`, `BlightedMap`, `BlightRavagedMap`, `ClusterJewel`, `ForbiddenJewel`, `Incubator`, `IncursionTemple`, `Invitation`, `Map`, `Memory`, `ShrineBelt`, `SkillGem`, `UniqueAccessory`, `UniqueArmour`, `UniqueFlask`, `UniqueJewel`, `UniqueMap`, `UniqueRelic`, `UniqueTincture`, `UniqueWeapon`, `ValdoMap`, `Vial`, `Wombgift`
**PoE1 Exchange**: `AllflameEmber`, `Artifact`, `Astrolabe`, `Currency`, `DeliriumOrb`, `DivinationCard`, `DjinnCoin`, `Essence`, `Fossil`, `Fragment`, `Oil`, `Omen`, `Resonator`, `Runegraft`, `Scarab`, `Tattoo`
**PoE2 Exchange**: `Abyss`, `Breach`, `Currency`, `Delirium`, `Essences`, `Expedition`, `Fragments`, `Idols`, `LineageSupportGems`, `Ritual`, `Runes`, `SoulCores`, `UncutGems`

## Global Options

`--game poe1|poe2` (default poe1), `--league <name>` (default current), `--language <code>` (en/de/fr/es/pt/ru/ja/zh), `--json` (machine-readable JSON output), `--no-cache` (bypass cached responses and fetch fresh data)

## Search Filters (PoE1)

`--class`, `--skill`, `--item`, `--keystone`, `--mastery`, `--anointment`, `--weapon-mode`, `--bandit`, `--pantheon`, `--time-machine`. All support `!` negation.

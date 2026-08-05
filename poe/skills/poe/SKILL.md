---
name: poe
description: Use when the user asks about their Path of Exile build, Path of Building, build analysis, passive tree, items, gems, DPS, defenses, resistances, crafting advice, item upgrades, or anything related to PoE character optimization.
---

# Path of Exile CLI Toolkit

You have access to the `poe` CLI — a toolkit for PoE character optimization. All commands output human-readable text by default. Add `--json` for machine-readable JSON. Use Bash to run commands.

## Domains

| Domain | Commands | When to use |
|--------|----------|-------------|
| **Build** | `poe build ...` | Reading, analyzing, or modifying Path of Building XML files |
| **Sim** | `poe sim ...` | Querying mod pools, fossils, essences, bench crafts, simulating crafting costs |
| **Ninja** | `poe ninja ...` | Live economy prices, build search, meta analysis, atlas strategies from poe.ninja |

## Quick Start

| User wants... | Domain | Start with... |
|---|---|---|
| Build review / optimization | Build | `poe build analyze` → drill into weak areas |
| Crafting help for an item | Sim | `poe sim mods` / `poe sim analyze` |
| Live item prices / economy | Ninja | `poe ninja price check` / `poe ninja price list` |
| Meta overview / popular builds | Ninja | `poe ninja meta summary` |
| Compare build to meta | Ninja | `poe ninja builds compare` |
| Compare two local builds | Build | `poe build compare` |
| "What mods can roll on X?" | Sim | `poe sim mods "<base>"` |
| "Best way to craft X?" | Sim | `poe sim suggest` / `poe sim compare` |
| Quick build snapshot | Build | `poe build summary` (includes main skill name) |
| General PoE question | — | Your PoE knowledge — read `mechanics.md` for reference |

## Deep Dives

Read these files (in this skill's directory) for detailed command reference and guidance:

- **`build.md`** — All build commands, PoB structure, multi-spec/set handling, safety layer, write commands
- **`craft.md`** — Crafting commands, simulation, advice approach, data management, limitations
- **`ninja.md`** — Live economy, build search, meta analysis, atlas strategies, compound workflows
- **`mechanics.md`** — PoE damage, defenses, passive tree, gem links, stat interpretation

Read the relevant file based on what the user is asking about. Don't read all of them upfront.

# poe-cli

A command-line interface for Path of Exile theorycrafting. Reads your [Path of Building](https://github.com/PathOfBuildingCommunity/PathOfBuilding) builds, runs PoB's Lua calculation engine in-process via [lupa](https://github.com/scoder/lupa), simulates crafting outcomes, and pulls live economy data from [poe.ninja](https://poe.ninja).

## What it does

**Build analysis** — Read, compare, and modify PoB builds from the terminal. Inspect items, gems, tree, flasks, jewels, and config. Create new builds, import from codes/URLs, and share via [pobb.in](https://pobb.in). Write operations go to a sandboxed `Claude/` subfolder so your real builds are never touched.

**Live calculation engine** — Embeds PoB's actual Lua calc engine via LuaJIT. Load a build and query its computed stats (DPS, defenses, etc.) the same way Path of Building does internally — no scraping, no approximation.

**Crafting simulation** — Monte Carlo simulation of PoE crafting methods: fossils, essences, alterations, chaos spam, multi-step strategies. Query mod pools and weights for any base type, compare methods head-to-head, or analyze an equipped item to find upgrade paths.

**Economy data** — Price checks, currency conversion, and price history from poe.ninja. Search the meta: what builds are popular, what gear they use, and what atlas strategies people are running.

All output is human-readable by default. Add `--json` for machine-parseable JSON output. Ships with a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill so an AI agent can drive the whole thing programmatically.

## Install

Requires [uv](https://docs.astral.sh/uv/) and [Path of Building Community](https://github.com/PathOfBuildingCommunity/PathOfBuilding).

```bash
uv tool install poe-tools          # install
uv tool upgrade poe-tools          # upgrade
poe --help
```

### Claude Code skill (optional)

```bash
poe install-skill            # install skill files to ~/.claude/skills/poe/
poe install-skill --force    # reinstall after upgrading the CLI
poe install-skill --uninstall
```

## Command reference

### Builds

```bash
# Read and analyze
poe build list
poe build summary "My RF Jugg"
poe build analyze "My RF Jugg"
poe build stats "My RF Jugg" --category off
poe build validate "My RF Jugg"
poe build compare "My RF Jugg" "League Starter"

# Drill into loadouts
poe build tree get "My RF Jugg"
poe build items list "My RF Jugg"
poe build gems list "My RF Jugg"
poe build flasks list "My RF Jugg"
poe build jewels list "My RF Jugg"
poe build config get "My RF Jugg"

# Modify builds (writes go to Claude/ subfolder)
poe build create "New Build" --class Witch --ascendancy Necromancer --level 90
poe build duplicate "My RF Jugg" "RF Jugg Copy"
poe build rename "Old Name" "New Name"
poe build set-level "My RF Jugg" --level 95
poe build set-class "My RF Jugg" --class Witch --ascendancy Necromancer
poe build items add "My RF Jugg" --slot Helmet --base "Hubris Circlet" --rarity RARE
poe build items edit "My RF Jugg" --slot Helmet --add-explicit "+90 to maximum Life"
poe build gems add "My RF Jugg" --slot "Body Armour" --gem Fireball --gem "Spell Echo Support"
poe build tree set "My RF Jugg" --add-nodes 500,600
poe build flasks add "My RF Jugg" --base "Granite Flask" --slot "Flask 1"
poe build jewels add "My RF Jugg" --base "Cobalt Jewel" --slot "Jewel 1"
poe build config preset "My RF Jugg" --preset boss

# Import/export
poe build decode <build_code>
poe build encode "My RF Jugg"
poe build share "My RF Jugg"
poe build import <url_or_code> --name "Imported"
```

### Live engine

```bash
poe build engine load "My RF Jugg"
poe build engine stats
```

### Crafting simulation

```bash
poe sim search "Crown"
poe sim mods "Hubris Circlet" --ilvl 84
poe sim weights "Hubris Circlet" --ilvl 84
poe sim simulate "Vaal Regalia" --method fossil --target IncreasedLife --fossils "Pristine Fossil,Dense Fossil"
poe sim simulate-multistep "Vaal Regalia" --step alt --step regal --target IncreasedLife
poe sim compare "Vaal Regalia" --target IncreasedLife --fossils "Pristine Fossil"
poe sim suggest --mod "IncreasedLife"
poe sim analyze "My RF Jugg" --slot Helmet
poe sim prices
```

### Economy (poe.ninja)

```bash
poe ninja price check "Exalted Orb" Currency
poe ninja price list Currency
poe ninja price convert 10 "Exalted Orb" "Chaos Orb"
poe ninja price history "Exalted Orb" Currency
poe ninja meta summary
poe ninja builds search --class Necromancer --skill "Summon Raging Spirits"
poe ninja builds inspect <account> <character>
poe ninja atlas recommend
```

## Build safety

All write operations go to a `Claude/` subfolder inside the PoB builds directory. Your original builds are never modified. The `--file` flag bypasses this and writes directly to the specified path.

## Development

```bash
git clone https://github.com/srhinos/poe-cli.git
cd poe-cli
uv sync

uv run ruff check poe/ tests/                                # Lint
uv run ruff format --check poe/ tests/                       # Format check
uv run ty check poe/                                         # Type check
uv run pytest tests/ --ignore=tests/integration -v           # Unit tests
uv run pytest tests/ -v                                      # All tests (needs network + PoB)
```

## Acknowledgments

Inspired by [ianderse/pob-mcp](https://github.com/ianderse/pob-mcp) and [Craft of Exile](https://craftofexile.com/).

### Data & Tools

- [Path of Building Community](https://github.com/PathOfBuildingCommunity/PathOfBuilding) — build format and Lua calculation engine
- [RePoE](https://github.com/brather1ng/RePoE) — game data extraction (mods, base items, fossils, essences)
- [poe.ninja](https://poe.ninja) — economy data and build analytics
- [lupa](https://github.com/scoder/lupa) — Python-Lua bridge for embedding LuaJIT
- [pobb.in](https://pobb.in) — build code sharing

## AI disclosure

This project was built with some help from [Claude Code](https://docs.anthropic.com/en/docs/claude-code). I'm an experienced software engineer and have done my best to verify correctness along way, but AI-assisted code can have blind spots that manual review won't always catch. The test suite is extensive and I trust the core workflows — just know that edge cases may not have gotten the same scrutiny. If you seee some true slop that makes no sense, please open an issue and I'll fix it up <3

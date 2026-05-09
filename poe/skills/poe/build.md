# Build Tools

For working with Path of Building `.xml` build files. All commands output human-readable text by default. Add `--json` for machine-readable JSON output.

## Getting Oriented

PoB builds are complex — multiple tree specs, item sets, skill sets, disabled gems, build notes. **Always start with the overview.**

```bash
poe build list                          # What builds are available?
poe build analyze "<name>"              # Overview: specs, sets, stats, notes
poe build notes "<name>"                # Build notes (often contain guides, gearing plans)
```

The `analyze` output tells you how many tree specs, item sets, and skill sets exist — and which are active. This reveals whether it's a single build, a leveling guide, or a multi-phase plan.

**Ask the user which phase they care about.** A build with specs named "Leveling 1-7" is a leveling guide. An import might have snapshots at different levels.

## Drilling Into a Loadout

```bash
poe build tree specs "<name>"                  # All tree specs
poe build tree get "<name>" --spec 3           # Specific spec
poe build tree get "<name>"                    # Active spec (default)

poe build items sets "<name>"                  # All item sets
poe build items list "<name>" --item-set 3     # Specific item set
poe build items list "<name>"                  # Active set (default)

poe build gems sets "<name>"                   # All skill sets
poe build gems list "<name>" --skill-set 2     # Specific skill set
poe build gems list "<name>"                   # Active set (default)
```

## Stats, Comparison, Validation

```bash
poe build summary "<name>"                     # Quick dashboard (class/level/main skill/DPS/life/resists)
poe build stats "<name>" --category off        # Offensive stats
poe build stats "<name>" --category def        # Defensive stats
poe build compare "<build1>" "<build2>"        # Side-by-side stat diff
poe build tree compare "<build1>" "<build2>"   # Tree node diff
poe build validate "<name>"                    # Check for common issues
poe build config get "<name>"                  # Build config (charges, conditions, enemy)
```

## Creating and Modifying Builds

```bash
# Create / delete / clone / rename
poe build create "<name>" --class Witch --ascendancy Necromancer --level 90
poe build create "<name>" --file /path/to/output.xml
poe build delete "<name>" --confirm
poe build duplicate "<name>" "Clone Name"
poe build rename "<name>" "New Name"

# Character properties
poe build set-level "<name>" --level 95
poe build set-class "<name>" --class Witch --ascendancy Necromancer
poe build set-bandit "<name>" --bandit Alira
poe build set-pantheon "<name>" --major "Soul of the Brine King" --minor "Soul of Garukhan"
poe build batch-set-level --level 100 --build "Build 1" --build "Build 2"

# Items
poe build items add "<name>" --slot Helmet --rarity RARE --item-name "Doom Crown" \
    --base "Hubris Circlet" --energy-shield 200 --quality 20 --influence Shaper \
    --implicit "+(50-70) to maximum Life" --explicit "+90 to maximum Life" \
    --crafted-mod "+10% to all Elemental Resistances"
poe build items add "<name>" --slot "Body Armour" --base "Vaal Regalia" --armour 0 \
    --evasion 0 --sockets "BBBBBG" --level-req 68 --fractured-mod "+1 to Level of Socketed Gems" \
    --synthesised
poe build items remove "<name>" --slot Helmet
poe build items remove "<name>" --id 3
poe build items edit "<name>" --slot Helmet \
    --add-explicit "+40 to maximum Life" --remove-explicit 0 \
    --set-name "New Name" --set-rarity RARE --set-quality 20 \
    --set-sockets "B-B-B-B" --set-armour 100 --set-energy-shield 500 \
    --set-influences Shaper
poe build items search "<name>" --mod "Life" --slot Helmet --influence Shaper --rarity RARE
poe build items import "<name>" --slot Helmet --text "Rarity: Rare\nDoom Crown\nHubris Circlet\n..."
poe build items move "<name>" --from Helmet --to "Weapon 1"
poe build items swap "<name>" --slot1 "Weapon 1" --slot2 "Weapon 1 Swap"
poe build items compare "<name>" --slot Helmet --build2 "Other Build" --file2 /path/to/other.xml
poe build items set-active "<name>" --item-set 2
poe build items add-set "<name>"
poe build items remove-set "<name>" --item-set 3

# Gems
poe build gems add "<name>" --slot "Body Armour" --gem Fireball --gem "Spell Echo Support" \
    --level 20 --quality 20 --quality-id Default --include-full-dps
poe build gems remove "<name>" --index 0
poe build gems edit "<name>" --group 0 --swap "Fireball,Ball Lightning" \
    --set-level "Ball Lightning,21" --set-quality "Ball Lightning,23" \
    --set-quality-id "Ball Lightning,Anomalous" \
    --toggle "Spell Echo Support" --set-slot "Body Armour"
poe build gems add-to-group "<name>" --group 0 --gem "Added Fire Damage Support"
poe build gems remove-from-group "<name>" --group 0 --gem "Spell Echo Support"
poe build gems add-set "<name>"
poe build gems remove-set "<name>" --skill-set 3
poe build gems set-active "<name>" --skill-set 2

# Passive tree
poe build tree set "<name>" --nodes 100,200,300
poe build tree set "<name>" --add-nodes 500,600
poe build tree set "<name>" --remove-nodes 100,200
poe build tree set "<name>" --mastery 53188:64875 --mastery 53738:29161
poe build tree set "<name>" --add-mastery 99999:88888
poe build tree set "<name>" --remove-mastery 53188:64875
poe build tree search "<name>" "100"
poe build tree set "<name>" --class-id 5 --ascend-class-id 2 --version 3_25
poe build tree set "<name>" --spec 2 --nodes 100,200
poe build tree set-active "<name>" --spec 2
poe build tree add-spec "<name>" --title "Endgame"
poe build tree remove-spec "<name>" --spec 3

# Config
poe build config set "<name>" --boolean useFrenzyCharges=true --number enemyPhysicalHitDamage=5000
poe build config set "<name>" --string customMod="some value"
poe build config set "<name>" --remove useFrenzyCharges
poe build config preset "<name>" --preset boss
poe build config options --query "charge"
poe build config sets "<name>"
poe build config add-set "<name>" --title "Bossing"
poe build config remove-set "<name>" --config-set 2
poe build config switch-set "<name>" --config-set 2

# Notes
poe build notes "<name>" --set "Updated notes text"

# Main skill
poe build set-main-skill "<name>" --index 1

# Flasks
poe build flasks list "<name>"
poe build flasks add "<name>" --base "Granite Flask" --slot "Flask 1" --rarity MAGIC --quality 20 \
    --explicit "+3000 to Armour during Flask Effect"
poe build flasks edit "<name>" --slot "Flask 1" --set-name "Iron Skin" --set-quality 20 \
    --add-explicit "+3000 to Armour during Flask Effect" --remove-explicit 0
poe build flasks reorder "<name>" --order "Flask 2" --order "Flask 1" --order "Flask 3"
poe build flasks remove "<name>" --slot "Flask 1"

# Jewels
poe build jewels list "<name>"
poe build jewels add "<name>" --base "Cobalt Jewel" --slot "Jewel 1" --rarity RARE \
    --explicit "+10% to Fire Resistance"
poe build jewels remove "<name>" --slot "Jewel 1"
poe build jewels remove "<name>" --id 3
poe build jewels socket "<name>" --id 3 --node 26725
poe build jewels unsocket "<name>" --id 3
```

All write commands accept `--file <path>` to specify an explicit file path instead of resolving by name. Read commands `items list`, `config get` also accept `--file`. Mutation commands `delete`, `rename`, `duplicate`, `import` support `--json` for structured output. Config presets available: `mapping`, `boss`, `sirus`, `shaper`.

**Indexing**: Tree specs are 1-indexed (`--spec 1`). Gem groups are 0-indexed (`--index 0`). Main skill index is 1-based (`--index 1`).

## Claude/ Safety Layer

**User builds are treated as read-only.** All create and modify operations write to `Claude/` inside the PoB builds directory. When modifying a build that lives outside `Claude/`, it is automatically cloned there first — the original is never touched.

- **Create**: `poe build create` places new builds in `Claude/` by default
- **Modify**: Any write command (`notes --set`, `items add/remove/edit/import/move/swap/set-active/add-set/remove-set`, `gems add/remove/edit/add-set/remove-set/set-active`, `tree set/set-active/add-spec/remove-spec`, `config set/preset/add-set/remove-set/switch-set`, `flasks add/edit/remove`, `jewels add/remove/socket/unsocket`, `set-level`, `set-class`, `set-bandit`, `set-pantheon`, `set-main-skill`, `rename`) clones the build into `Claude/` if it isn't already there
- **Delete**: Refuses to delete builds outside `Claude/` (use `--file` to override)
- **JSON output**: When a clone occurs, the response includes `cloned_from` (original path) and `working_copy` (path to the Claude/ copy)
- **`--file` flag**: Bypasses the safety layer entirely — writes directly to the specified path

## Other Build Commands

```bash
poe build decode <build_code>                    # Decode a PoB sharing code to XML
poe build decode <build_code> --save "Imported"  # Decode and save to Claude/Imported.xml
poe build encode "<name>"                        # Encode build to PoB sharing code
poe build share "<name>"                         # Encode + generate sharing URL
poe build open "<name>"                          # Open build in PoB via pob:// protocol (Windows only)
poe build import <url_or_code> --name "Imported" # Import from pobb.in URL or raw code
poe build export "<name>" <destination>          # Copy build file
poe build engine load "<name>"                   # Load into PoB's Lua engine for live stats
poe build engine stats                           # Get calculated stats from loaded build
poe build engine info                            # PoB version, Lua runtime info
```

## PoB Build Structure

### Multiple Specs / Sets

PoB builds frequently contain multiple loadouts:
- **Leveling guides**: tree specs progressing through campaign to endgame
- **Imported characters**: snapshots at different levels
- **Gear progression**: budget → midrange → endgame item sets
- **Skill variants**: mapping vs bossing skill sets

### Disabled Gems

Gems with `enabled: false` are intentional — gem swaps, future upgrades, or alternate options.

### Config Section

Config controls assumptions that dramatically affect stats:
- `usePowerCharges`, `useFrenzyCharges`, `useEnduranceCharges`
- `conditionEnemyShocked`, `conditionEnemyChilled`
- `customMods` — **check these**, they can inflate stats
- `ailmentMode`

**Always compare configs** when comparing builds. 10M DPS with frenzy charges + custom mods is not comparable to a build without them.

### Build Notes

Notes often contain critical context: gearing strategies, gem swaps, crafting guides, FAQ. Always read them.

## Build File Location

- Build files are auto-detected from the standard PoB builds directory
- Build names support **prefix matching** — `"My RF"` resolves to `"My RF Jugg"` if it's the only match. Ambiguous prefixes return an error listing matches.
- PoB installation path: `poe build engine info`

## Known Limitations

- **Per-gem level/quality**: `gems add` applies the same level/quality to all gems in a group — use `gems edit --set-level` and `--set-quality` to adjust individual gems after
- **Round-trip preservation**: The write path (parse → modify → rewrite) may not preserve all original XML formatting or uncommon elements

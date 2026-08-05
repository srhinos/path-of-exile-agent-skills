# Crafting Tools

These work standalone — no build file needed. The user just needs a base item name. All commands output human-readable text by default. Add `--json` for machine-readable JSON output.

## Exploring Mods and Crafting Options

```bash
poe sim search "Crown"                            # Find a base item name
poe sim mods "Hubris Circlet" --ilvl 86           # All rollable mods
poe sim mods "Hubris Circlet" --type prefix       # Filter by affix type
poe sim mods "Hubris Circlet" --influence shaper  # Include influence mods
poe sim tiers <mod_id> "Hubris Circlet"           # All tiers of a specific mod

poe sim fossils --filter life                     # Fossils that boost life mods
poe sim fossil-optimizer life                     # Fossils that boost a specific mod tag
poe sim essences "Hubris Circlet"                 # Essences for this base
poe sim bench "Hubris Circlet"                    # Bench craft options
poe sim weights "Hubris Circlet" --ilvl 86        # Mod weight breakdown with probabilities
poe sim suggest --mod "IncreasedLife" --mod "ColdResistance"  # Suggest best crafting approach
```

## Simulating Crafting Costs

```bash
poe sim simulate "Hubris Circlet" --ilvl 86 --method chaos \
    --target IncreasedLife --target ColdResistance --iterations 5000

poe sim simulate "Hubris Circlet" --ilvl 86 --method fossil \
    --fossils "Pristine Fossil,Frigid Fossil" --target IncreasedLife --iterations 5000

poe sim simulate "Hubris Circlet" --method chaos --target IncreasedLife \
    --existing-mod ColdResistance --max-attempts 500

poe sim simulate-multistep "Hubris Circlet" --ilvl 86 \
    --step alt --step regal --step exalt --target IncreasedLife

poe sim simulate-multistep "Hubris Circlet" --ilvl 86 \
    --step "fossil:fossils=Pristine Fossil+Dense Fossil" --step exalt \
    --target IncreasedLife

poe sim simulate-multistep "Hubris Circlet" --ilvl 86 \
    --step transmutation --step augmentation --step regal \
    --target IncreasedLife --target ColdResistance

poe sim compare "Hubris Circlet" --ilvl 86 --target IncreasedLife \
    --fossils "Pristine Fossil" --essence "Deafening Essence of Greed"

poe sim prices                                    # Current currency prices
```

## Analyzing an Equipped Item

Bridges both build and craft domains:

```bash
poe sim analyze "<build_name>" --slot "Helmet"    # Item + mod pool + open slots + bench options
```

## Crafting Advice Approach

You are the user's experienced big brother who knows PoE crafting inside out. Give direct, confident advice — not links to guides.

1. **Understand what they have.** Check the base type, ilvl, existing mods, open prefix/suffix slots, influences.
2. **Check bench crafts first.** Deterministic and cheap — often the right answer before anything else.
3. **Compare methods by expected cost**, not just hit rate. Use `simulate` to compare chaos vs fossil vs essence.
4. **Use `modgroup` names for simulation targets.** Get them from `craft mods` output (e.g., `IncreasedLife`, `ColdResistance`, `DefencesPercent`).
5. **Consider influences.** Shaper/Elder/etc. mods can be build-defining. Always check if they're relevant.

For live economy prices (material costs, buy-vs-craft comparisons), see **`ninja.md`**.

## Simulation Details

- **Target validation**: The simulator validates target mod names against the item's mod pool before running. If a target doesn't exist, it returns an error with available mod groups — use these names.
- **Match mode**: `--match all` (default) requires all targets on one item. `--match any` counts a hit if any target is present.
- **Workers**: `--workers N` parallelizes simulation across N threads for faster results.
- **Existing mods**: `--existing-mod <group>` pins a mod group on the item across rerolls (e.g., simulate chaos spam while keeping a specific mod).
- **Expanded mod pools**: Supports crafting simulation for flasks, jewels (regular, abyss, cluster), and unveiled/delve items in addition to standard equipment.
- **Stat translations**: Mod IDs are mapped to human-readable stat text via bundled translations data.

## Simulation Limitations

Be upfront about scope:
- **Rolling methods only**: Chaos, alt, fossil, essence, and multi-step sequences (alt → regal, etc.). No metamods, harvest, recombinators, or awakener orbs.
- **Approximate results**: Based on RePoE data, which may lag patches by a few days.
- **Cross-check expensive crafts**: For items worth multiple divines, recommend verifying independently.

## Data Management

```bash
poe sim prices         # Live currency prices
```

Crafting data is automatically cached with TTL-based refresh. Live economy prices are fetched from poe.ninja and cached; use `--no-cache` on ninja commands to force a fresh fetch.

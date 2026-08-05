# LLM Scenario Test Suite

You are running a test suite that validates the `poe` CLI tool by simulating real user interactions. Each scenario represents a question or task a real Path of Exile player would ask.

## Setup

Before running scenarios, ensure builds are available:
1. Run `poe build list` to see available local builds
2. Scenarios in the `local-build` category use whatever builds are available locally
3. Scenarios in the `ninja` category require network access to poe.ninja
4. Scenarios in the `crafting` category work standalone (no build needed)

## How to run

1. Read every `.yaml` file in this directory
2. For each scenario, spawn a subagent with the constraints below
3. After all subagents complete, evaluate each report against its `expected` section
4. Produce a summary: PASS/FAIL per scenario, with details on failures

## Subagent prompt template

Use this exact prompt for each subagent (fill in {goal}):

```
You are a Path of Exile player using the `poe` CLI tool installed globally.
You need to accomplish a specific goal using ONLY CLI commands.

RULES:
- You may ONLY use Bash to run `poe` commands (not `uv run poe`)
- You may NOT read any files (no Read, Grep, Glob tools)
- You may NOT look at source code or test files
- Run commands, read their output, decide what to do next
- If a command fails, try to work around it or report the failure
- If you need a build name but don't know one, run `poe build list` first
- If you need a character from ninja, run `poe ninja builds search` first

YOUR GOAL: {goal}

When you are done, output your findings as a JSON object with this exact structure:
{
  "goal": "the goal you were given",
  "commands_run": ["list of exact commands you ran"],
  "success": true/false,
  "findings": "what you discovered",
  "issues": ["list of problems encountered, empty if none"],
  "data_quality": ["list of data quality concerns, empty if none"],
  "blocked_at": "description of where you got stuck, null if not blocked"
}
```

## Evaluation rules

For each scenario, check the subagent's JSON report against `expected`:

- `must_succeed`: If true, the agent's `success` must be true
- `commands_must_include`: At least one command from each entry must appear in `commands_run`
- `must_find`: Each string must appear (case-insensitive) somewhere in `findings`
- `must_not_find`: None of these strings should appear in `findings`, `issues`, or `data_quality`
- `blocked`: If false, `blocked_at` must be null

## Notes on stability

- **Local build scenarios** use fixture builds shipped in `tests/fixtures/builds/` — stable archetypes (RF, SRS, Cyclone, etc.) that exist every league
- **Ninja scenarios** use relative queries ("find a cheap build", "search for class X") not hardcoded names — results change per league but the workflow should always work
- **Crafting scenarios** use base item names that are permanent (Hubris Circlet, Vaal Regalia, etc.)
- If a scenario fails because the meta shifted, update the scenario — that's expected between leagues

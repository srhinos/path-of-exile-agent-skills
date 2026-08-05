# CLAUDE.md

## Project Overview

Python CLI for interacting with Path of Building (PoB) build files, poe.ninja economy data, and crafting simulation. Managed with `uv`. Entry point: `poe` command via `poe.app:app` (cyclopts).

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture, data flows, and model reference.

## Build and Test Commands

- **Always use `uv run`** to execute Python and tools. Never use bare `python`, `python3`, or `pip` — they may resolve to the system Python or trigger the Windows Store alias. Every command must go through `uv run`.
- Install: `uv sync --all-extras`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Type check: `uv run ty check poe/`
- Run all tests: `uv run pytest`
- Run with coverage: `uv run pytest --cov --cov-report=term-missing`
- Per-file coverage check: `uv run coverage-threshold`
- Single test: `uv run pytest tests/path/to/test_file.py::test_name`
- Full pre-commit check: `uv run ruff check . && uv run ruff format --check . && uv run ty check poe/ && uv run pytest --cov && uv run coverage-threshold`
- Always run ruff, ty, and tests before committing any changes.
- For one-off Python snippets, use `uv run python -c "..."` — never `python3 -c`.

### Code/Test/Verify Loop

1. **Code:** Make changes.
2. **Lint/Format:** `uv run ruff check . && uv run ruff format --check .`
3. **Type check:** `uv run ty check poe/`
4. **Test:** `uv run pytest` (or targeted test file)
5. **Full gate (before commit):** `uv run ruff check . && uv run ruff format --check . && uv run ty check poe/ && uv run pytest`

## Architecture (Brief)

```
Commands → Services → Models → Data
```

- **Commands** (`poe/commands/`) — CLI args, call services, render output. No business logic.
- **Services** (`poe/services/`) — all business logic. `build/`, `ninja/`, `repoe/`.
- **Models** (`poe/models/`) — Pydantic data containers. No logic.
- **Data** — XML files (PoB builds) or bundled JSON (`poe/data/repoe/`).

### Safety Layer (Clone-on-Write)

Write operations clone the original build into a `Claude/` subfolder before modifying. Reads prefer `Claude/` copies for consistency. Bypassed when `--file` is explicitly provided.

### Key Patterns

**Output:** All commands output human-readable text by default. Add `--json` for machine-readable JSON. Human formatters registered via `@human_formatter(ModelClass)` in `formatters.py`. Commands call `output.render(data, json_mode=flag)`.

**Errors:** All domain exceptions inherit from `PoeError`. The top-level `run()` in `app.py` catches `PoeError` and serializes `{"error": "..."}` to stderr.

**RePoE data:** Bundled JSON in `poe/data/repoe/`, ingested from `vendor/RePoE/` (git subtree) by a dev-only pipeline. Never fetched over HTTP at runtime.

## Code Style

- No file-level docstrings (module docstrings). Code should be self-documenting.
- No random or explanatory comments. Only comment when the logic is genuinely non-obvious and cannot be clarified through naming or structure.
- No inline `noqa` comments — fix the code or update ruff config instead.
- Use strict typing (ty enforced)
- Classes: PascalCase (`BuildDocument`)
- Functions/methods: snake_case (`resolve_build_file()`)
- Constants: SCREAMING_SNAKE_CASE (`CLAUDE_SUBFOLDER`) — all constants in `poe/constants.py`, never local `_CONSTANT` in service files
- When writing tests, do NOT put a docstring to explain what the test does:
  ```
  # BAD: redundant docstring
  def test_cache_preserves_symtable(self):
      """Test that symtable is preserved in cache"""
      ...

  # GOOD:
  def test_cache_preserves_symtable(self):
      ...
  ```

## Code Change Guidelines

- **Minimize diffs**: Prefer the smallest change that satisfies the request. Avoid unrelated refactors or style rewrites unless necessary for correctness
- **No speculative getattr**: Never use `getattr(obj, "attr", default)` when unsure about attribute names. Check the class definition or source code first
- **Fail fast**: Write code with fail-fast logic by default. Do not swallow exceptions with errors or warnings
- **No fallback logic**: Do not add fallback logic unless explicitly told to and agreed with the user
- **No guessing**: Do not say "The issue is..." before you actually know what the issue is. Investigate first.
- **No backwards compatibility code**: No legacy `to_dict()`, no import aliases, no fallback attribute names. Single consumer, breaking changes are fine.
- **Service naming**: Service folders are named after data sources (`build/`, `ninja/`, `repoe/`), not CLI command names.

## Imports

- Organize imports by standard Python conventions
- Prefer specific imports: `from poe.exceptions import BuildNotFoundError`
- Prefer module-level imports, unless there is a good reason to put them inside functions
- Absolute imports only — relative imports are banned (ruff `ban-relative-imports = "all"`)

## Testing

- 1800+ tests, 90% minimum coverage enforced (95% for build services/models, 80% for engine/pipeline)
- Tests mirror source layout: `poe/services/build/build_service.py` → `tests/services/build/test_build_service.py`
- Strict ruff linting: `select = ["ALL"]` — never add `noqa` or edit `pyproject.toml` to ignore a rule
- Test fixtures in `tests/conftest.py`:
  - `invoke_cli(app, args)` → `CliResult` with output/exit_code/exception
  - `MINIMAL_BUILD_XML` — complete PoB XML template for testing
  - `PoBXmlBuilder` — fluent builder for constructing test builds
  - `make_repoe_data()` / `REPOE_DATA` — mock RepoE data for crafting tests
  - `fixture_path()` — resolve files from `tests/fixtures/`
- HTTP mocking: `respx` for ninja service tests
- Integration tests (real PoB/network) marked with `@pytest.mark.integration`

### Required test categories (beyond happy path)

Coverage % is necessary but not sufficient. Every non-trivial function needs tests across all five categories below. Code reviews keep finding bugs that "passed all tests" because tests only checked shape and happy paths. Each category targets a distinct failure mode that the others miss.

1. **Invariant assertions, not shape assertions.** After a function returns, assert that the result respects domain rules — not just that the right type came back. `assert isinstance(result, SimResult)` is worthless on its own. `assert len(item.prefixes) <= item.max_prefixes` is the test that catches the bug. Every simulation/mutation test should assert game-rule invariants on the output state.

2. **Parametrize over the input space, not the canonical output space.** If a function promises case-insensitivity, normalization, or alias-resolution, the parametrize values must include the *non-canonical* forms. `@pytest.mark.parametrize("item_type", NINJA_POE2_EXCHANGE_TYPES)` only proves "canonical input survives" — it can't catch a broken normalizer. Use lowercase, uppercase, mixed case, aliases, and underscores; assert all map to the same canonical output.

3. **Cover every value in an enum/lookup, not one representative.** When a function dispatches on an enum (Influence, Rarity, CraftMethod, currency aliases, item types), parametrize over the *full* enum or include every key in the lookup table. Single-representative tests pass coincidentally when the picked value happens to round-trip through the bug. The Influence codename bug shipped because only `shaper` was tested and Shaper's codename is its lowercased name.

4. **Negative tests for every `raise`.** Every `raise PoeError`, `raise SimDataError`, `raise NinjaError`, `raise ApiSchemaError` needs a test that triggers it with `pytest.raises(...)` and asserts the error message includes the relevant context. Validation paths that aren't tested are validation paths that don't exist.

5. **Semantic invariants on Pydantic models.** Pydantic enforces types, not semantics. If a `float` field must be finite, write a test that asserts it. If a `list[str]` must be non-empty, write a test that asserts it. If two fields must agree (`hits <= iterations`), write a test that asserts it. Write the test even when the producer "always returns valid values" today — that contract decays silently otherwise.

6. **Construct objects through the production code path, not just kwargs.** A Pydantic validator that fires on `Item(rarity="HEROIC")` may not fire on `item.rarity = "HEROIC"` — Pydantic v2's `validate_assignment` defaults to `False`. The XML parser does `BuildDocument()` then `setattr` for the next 200 lines, so kwargs-only tests give a false sense of safety. For every model touched by a parser, an importer, or a service mutation, add a test that exercises the same construction pattern: load a fixture, mutate via setattr, write back, and reload. If the validator should fire, set `model_config = ConfigDict(validate_assignment=True)`.

When adding a test, ask: which of these six categories does it fall into? If the answer is "none, it just exercises the happy path," it's incomplete. Add the others.

## Git

- Commit messages are one line, brief, and Title Cased Like This.
- Never `git add -f` gitignored files. If a file is ignored, it stays ignored.
- Commit messages describe *what changed and why* for external readers. Never reference internal plan phases, step numbers, or implementation details (e.g., "Phase 3" or "Step 2 of plan").

## Planning

- Before implementing non-trivial plans, run 4+ parallel subagents with the **same prompt** to independently analyze the problem. Converging conclusions validate the approach; divergence reveals blind spots.
- The main agent handles all code changes directly — subagents are for research and verification only.

# Task Sequence: Lean & Trustworthy agy-skills Refactor

## Phase 1: Prune Bloat & Delete Dead Modules
- [x] Task 1.1: Delete `spaceship.py` and `agy_skills/catalog.py`.
- [x] Task 1.2: Delete `agy_skills/plugin_client.py`.
- [x] Task 1.3: Remove marketplace and plugin-client imports from `agy_skills/__init__.py`, `agy_skills/cli.py`, and `agy_skills/main.py`.

## Phase 2: Core Data Models & Deterministic State
- [x] Task 2.1: Refactor `agy_skills/models.py` — streamline `Scope` to `WORKSPACE` and `GLOBAL`; compute token counts directly from byte length without calibration tables; keep `Skill` and `Rule` dataclasses lean.
- [x] Task 2.2: Implement `agy_skills/state.py` — atomic JSON read/write for `.agents/config.json`, `.gemini/config.json`, and `~/.gemini/config/config.json` with strict error handling.
- [x] Task 2.3: Refactor `agy_skills/discovery.py` — remove `OFFICIAL_IDE_CALIBRATION`; implement deterministic traversal for workspace and global skills/rules; wire toggle logic to `agy_skills/state.py`.
- [x] Task 2.4: Refactor `agy_skills/validator.py` — enforce `SKILL.md` frontmatter rules and 24 KB rule ceiling with precise failure messages.

## Phase 3: High-Reliability CLI Commands
- [x] Task 3.1: Update `agy_skills/cli.py` to support `list`, `status`, `enable`, `disable`, `info`, and `lint` with optional `--json` output.
- [x] Task 3.2: Update `agy_skills/main.py` argument parsing to remove unused subcommands (`mcp`, `agents`, `install`, `plugin`) and ensure zero uncaught exception crashes.

## Phase 4: Rebuild Clean 2-Pane TUI
- [x] Task 4.1: Rewrite `agy_skills/tui/app.py` to provide the split-view (Left: Grouped Skills & Rules list; Right: Card + preview; Bottom: Budget bar & shortcut hints).
- [x] Task 4.2: Implement keyboard handlers (`j`/`k`, `Space` toggle, `Tab` scope cycle, `e` editor spawn via `$EDITOR`, `/` filter, `q` quit).
- [x] Task 4.3: Ensure clean curses cleanup on exit, resize recovery, and absence of visual artifacts.

## Phase 5: Test Suite Verification & CI Compliance
- [x] Task 5.1: Update tests in `tests/` (`test_discovery.py`, `test_cli.py`, `test_state.py`) to cover all new behaviors and removed bloat.
- [x] Task 5.2: Execute `scripts/ci.sh` to confirm syntax verification and unit tests pass cleanly.

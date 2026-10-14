# Specification: Lean & Trustworthy agy-skills CLI & TUI

## 1. Problem Statement & Objectives
The existing codebase accrued synthetic bloat (fake star counts, reverse-engineered language server RPC mocks, hardcoded magic calibrations for IDE plugins, and multi-tab curses modals). 

This refactor prunes synthetic components and establishes a lean, deterministic, stdlib-only Python tool for:
1. Discovering local skills and rules across Workspace and Global scopes.
2. Validating format compliance (`SKILL.md` frontmatter, 24 KB rule limits).
3. Computing honest token counts from actual file contents.
4. Toggling active state deterministically via workspace/global JSON config without swallowed exceptions.
5. Providing a fast, responsive 2-pane TUI and equivalent CLI.

## 2. Scope of Removals (Pruning)
- **Delete `agy_skills/catalog.py`**: Remove all fake marketplace catalog entries and scraping logic.
- **Delete `agy_skills/plugin_client.py`**: Remove Language Server RPC client and `localhost:5387` connection.
- **Delete `spaceship.py`**: Remove unrelated DNS management script.
- **Prune `agy_skills/discovery.py`**: Remove `OFFICIAL_IDE_CALIBRATION`, simulated plugin breakdown modals, and heuristic mocks.
- **Simplify `agy_skills/tui/app.py`**: Replace the 5-tab modal browser with a clean 2-pane split-view focused purely on Skills & Rules.

## 3. Core Architecture & Component Boundaries

### 3.1 Data Models (`agy_skills/models.py`)
- `Scope(Enum)`: `WORKSPACE`, `GLOBAL`. (Remove `BUILTIN`, `CATALOG`).
- `TokenBudget`: Default 20,000 tokens limit.
- `Skill(dataclass)`:
  - `name`: string identifier
  - `description`: extracted from YAML frontmatter
  - `path`: Path to directory
  - `skill_file`: Path to `SKILL.md`
  - `scope`: `Scope`
  - `tokens`: integer (computed as `max(1, round(len(raw_content) / 3.5))`)
  - `is_active`: boolean
  - `is_valid`: boolean
  - `validation_errors`: List[str]
- `Rule(dataclass)`:
  - `name`: string identifier (e.g. `GEMINI.md`)
  - `path`: Path to file
  - `scope`: `Scope`
  - `size_bytes`: integer
  - `tokens`: integer (computed from text)
  - `is_active`: boolean
  - `is_valid`: boolean (`size_bytes <= 24576`)

### 3.2 Filesystem Discovery & State (`agy_skills/discovery.py`, `agy_skills/state.py`)
- **Workspace Discovery Paths**:
  - Skills: `<workspace>/.agents/skills/*/SKILL.md`, `<workspace>/.gemini/skills/*/SKILL.md`
  - Rules: `<workspace>/GEMINI.md`, `<workspace>/.gemini/GEMINI.md`
- **Global Discovery Paths**:
  - Skills: `~/.gemini/config/skills/*/SKILL.md`
  - Rules: `~/.gemini/config/GEMINI.md`
- **Precedence & Invariants**:
  - Workspace root is detected by searching parents for `.git`, `.agents`, or `.gemini`.
  - `Path.home()` is strictly prevented from being treated as a workspace root.
  - A workspace skill/rule overrides a global skill/rule of the same name.
- **State Persistence**:
  - Workspace: `<workspace>/.agents/config.json` (fallback `<workspace>/.gemini/config.json`)
  - Global: `~/.gemini/config/config.json`
  - Schema:
    ```json
    {
      "skills": {
        "<skill_name>": { "enabled": true }
      },
      "rules": {
        "<rule_name>": { "enabled": true }
      }
    }
    ```
  - **Zero Silent Failures**: All config reads/writes propagate explicit errors (`IOError`, `PermissionError`, `json.JSONDecodeError`) to the caller instead of `except Exception: pass`.

### 3.3 CLI Interface (`agy_skills/cli.py`, `agy_skills/main.py`)
- `agy-skills`: Launch the 2-pane TUI when no subcommand is specified.
- `agy-skills list [--scope workspace|global] [--json]`: Print discovered items, active indicator, token count, and path.
- `agy-skills status [--json]`: Print context token gauge, active vs disabled count, and compliance audit.
- `agy-skills enable <name> [--scope workspace|global]`: Enable skill or rule; exit 0 on success, exit 1 on error.
- `agy-skills disable <name> [--scope workspace|global]`: Disable skill or rule; exit 0 on success, exit 1 on error.
- `agy-skills info <name> [--json]`: Print full metadata, file location, tokens, and markdown content.
- `agy-skills lint`: Validate all skills/rules; exit 0 if all valid, exit 1 with failure details.

### 3.4 Streamlined 2-Pane TUI (`agy_skills/tui/app.py`)
- Standard library `curses` implementation.
- **Left Pane (List View)**:
  - Categorized groups: `WORKSPACE SKILLS`, `WORKSPACE RULES`, `GLOBAL SKILLS`, `GLOBAL RULES`.
  - Status indicator: `●` (active / green) or `○` (disabled / dim).
  - Item name and token count aligned to right margin of pane.
  - Selection cursor: highlighted row navigable with `j`/`k` or `↑`/`↓`.
- **Right Pane (Inspector View)**:
  - Header card: Name, Scope, Token count, Byte size, File path, Active status.
  - Clean wrapped body preview (no buggy table formatting; clean headings and bullet indentation).
  - Scrollable detail view with `d`/`u` or `PageDown`/`PageUp`.
- **Bottom Bar**:
  - Real-time token budget gauge: `Context: [▓▓▓░░░░░] X / 20,000 tok (Y%)`.
  - Responsive shortcut bar:
    - `[Space]`: Toggle enabled/disabled state (immediate redraw + config save).
    - `[Tab]`: Cycle scope filter (`ALL` -> `WORKSPACE` -> `GLOBAL`).
    - `[e]`: Suspend curses, open file in `$EDITOR`, restore curses upon exit.
    - `[/]`: Live search filter.
    - `[q]` / `[Esc]`: Quit cleanly.
- Terminal resize (`curses.KEY_RESIZE`) handled smoothly without crashing or text wrapping overflow.

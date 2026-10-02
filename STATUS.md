# Project Status & Wayfinding

### 1. Ground Truth & Verification
- **Workspace**: `/Users/kush-chou/Projects/agy-skills`
- **Active Branch**: `main (clean)`
- **Verification Command**: `python3 -m unittest discover -s tests`
- **Deployment / Runtime Env**: macOS Darwin / Python 3.9+ / Google Antigravity & Gemini CLI runtime

### 2. Invariants & Landmines
- *Negative Constraints*:
  - Zero git-coupling runtime: CLI commands must never execute git subcommands that depend on commit HEAD or branch states.
  - Non-destructive deactivation: Disabling active skills unlinks symlinks cleanly without altering or deleting catalog sources. Real directories are auto-backed up before removal.
  - Native Antigravity aesthetics: Output and viewer formatting must match the exact 4-tier discovery layout and ANSI color palette of Antigravity CLI.
- *Fragile Edges / Gotchas*:
  - Avoid putting raw HTML or `<code>` tags in terminal outputs and diagram nodes.

### 3. Frontier & Fog of War
- **Current Objective**: Implement GitHub sparse registry index crawler for community packages (`agy-skills search --remote`, `agy-skills install <author>/<skill>`).
- **Next in Queue**:
  1. Community registry index crawler & remote schema.
  2. One-click install from remote GitHub URLs / registry.
  3. Prepare for `agyskills.sh` domain deployment on launch day.
- **Blocked / Waiting**: None.
- **Fog of War (Unspecified)**: None.

### 4. Decisions & Log
- `2026-10-02`: Implemented interactive dual-pane curses TUI browser (`agy_skills/browse.py`, `agy-skills browse` / `tui` / `ui`). Added real-time navigation, live preview rendering, inline search (`/`), scope cycle (`Tab`), and atomic toggle enable/disable (`Space`/`Enter`). Test suite expanded to 8 tests passing.
- `2026-10-02`: Initialized standalone repository for `agy-skills`. Implemented multi-scope resolver (`workspace`, `shared`, `global`), frontmatter parser, non-destructive symlink engine, and Antigravity-native terminal viewer. 5/5 unit tests passing.

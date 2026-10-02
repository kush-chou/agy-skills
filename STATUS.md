# Project Status & Wayfinding

### 1. Ground Truth & Verification
- **Workspace**: `/Users/kush-chou/.gemini/antigravity/scratch/agy-skills`
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
- **Current Objective**: Package initial v0.1.0 release, symlink binary into PATH, and verify interactive CLI end-to-end.
- **Next in Queue**:
  1. Add curses-based interactive full-screen browser (`agy-skills browse`).
  2. Implement GitHub sparse registry index crawler for community packages.
  3. Prepare for `agyskills.sh` domain deployment on launch day.
- **Blocked / Waiting**: None.
- **Fog of War (Unspecified)**: None.

### 4. Decisions & Log
- `2026-10-02`: Initialized standalone repository for `agy-skills`. Implemented multi-scope resolver (`workspace`, `shared`, `global`), frontmatter parser, non-destructive symlink engine, and Antigravity-native terminal viewer. 5/5 unit tests passing.

# agy-skills ⚡

> Fast, modular context package manager for Google Antigravity & Gemini CLI.

`agy-skills` brings **Homebrew / Oh-My-Zsh ergonomics** to AI coding agent context. It provides atomic, non-destructive activation of skills, behavioral rules, and subagents across project workspaces and global developer dotfiles.

---

## 🏛️ Architecture Overview

```text
Scope Detection ($PWD)
 ├── In Git / .agents repo ──> Workspace Scope  (<project>/.agents/skills/)
 └── In Home directory    ──> Global Dotfiles  (~/.agents/skills/)

Discovery Hierarchy
 ├── 1. Workspace Skills   (<project>/.agents/skills/ or ~/.agents/skills/)
 ├── 2. Shared Skills      (~/.gemini/skills/)
 ├── 3. Built-in Skills    (antigravity-cli/builtin/skills/)
 └── 4. Available Catalog  (~/.agents.backup/skills/)
```

---

## ⚡ Quick Start

### Installation

```bash
# Clone and install locally
git clone https://github.com/kush-chou/agy-skills.git ~/.gemini/antigravity/scratch/agy-skills
bash ~/.gemini/antigravity/scratch/agy-skills/install.sh
```

### Usage Cheatsheet

```bash
# List all skills across the 4 Antigravity discovery tiers
agy-skills list

# Enable a skill in current project workspace (symlink)
agy-skills add writing-beats

# Enable a skill into global developer dotfiles (~/.agents/skills/)
agy-skills add writing-beats --global

# Enable a skill into shared machine skills (~/.gemini/skills/)
agy-skills add writing-beats --shared

# View a skill runbook with formatted Antigravity viewer
agy-skills show migrate-workflows

# Fast keyword search across catalog and active skills
agy-skills search "android"

# Disable / unlink an active skill safely
agy-skills remove writing-beats

# Audit scope resolution and health
agy-skills status
```

---

## 🔒 Safety & Invariants

1. **Non-Destructive Lifecycle**: Disabling a skill simply unlinks its symlink. Source files in your backup catalog are never modified or removed.
2. **Zero Git-Coupling at Runtime**: Operates purely on deterministic filesystem paths, avoiding git branch or detached HEAD traps.
3. **Native Antigravity Alignment**: Formats output to perfectly mirror Antigravity's internal discovery hierarchy and UI palette.

---

## 🧪 Testing

```bash
python3 -m unittest discover -s tests
```

---

## License

Apache-2.0 © 2026 Kushagra Choudhary

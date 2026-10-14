"""Filesystem discovery and registry for Antigravity skills and rules."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from .models import DEFAULT_TOKEN_BUDGET, Rule, Scope, Skill
from .state import (
    is_rule_enabled,
    is_skill_enabled,
    load_config_for_scope,
    set_rule_enabled,
    set_skill_enabled,
    write_config,
)
from .validator import validate_rule, validate_skill


def find_workspace_root(start_dir: Optional[Path] = None) -> Path:
    """Find workspace root by searching upwards for .git, .agents, or .gemini.

    Invariant: Path.home() is strictly prevented from being treated as a workspace root.
    """
    curr = (start_dir or Path.cwd()).resolve()
    home = Path.home().resolve()

    for p in [curr, *curr.parents]:
        if p == home:
            continue
        if (p / ".git").exists() or (p / ".agents").exists() or (p / ".gemini").exists():
            return p

    return curr


def get_global_config_dir(home_dir: Optional[Path] = None) -> Path:
    """Return canonical global config directory (~/.gemini/config)."""
    home = home_dir or Path.home()
    return home / ".gemini" / "config"


class CustomizationRegistry:
    """Discovers, indexes, validates, and manages Antigravity skills and rules."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        home_dir: Optional[Path] = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ):
        self.workspace_root = find_workspace_root(workspace_root)
        self.home_dir = home_dir or Path.home()
        self.global_config_dir = get_global_config_dir(self.home_dir)
        self.workspace_gemini_dir = self.workspace_root / ".gemini"
        self.token_budget: int = token_budget

        self.skills: List[Skill] = []
        self.rules: List[Rule] = []

        # Legacy compatibility stubs (always empty)
        self.subagents: list = []
        self.plugins: list = []
        self.mcp_servers: list = []

    def discover_workspace_skills(self) -> List[Skill]:
        """Discover skills in workspace scope (<workspace>/.agents/skills and <workspace>/.gemini/skills),
        including active skills and disabled skills inside .disabled/ directories."""
        candidates: List[Path] = [
            self.workspace_root / ".agents" / "skills",
            self.workspace_root / ".gemini" / "skills",
        ]
        seen_names: Set[str] = set()
        skills: List[Skill] = []

        for base in candidates:
            if not base.is_dir():
                continue

            # 1. Active skills
            for item in sorted(base.iterdir()):
                if not item.is_dir() or item.name.startswith("."):
                    continue
                skill = Skill.from_directory(item, Scope.WORKSPACE)
                if skill is not None:
                    skill.is_active = True
                    validate_skill(skill)
                    if skill.name in seen_names:
                        for existing in skills:
                            if existing.name == skill.name:
                                existing.aliases.append(skill.path)
                                break
                    else:
                        seen_names.add(skill.name)
                        skills.append(skill)

            # 2. Disabled skills in .disabled/
            dis_base = base / ".disabled"
            if dis_base.is_dir():
                for item in sorted(dis_base.iterdir()):
                    if not item.is_dir() or item.name.startswith("."):
                        continue
                    skill = Skill.from_directory(item, Scope.WORKSPACE)
                    if skill is not None:
                        skill.is_active = False
                        validate_skill(skill)
                        if skill.name in seen_names:
                            for existing in skills:
                                if existing.name == skill.name:
                                    existing.aliases.append(skill.path)
                                    break
                        else:
                            seen_names.add(skill.name)
                            skills.append(skill)

        return skills

    def discover_global_skills(self) -> List[Skill]:
        """Discover skills in global scope (~/.gemini/config/skills and fallback ~/.agents/skills),
        including active skills and disabled skills inside .disabled/ directories."""
        candidates: List[Path] = [
            self.home_dir / ".gemini" / "config" / "skills",
            self.home_dir / ".agents" / "skills",
        ]
        seen_names: Set[str] = set()
        skills: List[Skill] = []

        for base in candidates:
            if not base.is_dir():
                continue

            # 1. Active skills
            for item in sorted(base.iterdir()):
                if not item.is_dir() or item.name.startswith("."):
                    continue
                skill = Skill.from_directory(item, Scope.GLOBAL)
                if skill is not None:
                    skill.is_active = True
                    validate_skill(skill)
                    if skill.name in seen_names:
                        for existing in skills:
                            if existing.name == skill.name:
                                existing.aliases.append(skill.path)
                                break
                    else:
                        seen_names.add(skill.name)
                        skills.append(skill)

            # 2. Disabled skills in .disabled/
            dis_base = base / ".disabled"
            if dis_base.is_dir():
                for item in sorted(dis_base.iterdir()):
                    if not item.is_dir() or item.name.startswith("."):
                        continue
                    skill = Skill.from_directory(item, Scope.GLOBAL)
                    if skill is not None:
                        skill.is_active = False
                        validate_skill(skill)
                        if skill.name in seen_names:
                            for existing in skills:
                                if existing.name == skill.name:
                                    existing.aliases.append(skill.path)
                                    break
                        else:
                            seen_names.add(skill.name)
                            skills.append(skill)

        return skills

    def discover_workspace_rules(self) -> List[Rule]:
        """Discover rules in workspace scope (<workspace>/GEMINI.md, <workspace>/.gemini/GEMINI.md,
        and <workspace>/.agents/rules/*.md), including disabled rules."""
        candidates: List[Tuple[Path, Path, str]] = [
            (
                self.workspace_root / "GEMINI.md",
                self.workspace_root / ".disabled" / "GEMINI.md",
                "GEMINI.md",
            ),
            (
                self.workspace_root / ".gemini" / "GEMINI.md",
                self.workspace_root / ".gemini" / ".disabled" / "GEMINI.md",
                "GEMINI.md",
            ),
        ]

        agents_rules_dir = self.workspace_root / ".agents" / "rules"
        if agents_rules_dir.is_dir():
            for f in sorted(agents_rules_dir.glob("*.md")):
                if f.is_file() and not f.name.startswith("."):
                    candidates.append((f, agents_rules_dir / ".disabled" / f.name, f.name))
            if (agents_rules_dir / ".disabled").is_dir():
                for f in sorted((agents_rules_dir / ".disabled").glob("*.md")):
                    if f.is_file() and not f.name.startswith("."):
                        candidates.append((agents_rules_dir / f.name, f, f.name))

        seen_names: Set[str] = set()
        rules: List[Rule] = []

        for active_path, disabled_path, name in candidates:
            if name in seen_names:
                continue

            target_path = None
            is_active = True
            if active_path.is_file():
                target_path = active_path
                is_active = True
            elif disabled_path.is_file():
                target_path = disabled_path
                is_active = False

            if target_path is not None:
                rule = Rule.from_file(target_path, Scope.WORKSPACE, name_override=name)
                if rule is not None:
                    rule.is_active = is_active
                    validate_rule(rule)
                    seen_names.add(rule.name)
                    rules.append(rule)

        return rules

    def discover_global_rules(self) -> List[Rule]:
        """Discover rules in global scope (~/.gemini/config/GEMINI.md, ~/.agents/rules/*.md),
        including disabled rules."""
        candidates: List[Tuple[Path, Path, str]] = [
            (
                self.home_dir / ".gemini" / "config" / "GEMINI.md",
                self.home_dir / ".gemini" / "config" / ".disabled" / "GEMINI.md",
                "GEMINI.md",
            ),
        ]

        for base in [self.home_dir / ".agents" / "rules", self.home_dir / ".gemini" / "config" / "rules"]:
            if base.is_dir():
                for f in sorted(base.glob("*.md")):
                    if f.is_file() and not f.name.startswith("."):
                        candidates.append((f, base / ".disabled" / f.name, f.name))
                if (base / ".disabled").is_dir():
                    for f in sorted((base / ".disabled").glob("*.md")):
                        if f.is_file() and not f.name.startswith("."):
                            candidates.append((base / f.name, f, f.name))

        seen_names: Set[str] = set()
        rules: List[Rule] = []

        for active_path, disabled_path, name in candidates:
            if name in seen_names:
                continue

            target_path = None
            is_active = True
            if active_path.is_file():
                target_path = active_path
                is_active = True
            elif disabled_path.is_file():
                target_path = disabled_path
                is_active = False

            if target_path is not None:
                rule = Rule.from_file(target_path, Scope.GLOBAL, name_override=name)
                if rule is not None:
                    rule.is_active = is_active
                    validate_rule(rule)
                    seen_names.add(rule.name)
                    rules.append(rule)

        return rules

    def _sync_item_disk_state(self, item: Union[Skill, Rule], should_be_enabled: bool) -> None:
        """Move item into or out of .disabled on disk so Antigravity runtime accurately injects/omits it."""
        try:
            if not should_be_enabled:
                if item.path.exists() and item.path.parent.name != ".disabled":
                    dest_dir = item.path.parent / ".disabled"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / item.path.name
                    item.path.rename(dest_path)
                    item.path = dest_path
                    if isinstance(item, Skill):
                        item.skill_file = dest_path / "SKILL.md"
                    item.is_active = False
            else:
                if item.path.exists() and item.path.parent.name == ".disabled":
                    dest_dir = item.path.parent.parent
                    dest_path = dest_dir / item.path.name
                    item.path.rename(dest_path)
                    item.path = dest_path
                    if isinstance(item, Skill):
                        item.skill_file = dest_path / "SKILL.md"
                    item.is_active = True
        except Exception:
            pass

    def discover_all(self) -> Tuple[List[Skill], List[Rule]]:
        """Run full discovery across workspace and global scopes, resolving precedence and state."""
        ws_skills = self.discover_workspace_skills()
        gl_skills = self.discover_global_skills()
        ws_rules = self.discover_workspace_rules()
        gl_rules = self.discover_global_rules()

        # Load configs (propagates explicit IO/JSON errors on corrupt files)
        _, ws_cfg = load_config_for_scope(Scope.WORKSPACE, self.workspace_root, self.home_dir)
        _, gl_cfg = load_config_for_scope(Scope.GLOBAL, self.workspace_root, self.home_dir)

        # Apply state to workspace skills and sync filesystem
        for s in ws_skills:
            target_enabled = is_skill_enabled(ws_cfg, s.name, default=s.is_active)
            self._sync_item_disk_state(s, target_enabled)
            s.is_active = target_enabled

        # Apply state to workspace rules and sync filesystem
        for r in ws_rules:
            target_enabled = is_rule_enabled(ws_cfg, r.name, default=r.is_active)
            self._sync_item_disk_state(r, target_enabled)
            r.is_active = target_enabled

        # Precedence: Workspace skills/rules override global ones with matching names
        ws_skill_names = {s.name for s in ws_skills}
        for s in gl_skills:
            if s.name in ws_skill_names:
                s.is_overridden = True
                s.is_active = False
            else:
                s.is_overridden = False
                target_enabled = is_skill_enabled(gl_cfg, s.name, default=s.is_active)
                self._sync_item_disk_state(s, target_enabled)
                s.is_active = target_enabled

        ws_rule_names = {r.name for r in ws_rules}
        for r in gl_rules:
            if r.name in ws_rule_names:
                r.is_overridden = True
                r.is_active = False
            else:
                r.is_overridden = False
                target_enabled = is_rule_enabled(gl_cfg, r.name, default=r.is_active)
                self._sync_item_disk_state(r, target_enabled)
                r.is_active = target_enabled

        self.skills = ws_skills + gl_skills
        self.rules = ws_rules + gl_rules
        return self.skills, self.rules

    def get_total_active_tokens(self) -> int:
        """Compute honest token counts from active, non-overridden skills and rules."""
        skill_toks = sum(s.tokens for s in self.skills if s.is_active and not s.is_overridden)
        rule_toks = sum(r.tokens for r in self.rules if r.is_active and not r.is_overridden)
        return skill_toks + rule_toks

    def set_item_state(self, item: Union[Skill, Rule], enabled: bool) -> None:
        """Deterministically update active state on disk and persist to scope config.json."""
        # 1. Move on filesystem so Antigravity runtime sees the change
        self._sync_item_disk_state(item, enabled)

        # 2. Persist state in scope config.json
        cfg_path, cfg = load_config_for_scope(item.scope, self.workspace_root, self.home_dir)
        if isinstance(item, Skill):
            set_skill_enabled(cfg, item.name, enabled)
        elif isinstance(item, Rule):
            set_rule_enabled(cfg, item.name, enabled)
        else:
            raise TypeError(f"Unsupported item type for state persistence: {type(item).__name__}")

        write_config(cfg_path, cfg)
        item.is_active = enabled

    def toggle_item(self, item: Union[Skill, Rule]) -> bool:
        """Toggle active state of a skill or rule and persist to disk and config.json."""
        new_state = not item.is_active
        self.set_item_state(item, new_state)
        return item.is_active

    def activate_all(self, items: List[Union[Skill, Rule]]) -> None:
        """Enable all items in the given collection."""
        for item in items:
            self.set_item_state(item, True)

    def deactivate_all(self, items: List[Union[Skill, Rule]]) -> None:
        """Disable all items in the given collection."""
        for item in items:
            self.set_item_state(item, False)

    def find_item(self, name: str, scope: Optional[Scope] = None) -> Optional[Union[Skill, Rule]]:
        """Find a skill or rule by name, prioritizing workspace scope if not specified."""
        for s in self.skills:
            if s.name == name and (scope is None or s.scope == scope):
                return s
        for r in self.rules:
            if (r.name == name or r.path.name == name) and (scope is None or r.scope == scope):
                return r
        return None

    def delete_item(self, item: Union[Skill, Rule]) -> bool:
        """Permanently delete a skill directory or rule file from disk and remove from config.json."""
        import shutil

        # 1. Remove from filesystem
        if isinstance(item, Skill):
            if item.path.exists() and item.path.is_dir():
                shutil.rmtree(item.path)
        elif isinstance(item, Rule):
            if item.path.exists() and item.path.is_file():
                item.path.unlink()

        # 2. Clean up from config.json
        cfg_path, cfg = load_config_for_scope(item.scope, self.workspace_root, self.home_dir)
        section = "skills" if isinstance(item, Skill) else "rules"
        if section in cfg and isinstance(cfg[section], dict) and item.name in cfg[section]:
            del cfg[section][item.name]
            write_config(cfg_path, cfg)

        # 3. Reload active registry
        self.discover_all()
        return True


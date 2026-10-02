import os
import shutil
from typing import Optional, Dict, Tuple, List
from .types import SkillInfo, RuleInfo, SubagentInfo, ScopeContext, ContextBudget
from .catalog import (
    scan_skills_dir,
    load_catalog_map,
    scan_rules_dir,
    scan_subagents_dir,
)

# ANSI formatting
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

class SkillManager:
    def __init__(self, scope: ScopeContext):
        self.scope = scope

    def scan_all(self) -> Tuple[Dict[str, SkillInfo], Dict[str, SkillInfo], Dict[str, SkillInfo], Dict[str, SkillInfo]]:
        workspace_skills = scan_skills_dir(self.scope.workspace_skills_dir, tier="workspace")
        shared_skills = scan_skills_dir(self.scope.shared_skills_dir, tier="shared")
        builtin_skills = scan_skills_dir(self.scope.builtin_skills_dir, tier="builtin")
        catalog_skills = load_catalog_map(self.scope.catalog_dirs)

        active_names = set(workspace_skills.keys()) | set(shared_skills.keys())
        available_catalog = {k: v for k, v in catalog_skills.items() if k not in active_names}

        return workspace_skills, shared_skills, builtin_skills, available_catalog

    def scan_rules(self) -> Tuple[Dict[str, RuleInfo], Dict[str, RuleInfo]]:
        """Returns (active_rules, available_rules)."""
        active_ws = scan_rules_dir(self.scope.workspace_rules_dir, tier="workspace")
        active_global = scan_rules_dir(self.scope.global_rules_dir, tier="global")

        # Global rules are active unless overridden by workspace
        active = {**active_global, **active_ws}

        # Backup / catalog rules if any
        backup_rules_dir = os.path.join(os.path.expanduser("~"), ".agents.backup", "rules")
        catalog_rules = scan_rules_dir(backup_rules_dir, tier="catalog")
        available = {k: v for k, v in catalog_rules.items() if k not in active}

        return active, available

    def scan_subagents(self) -> Tuple[Dict[str, SubagentInfo], Dict[str, SubagentInfo]]:
        """Returns (active_subagents, available_subagents)."""
        active_ws = scan_subagents_dir(self.scope.workspace_agents_dir, tier="workspace")
        active_global = scan_subagents_dir(self.scope.global_agents_subagents_dir, tier="global")
        active = {**active_global, **active_ws}

        backup_agents_dir = os.path.join(os.path.expanduser("~"), ".agents.backup", "agents")
        catalog_agents = scan_subagents_dir(backup_agents_dir, tier="catalog")
        available = {k: v for k, v in catalog_agents.items() if k not in active}

        return active, available

    def calculate_budget(self) -> ContextBudget:
        ws, shared, builtin, _ = self.scan_all()
        rules_active, _ = self.scan_rules()
        subagents_active, _ = self.scan_subagents()

        rules_tok = sum(r.token_cost for r in rules_active.values())
        skills_tok = sum(s.token_cost for s in ws.values()) + sum(s.token_cost for s in shared.values())
        agents_tok = sum(a.token_cost for a in subagents_active.values())

        total = rules_tok + skills_tok + agents_tok
        return ContextBudget(
            rules_tokens=rules_tok,
            skills_tokens=skills_tok,
            subagents_tokens=agents_tok,
            total_tokens=total,
            max_tokens=20000,
        )

    def format_list(self) -> str:
        ws, shared, builtin, catalog = self.scan_all()
        budget = self.calculate_budget()
        total_active = len(ws) + len(shared) + len(builtin)
        total_skills = total_active + len(catalog)

        out = []
        out.append(f"{BOLD}Antigravity Context & Skills Manager{RESET}")
        out.append(f"Context Budget: {budget.total_tokens:,} / {budget.max_tokens:,} tokens ({budget.percentage:.1f}%) "
                   f"[Rules: {budget.rules_tokens:,} · Skills: {budget.skills_tokens:,} · Agents: {budget.subagents_tokens:,}]\n")

        out.append(f"{BOLD}Skills{RESET}: {total_skills} total ({total_active} active · {len(catalog)} in catalog)\n")

        # Workspace Skills
        if ws:
            loc_label = "Workspace config" if self.scope.is_project_detected else "Home dotfiles"
            out.append(f"{BOLD}Workspace skills{RESET} · {DIM}{loc_label}{RESET}")
            for name, info in sorted(ws.items()):
                tag = f"{CYAN}🔗{RESET} " if info.is_symlink else ""
                out.append(f"  {tag}{CYAN}{name}{RESET}: {info.description}")
            out.append("")

        # Shared Skills
        if shared:
            out.append(f"{BOLD}Shared skills{RESET} · {DIM}From {self.scope.shared_skills_dir}{RESET}")
            for name, info in sorted(shared.items()):
                out.append(f"  {CYAN}{name}{RESET}: {info.description}")
            out.append("")

        # Available Catalog
        if catalog:
            out.append(f"{BOLD}Available in Catalog{RESET} · {DIM}Ready to activate ({len(catalog)} skills){RESET}")
            for name, info in sorted(catalog.items()):
                out.append(f"  {DIM}⚪ {name}: {info.description}{RESET}")
            out.append("")

        out.append(f"{DIM}Press 'agy-skills browse' for the full interactive TUI & live budget meter.{RESET}")
        return "\n".join(out)

    def find_skill(self, name: str) -> Optional[SkillInfo]:
        ws, shared, builtin, catalog = self.scan_all()
        return ws.get(name) or shared.get(name) or builtin.get(name) or catalog.get(name)

    def enable(self, name: str, target_tier: str = "workspace", copy_mode: bool = False) -> Tuple[bool, str]:
        catalog_map = load_catalog_map(self.scope.catalog_dirs)
        if name not in catalog_map:
            return False, f"Skill '{name}' not found in catalog."

        src_info = catalog_map[name]
        src_dir = os.path.dirname(src_info.path) if src_info.path.endswith("SKILL.md") else src_info.path

        if target_tier == "global":
            target_base = os.path.join(self.scope.global_agents_dir, "skills")
        elif target_tier == "shared":
            target_base = self.scope.shared_skills_dir
        else:
            target_base = self.scope.workspace_skills_dir

        dest_dir = os.path.join(target_base, name)
        os.makedirs(target_base, exist_ok=True)

        if os.path.exists(dest_dir) or os.path.islink(dest_dir):
            return True, f"Skill '{name}' is already active in {target_tier} ({dest_dir})."

        try:
            if copy_mode:
                shutil.copytree(src_dir, dest_dir, symlinks=True)
                return True, f"✅ Enabled '{name}' in {target_tier} (copied to {dest_dir})"
            else:
                os.symlink(src_dir, dest_dir)
                return True, f"✅ Enabled '{name}' in {target_tier} (symlinked to {dest_dir})"
        except Exception as e:
            return False, f"Failed to enable skill '{name}': {e}"

    def disable(self, name: str, target_tier: Optional[str] = None) -> Tuple[bool, str]:
        candidates = []
        if target_tier == "global":
            candidates.append(os.path.join(self.scope.global_agents_dir, "skills", name))
        elif target_tier == "shared":
            candidates.append(os.path.join(self.scope.shared_skills_dir, name))
        elif target_tier == "workspace":
            candidates.append(os.path.join(self.scope.workspace_skills_dir, name))
        else:
            candidates.extend([
                os.path.join(self.scope.workspace_skills_dir, name),
                os.path.join(self.scope.shared_skills_dir, name),
                os.path.join(self.scope.global_agents_dir, "skills", name),
            ])

        found_path = None
        for p in candidates:
            if os.path.exists(p) or os.path.islink(p):
                found_path = p
                break

        if not found_path:
            return False, f"Skill '{name}' is not currently active."

        try:
            if os.path.islink(found_path):
                os.unlink(found_path)
                return True, f"✅ Disabled '{name}' (safely unlinked from {found_path})"
            else:
                catalog_map = load_catalog_map(self.scope.catalog_dirs)
                if name not in catalog_map:
                    backup_dir = os.path.join(os.path.expanduser("~"), ".agents.backup", "skills", name)
                    shutil.copytree(found_path, backup_dir, dirs_exist_ok=True)
                shutil.rmtree(found_path)
                return True, f"✅ Disabled '{name}' (removed from {found_path})"
        except Exception as e:
            return False, f"Failed to disable skill '{name}': {e}"

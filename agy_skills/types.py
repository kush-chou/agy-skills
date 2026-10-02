from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    tier: str  # "workspace", "shared", "builtin", "catalog"
    is_symlink: bool = False
    is_builtin: bool = False
    lines_count: int = 0
    token_cost: int = 0
    collection: str = "core"  # e.g. "stitch", "android", "mattpocock"

@dataclass
class RuleInfo:
    name: str
    description: str
    path: str
    tier: str  # "workspace", "global", "catalog"
    is_always_on: bool = True
    is_symlink: bool = False
    lines_count: int = 0
    token_cost: int = 0
    collection: str = "core"

@dataclass
class SubagentInfo:
    name: str
    role: str
    description: str
    path: str
    tier: str  # "workspace", "global", "catalog"
    is_symlink: bool = False
    lines_count: int = 0
    token_cost: int = 0
    collection: str = "core"

@dataclass
class ContextBudget:
    rules_tokens: int = 0
    skills_tokens: int = 0
    subagents_tokens: int = 0
    total_tokens: int = 0
    max_tokens: int = 20000

    @property
    def percentage(self) -> float:
        return min(100.0, (self.total_tokens / self.max_tokens) * 100.0)

    @property
    def is_warning(self) -> bool:
        return self.total_tokens > 15000

    @property
    def is_critical(self) -> bool:
        return self.total_tokens >= self.max_tokens

@dataclass
class ScopeContext:
    workspace_root: Optional[str]
    workspace_skills_dir: str
    global_agents_dir: str
    shared_skills_dir: str
    builtin_skills_dir: str
    catalog_dirs: List[str]
    is_project_detected: bool
    workspace_rules_dir: str = ""
    global_rules_dir: str = ""
    workspace_agents_dir: str = ""
    global_agents_subagents_dir: str = ""

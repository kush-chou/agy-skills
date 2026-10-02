from dataclasses import dataclass
from typing import Optional

@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    tier: str  # "workspace", "shared", "builtin", "catalog"
    is_symlink: bool = False
    is_builtin: bool = False
    lines_count: int = 0

@dataclass
class ScopeContext:
    workspace_root: Optional[str]
    workspace_skills_dir: str
    global_agents_dir: str
    shared_skills_dir: str
    builtin_skills_dir: str
    catalog_dirs: list[str]
    is_project_detected: bool

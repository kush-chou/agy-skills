import os
from typing import Optional
from .types import ScopeContext

def find_workspace_root(cwd: Optional[str] = None) -> Optional[str]:
    curr = os.path.abspath(cwd or os.getcwd())
    home = os.path.expanduser("~")

    # If currently in home directory root, no project is active
    if curr == home:
        return None

    while True:
        # Check for git root or .agents directory
        if os.path.isdir(os.path.join(curr, ".git")) or os.path.isdir(os.path.join(curr, ".agents")):
            return curr

        parent = os.path.dirname(curr)
        if parent == curr or curr == home:
            break
        curr = parent

    return None

def resolve_scope(cwd: Optional[str] = None) -> ScopeContext:
    workspace_root = find_workspace_root(cwd)
    home = os.path.expanduser("~")
    global_agents = os.path.join(home, ".agents")

    if workspace_root:
        workspace_skills = os.path.join(workspace_root, ".agents", "skills")
        workspace_rules = os.path.join(workspace_root, ".agents", "rules")
        workspace_agents = os.path.join(workspace_root, ".agents", "agents")
        is_project = True
    else:
        # Fallback when in home or non-repo directory: workspace points to ~/.agents/skills
        workspace_skills = os.path.join(global_agents, "skills")
        workspace_rules = os.path.join(global_agents, "rules")
        workspace_agents = os.path.join(global_agents, "agents")
        is_project = False

    shared_skills = os.path.join(home, ".gemini", "skills")
    global_rules = os.path.join(global_agents, "rules")
    global_subagents = os.path.join(global_agents, "agents")

    builtin_candidates = [
        os.path.join(home, ".gemini", "antigravity", "builtin", "skills"),
        os.path.join(home, ".gemini", "antigravity-cli", "builtin", "skills"),
    ]
    builtin_skills = next((p for p in builtin_candidates if os.path.isdir(p)), builtin_candidates[0])

    catalog_dirs = [
        os.path.join(global_agents, "catalog"),
        os.path.join(home, ".agents.backup", "skills"),
        os.path.join(home, ".cache", "agy-skills", "store"),
    ]

    return ScopeContext(
        workspace_root=workspace_root,
        workspace_skills_dir=workspace_skills,
        global_agents_dir=global_agents,
        shared_skills_dir=shared_skills,
        builtin_skills_dir=builtin_skills,
        catalog_dirs=[d for d in catalog_dirs if os.path.isdir(d)],
        is_project_detected=is_project,
        workspace_rules_dir=workspace_rules,
        global_rules_dir=global_rules,
        workspace_agents_dir=workspace_agents,
        global_agents_subagents_dir=global_subagents,
    )

import sys
import argparse
from .scope import resolve_scope
from .manager import SkillManager
from .viewer import render_skill_view, display_skill_interactive
from .__init__ import __version__

def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="agy-skills",
        description="Fast, modular context package manager for Google Antigravity & Gemini CLI",
    )
    parser.add_argument("-v", "--version", action="version", version=f"agy-skills {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    list_p = subparsers.add_parser("list", help="List all discovered skills across tiers")
    list_p.add_argument("--json", action="store_true", help="Output in JSON format")

    # add / enable
    add_p = subparsers.add_parser("add", aliases=["enable", "install"], help="Enable a skill from the catalog")
    add_p.add_argument("name", help="Name of the skill to enable")
    add_p.add_argument("-g", "--global", dest="is_global", action="store_true", help="Enable into global dotfiles (~/.agents/skills/)")
    add_p.add_argument("-s", "--shared", dest="is_shared", action="store_true", help="Enable into shared user skills (~/.gemini/skills/)")
    add_p.add_argument("--copy", action="store_true", help="Copy directory instead of symlinking")

    # remove / disable
    rm_p = subparsers.add_parser("remove", aliases=["disable", "uninstall"], help="Disable an active skill")
    rm_p.add_argument("name", help="Name of the skill to disable")
    rm_p.add_argument("-g", "--global", dest="is_global", action="store_true", help="Target global scope (~/.agents/skills/)")
    rm_p.add_argument("-s", "--shared", dest="is_shared", action="store_true", help="Target shared scope (~/.gemini/skills/)")

    # show / view
    show_p = subparsers.add_parser("show", aliases=["view", "info"], help="View a skill's runbook and instructions")
    show_p.add_argument("name", help="Name of the skill to view")
    show_p.add_argument("--raw", action="store_true", help="Print raw unformatted markdown")

    # search
    search_p = subparsers.add_parser("search", help="Search skills by keyword")
    search_p.add_argument("query", help="Keyword to search in name or description")

    # status
    status_p = subparsers.add_parser("status", help="Inspect active scope, health, and symlink integrity")

    parsed = parser.parse_args(args)

    if not parsed.command:
        # Default behavior: list skills
        scope = resolve_scope()
        mgr = SkillManager(scope)
        print(mgr.format_list())
        return

    scope = resolve_scope()
    mgr = SkillManager(scope)

    if parsed.command == "list":
        print(mgr.format_list())

    elif parsed.command in ("add", "enable", "install"):
        target_tier = "workspace"
        if getattr(parsed, "is_global", False):
            target_tier = "global"
        elif getattr(parsed, "is_shared", False):
            target_tier = "shared"
        
        ok, msg = mgr.enable(parsed.name, target_tier=target_tier, copy_mode=getattr(parsed, "copy", False))
        print(msg)
        if not ok:
            sys.exit(1)

    elif parsed.command in ("remove", "disable", "uninstall"):
        target_tier = None
        if getattr(parsed, "is_global", False):
            target_tier = "global"
        elif getattr(parsed, "is_shared", False):
            target_tier = "shared"

        ok, msg = mgr.disable(parsed.name, target_tier=target_tier)
        print(msg)
        if not ok:
            sys.exit(1)

    elif parsed.command in ("show", "view", "info"):
        skill = mgr.find_skill(parsed.name)
        if not skill:
            print(f"Error: Skill '{parsed.name}' not found.")
            sys.exit(1)

        if getattr(parsed, "raw", False):
            with open(skill.path, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            display_skill_interactive(skill)

    elif parsed.command == "search":
        q = parsed.query.lower()
        ws, shared, builtin, catalog = mgr.scan_all()
        all_skills = {**ws, **shared, **builtin, **catalog}
        matches = [s for s in all_skills.values() if q in s.name.lower() or q in s.description.lower()]

        print(f"Search results for '{parsed.query}' ({len(matches)} found):")
        for s in sorted(matches, key=lambda x: x.name):
            print(f"  • {s.name} ({s.tier}): {s.description}")

    elif parsed.command == "status":
        print("=== Antigravity Context Scope Status ===")
        print(f"Project Detected: {'Yes' if scope.is_project_detected else 'No'}")
        if scope.workspace_root:
            print(f"Workspace Root:   {scope.workspace_root}")
        print(f"Workspace Skills: {scope.workspace_skills_dir}")
        print(f"Shared Skills:    {scope.shared_skills_dir}")
        print(f"Global Agents:    {scope.global_agents_dir}")
        print(f"Catalog Dirs:     {', '.join(scope.catalog_dirs)}")

if __name__ == "__main__":
    main()

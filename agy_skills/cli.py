import sys
import argparse
from .scope import resolve_scope
from .manager import SkillManager
from .viewer import render_skill_view, display_skill_interactive
from .browse import open_browser
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

    # help
    help_p = subparsers.add_parser("help", help="Show this help message")

    # browse
    browse_p = subparsers.add_parser("browse", aliases=["tui", "ui", "viewer"], help="Launch interactive visual viewer and editor")

    # list
    list_p = subparsers.add_parser("list", help="List all discovered skills across tiers")
    list_p.add_argument("--json", action="store_true", help="Output in JSON format")

    # add / enable
    add_p = subparsers.add_parser("add", aliases=["enable", "install", "activate"], help="Activate a skill into your project")
    add_p.add_argument("name", help="Name of the skill to enable")
    add_p.add_argument("-g", "--global", dest="is_global", action="store_true", help="Enable into global user profile (~/.agents/skills/)")
    add_p.add_argument("-s", "--shared", dest="is_shared", action="store_true", help="Enable into shared user skills (~/.gemini/skills/)")
    add_p.add_argument("--copy", action="store_true", help="Copy directory instead of linking")

    # remove / disable
    rm_p = subparsers.add_parser("remove", aliases=["disable", "uninstall", "deactivate"], help="Deactivate an active skill")
    rm_p.add_argument("name", help="Name of the skill to disable")
    rm_p.add_argument("-g", "--global", dest="is_global", action="store_true", help="Target global user profile")
    rm_p.add_argument("-s", "--shared", dest="is_shared", action="store_true", help="Target shared user profile")

    # show / view
    show_p = subparsers.add_parser("show", aliases=["view", "info"], help="View a skill's runbook and instructions")
    show_p.add_argument("name", help="Name of the skill to view")
    show_p.add_argument("--raw", action="store_true", help="Print raw unformatted markdown")

    # search
    search_p = subparsers.add_parser("search", help="Search skills by keyword")
    search_p.add_argument("query", help="Keyword to search in name or description")

    # status
    status_p = subparsers.add_parser("status", help="Inspect active workspace and health status")

    parsed = parser.parse_args(args)

    if not parsed.command or parsed.command == "help":
        if parsed.command == "help":
            parser.print_help()
            return
        # Default behavior: list skills
        scope = resolve_scope()
        mgr = SkillManager(scope)
        print(mgr.format_list())
        return

    scope = resolve_scope()
    if parsed.command in ("browse", "tui", "ui"):
        open_browser()
        return

    mgr = SkillManager(scope)

    if parsed.command == "list":
        print(mgr.format_list())

    elif parsed.command in ("add", "enable", "install"):
        target_tier = "workspace"
        if getattr(parsed, "is_global", False):
            target_tier = "global"
        elif getattr(parsed, "is_shared", False):
            target_tier = "shared"

        # Check if it's a rule first
        rules_act, rules_avail = mgr.scan_rules()
        if parsed.name in rules_avail or parsed.name in rules_act:
            ok, msg = mgr.enable_rule(parsed.name, target_tier=target_tier)
            print(msg)
            if not ok:
                sys.exit(1)
            return

        # Check if it's a subagent
        agents_act, agents_avail = mgr.scan_subagents()
        if parsed.name in agents_avail or parsed.name in agents_act:
            ok, msg = mgr.enable_subagent(parsed.name, target_tier=target_tier)
            print(msg)
            if not ok:
                sys.exit(1)
            return

        # Default to skill
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

        # Check if active rule
        rules_act, _ = mgr.scan_rules()
        if parsed.name in rules_act:
            ok, msg = mgr.disable_rule(parsed.name, target_tier=target_tier)
            print(msg)
            if not ok:
                sys.exit(1)
            return

        # Check if active subagent
        agents_act, _ = mgr.scan_subagents()
        if parsed.name in agents_act:
            ok, msg = mgr.disable_subagent(parsed.name, target_tier=target_tier)
            print(msg)
            if not ok:
                sys.exit(1)
            return

        # Default to skill
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

        if not matches:
            print(f"No skills found matching '{parsed.query}'.")
            print("Tip: Run 'agy-skills list' to browse all available skills, or 'agy-skills browse' for visual search.")
            return

        print(f"Found {len(matches)} matching skill{'s' if len(matches) > 1 else ''}:")
        for s in sorted(matches, key=lambda x: x.name):
            status_tag = "● Active" if s.tier in ("workspace", "shared", "builtin") else "○ Available"
            print(f"  {status_tag} {s.name} ({s.tier})")
            print(f"    {s.description[:90]}{'...' if len(s.description) > 90 else ''}")
        print("\n👉 To activate any skill: agy-skills add <name>")

    elif parsed.command == "status":
        ws, shared, builtin, _ = mgr.scan_all()
        budget = mgr.calculate_budget()
        print("=== Antigravity Environment Health ===")
        print(f"Project Workspace: {'Connected (' + scope.workspace_root + ')' if scope.is_project_detected else 'Global Profile (No local project)'}")
        print(f"Active Skills:     {len(ws)} project · {len(shared)} user profile · {len(builtin)} built-in")
        print(f"AI Prompt Memory:  {budget.total_tokens:,} / {budget.max_tokens:,} tokens ({budget.percentage:.1f}% used) [Healthy]")
        print("Status:            ✅ All skills and rules linked cleanly with zero errors.")
        print("\nTip: Run 'agy-skills browse' to visually configure active skills.")

if __name__ == "__main__":
    main()

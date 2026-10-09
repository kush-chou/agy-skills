"""Main entrypoint for agy-skills CLI and TUI."""

import argparse
from pathlib import Path
import sys

from .cli import (
    manage_plugin_cli,
    print_info,
    print_lint,
    print_list,
    print_search,
    print_tokens,
    run_install,
    toggle_plugin_component_cli,
)
from .discovery import CustomizationRegistry
from .models import Scope
from .tui.app import SkillManagerTUI


def main() -> None:
    # Top-level parser
    parser = argparse.ArgumentParser(
        prog="agy-skills",
        description="Keyboard-first CLI and TUI counterpart to the Antigravity IDE Customizations menu.",
    )
    parser.add_argument(
        "-w", "--workspace",
        type=Path,
        default=None,
        help="Specify workspace root directory (defaults to current repository root).",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all discovered skills, rules, subagents, plugins, and MCP servers.",
    )
    parser.add_argument(
        "-v", "--lint",
        action="store_true",
        help="Run Antigravity compliance checks against all customizations.",
    )
    parser.add_argument(
        "--info",
        metavar="NAME",
        help="Print detailed information for a specific skill, rule, subagent, plugin, or MCP server.",
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Audit active context window usage against the 20,000 token limit.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # list subcommand
    subparsers.add_parser("list", help="List all customizations non-interactively.")

    # tokens subcommand
    subparsers.add_parser("tokens", help="Audit active context window token consumption.")

    # lint subcommand
    subparsers.add_parser("lint", help="Lint all customizations for Antigravity standard compliance.")

    # info / inspect subcommand
    sub_info = subparsers.add_parser("info", help="Inspect a specific customization or plugin in detail.")
    sub_info.add_argument("name", help="Name of skill, rule, plugin, or MCP server.")

    sub_inspect = subparsers.add_parser("inspect", help="Alias for 'info' - inspect customization details.")
    sub_inspect.add_argument("name", help="Name of skill, rule, plugin, or MCP server.")

    # toggle subcommand (granular power feature)
    sub_toggle = subparsers.add_parser("toggle", help="Toggle a plugin or cherry-pick individual subcomponents.")
    sub_toggle.add_argument("name", help="Plugin name or customization name.")
    sub_toggle.add_argument("--sub", "--component", dest="component", default=None, help="Specific subcomponent to toggle.")

    # search subcommand
    sub_search = subparsers.add_parser("search", help="Search the curated agent skill marketplace.")
    sub_search.add_argument("query", nargs="?", default="", help="Search query (e.g. 'supabase', 'review').")

    # install subcommand
    sub_install = subparsers.add_parser("install", help="Turnkey install a skill pack from the marketplace.")
    sub_install.add_argument("pack", help="Name of the skill pack to install (e.g. 'superpowers', 'ui-ux-pro-max').")
    sub_install.add_argument(
        "--global", "-g",
        dest="is_global",
        action="store_true",
        help="Install into global scope (~/.gemini/config/skills) instead of workspace.",
    )

    # plugin subcommand
    sub_plugin = subparsers.add_parser("plugin", help="Manage installed Antigravity plugins live via Language Server.")
    sub_plugin.add_argument("name", help="Plugin name or directory.")
    sub_plugin.add_argument(
        "action",
        nargs="?",
        default="toggle",
        choices=["toggle", "enable", "disable"],
        help="Action to perform (default: toggle).",
    )

    # mcp subcommand
    sub_mcp = subparsers.add_parser("mcp", help="List or inspect Antigravity MCP servers.")
    sub_mcp.add_argument("server_name", nargs="?", default=None, help="MCP server name to inspect.")

    args = parser.parse_args()

    registry = CustomizationRegistry(workspace_root=args.workspace)

    # Command dispatch
    if args.command == "search":
        print_search(args.query, registry.workspace_root, registry.home_dir)
    elif args.command == "install":
        scope = Scope.GLOBAL if args.is_global else Scope.WORKSPACE
        sys.exit(run_install(args.pack, scope, registry.workspace_root, registry.home_dir))
    elif args.command == "plugin":
        sys.exit(manage_plugin_cli(registry, args.name, args.action))
    elif args.command == "toggle":
        if args.component:
            sys.exit(toggle_plugin_component_cli(registry, args.name, args.component))
        else:
            sys.exit(manage_plugin_cli(registry, args.name, "toggle"))
    elif args.command == "tokens" or args.tokens:
        print_tokens(registry)
    elif args.command == "mcp":
        if args.server_name:
            print_info(registry, args.server_name)
        else:
            registry.discover_all()
            print(f"\n=== Antigravity MCP Servers ({len(registry.mcp_servers)} found) ===")
            for m in registry.mcp_servers:
                status = "● active" if m.is_active else "○ disabled"
                print(f"  • {m.name:<26} [{m.tools_count} tools]  {status:<10} ({m.path})")
            print("")
    elif args.command == "lint" or args.lint:
        sys.exit(print_lint(registry))
    elif args.command in ("info", "inspect") or args.info:
        target = args.name if args.command in ("info", "inspect") else args.info
        print_info(registry, target)
    elif args.command == "list" or args.list:
        print_list(registry)
    else:
        app = SkillManagerTUI(registry)
        app.run()


if __name__ == "__main__":
    main()

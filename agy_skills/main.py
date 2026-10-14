"""Main entrypoint for agy-skills CLI and TUI."""

import argparse
from pathlib import Path
import sys
from typing import Optional

from .cli import (
    cli_disable,
    cli_enable,
    cli_info,
    cli_lint,
    cli_list,
    cli_status,
)
from .discovery import CustomizationRegistry
from .models import Scope
from .tui.app import SkillManagerTUI


def _resolve_scope(scope_str: Optional[str], is_workspace: bool = False, is_global: bool = False) -> Optional[Scope]:
    """Resolve scope from argument string or flag booleans."""
    if is_workspace or scope_str == "workspace":
        return Scope.WORKSPACE
    if is_global or scope_str == "global":
        return Scope.GLOBAL
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agy-skills",
        description="Lean & Trustworthy Antigravity Skills & Rules Manager across Workspace and Global scopes.",
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
        help="List all discovered skills and rules non-interactively.",
    )
    parser.add_argument(
        "-s", "--status",
        action="store_true",
        help="Display Antigravity token gauge and compliance status.",
    )
    parser.add_argument(
        "-v", "--lint",
        action="store_true",
        help="Validate all skills and rules against Antigravity specifications.",
    )
    parser.add_argument(
        "--info",
        metavar="NAME",
        help="Print detailed information for a specific skill or rule.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # list subcommand
    sub_list = subparsers.add_parser("list", help="List discovered skills and rules.")
    sub_list.add_argument(
        "--scope",
        choices=["workspace", "global"],
        default=None,
        help="Filter items by scope (workspace or global).",
    )
    sub_list.add_argument("-w", "--workspace", dest="is_workspace", action="store_true", help="List workspace items.")
    sub_list.add_argument("-g", "--global", dest="is_global", action="store_true", help="List global items.")
    sub_list.add_argument("--json", action="store_true", help="Output as JSON.")

    # status subcommand
    sub_status = subparsers.add_parser("status", help="Print context token gauge and compliance audit.")
    sub_status.add_argument("--json", action="store_true", help="Output as JSON.")

    # enable subcommand
    sub_enable = subparsers.add_parser("enable", help="Enable a skill or rule.")
    sub_enable.add_argument("name", help="Name of skill or rule to enable.")
    sub_enable.add_argument(
        "--scope",
        choices=["workspace", "global"],
        default=None,
        help="Target scope explicitly.",
    )
    sub_enable.add_argument("-w", "--workspace", dest="is_workspace", action="store_true", help="Target workspace scope.")
    sub_enable.add_argument("-g", "--global", dest="is_global", action="store_true", help="Target global scope.")

    # disable subcommand
    sub_disable = subparsers.add_parser("disable", help="Disable a skill or rule.")
    sub_disable.add_argument("name", help="Name of skill or rule to disable.")
    sub_disable.add_argument(
        "--scope",
        choices=["workspace", "global"],
        default=None,
        help="Target scope explicitly.",
    )
    sub_disable.add_argument("-w", "--workspace", dest="is_workspace", action="store_true", help="Target workspace scope.")
    sub_disable.add_argument("-g", "--global", dest="is_global", action="store_true", help="Target global scope.")

    # info subcommand
    sub_info = subparsers.add_parser("info", help="Inspect a specific skill or rule.")
    sub_info.add_argument("name", help="Name of skill or rule to inspect.")
    sub_info.add_argument("--json", action="store_true", help="Output as JSON.")

    # lint subcommand
    subparsers.add_parser("lint", help="Validate all skills and rules.")

    args = parser.parse_args()

    try:
        registry = CustomizationRegistry(workspace_root=args.workspace)

        as_json = getattr(args, "json", False)

        if args.command == "list" or args.list:
            sc_str = getattr(args, "scope", None)
            is_ws = getattr(args, "is_workspace", False)
            is_gl = getattr(args, "is_global", False)
            scope = _resolve_scope(sc_str, is_workspace=is_ws, is_global=is_gl)
            sys.exit(cli_list(registry, scope=scope, as_json=as_json))

        elif args.command == "status" or args.status:
            sys.exit(cli_status(registry, as_json=as_json))

        elif args.command == "enable":
            sc_str = getattr(args, "scope", None)
            is_ws = getattr(args, "is_workspace", False)
            is_gl = getattr(args, "is_global", False)
            scope = _resolve_scope(sc_str, is_workspace=is_ws, is_global=is_gl)
            sys.exit(cli_enable(registry, args.name, scope=scope))

        elif args.command == "disable":
            sc_str = getattr(args, "scope", None)
            is_ws = getattr(args, "is_workspace", False)
            is_gl = getattr(args, "is_global", False)
            scope = _resolve_scope(sc_str, is_workspace=is_ws, is_global=is_gl)
            sys.exit(cli_disable(registry, args.name, scope=scope))

        elif args.command == "info" or args.info:
            target = args.name if args.command == "info" else args.info
            sys.exit(cli_info(registry, target, as_json=as_json))

        elif args.command == "lint" or args.lint:
            sys.exit(cli_lint(registry))

        else:
            # Launch 2-pane TUI when no subcommand or action flag is given
            app = SkillManagerTUI(registry)
            app.run()

    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

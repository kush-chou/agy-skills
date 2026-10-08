"""Main entrypoint for agy-skills."""

import argparse
from pathlib import Path
import sys

from .cli import print_info, print_lint, print_list
from .discovery import CustomizationRegistry
from .tui.app import SkillManagerTUI


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agy-skills",
        description="Curses-based Antigravity Skills & Rules Manager across Global and Workspace scopes.",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all discovered skills and rules non-interactively.",
    )
    parser.add_argument(
        "-v", "--lint",
        action="store_true",
        help="Run Antigravity compliance checks against all skills and rules.",
    )
    parser.add_argument(
        "--info",
        metavar="NAME",
        help="Print detailed information for a specific skill or rule.",
    )
    parser.add_argument(
        "-w", "--workspace",
        type=Path,
        default=None,
        help="Specify workspace root directory (defaults to current repository root).",
    )

    args = parser.parse_args()

    registry = CustomizationRegistry(workspace_root=args.workspace)

    if args.lint:
        sys.exit(print_lint(registry))
    elif args.info:
        print_info(registry, args.info)
    elif args.list:
        print_list(registry)
    else:
        app = SkillManagerTUI(registry)
        app.run()


if __name__ == "__main__":
    main()

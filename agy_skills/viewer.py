import os
import sys
import shutil
from typing import Optional
from .types import SkillInfo

# ANSI Color codes
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def format_skill_header(info: SkillInfo) -> str:
    lines = [
        f"{BOLD}{info.name}{RESET}",
        f"{info.description}",
        f"{DIM}{info.path}{RESET}",
        "",
    ]
    return "\n".join(lines)

def highlight_markdown_line(line: str) -> str:
    if line.startswith("#"):
        return f"{MAGENTA}{BOLD}{line}{RESET}"
    if line.startswith("- ") or line.startswith("* "):
        return f"{CYAN}•{RESET} {line[2:]}"
    if line.strip().startswith("```"):
        return f"{DIM}{line}{RESET}"
    return line

def render_skill_view(info: SkillInfo, max_lines: Optional[int] = None) -> str:
    header = format_skill_header(info)
    body_lines = []

    try:
        with open(info.path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.read().splitlines()

        # Skip YAML frontmatter for display if present
        start_idx = 0
        if raw_lines and raw_lines[0].strip() == "---":
            for i in range(1, len(raw_lines)):
                if raw_lines[i].strip() == "---":
                    start_idx = i + 1
                    break

        content_lines = raw_lines[start_idx:]
        total_lines = len(content_lines)

        displayed_lines = content_lines
        if max_lines and max_lines < total_lines:
            displayed_lines = content_lines[:max_lines]

        for line in displayed_lines:
            body_lines.append(f"  {highlight_markdown_line(line)}")

        footer = f"\n{DIM}(1-{len(displayed_lines)} of {total_lines} lines){RESET}"
        nav_bar = f"\n{DIM}↑/↓ scroll · pgup/pgdown page · ctrl+end bottom · ctrl+home top · esc back{RESET}"

        return header + "\n".join(body_lines) + footer + nav_bar
    except Exception as e:
        return f"Error reading skill at {info.path}: {e}"

def display_skill_interactive(info: SkillInfo):
    """
    Displays the skill view. If interactive TTY, pages via less or terminal pager.
    """
    view_text = render_skill_view(info)

    if sys.stdout.isatty():
        # Clean terminal output or pager
        pager = os.environ.get("PAGER")
        if pager and shutil.which(pager):
            import subprocess
            try:
                proc = subprocess.Popen([pager], stdin=subprocess.PIPE, text=True)
                proc.communicate(view_text)
                return
            except Exception:
                pass

    print(view_text)

"""Curses-based 2-pane split-view TUI for Antigravity skills and rules."""

import curses
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
from typing import Any, List, Optional, Tuple, Union

from ..discovery import CustomizationRegistry
from ..models import Rule, Scope, Skill, Subagent


class SkillManagerTUI:
    """Lean 2-pane TUI for managing Antigravity skills, rules, and subagents with real-time budget meter."""

    def __init__(self, registry: CustomizationRegistry):
        self.registry = registry
        self.skills: List[Skill] = []
        self.rules: List[Rule] = []
        self.subagents: List[Subagent] = []

        self.selected_index: int = 0
        self.scroll_offset: int = 0
        self.detail_scroll: int = 0

        self.filter_text: str = ""
        self.is_filtering: bool = False
        self.filter_buffer: str = ""

        # Scope filter: "ALL", "WORKSPACE", "GLOBAL"
        self.scope_filter: str = "ALL"
        self.has_colors: bool = False
        self.status_message: str = ""

    def refresh_data(self) -> None:
        """Reload skills, rules, and subagents from filesystem and configuration."""
        self.skills, self.rules = self.registry.discover_all()
        self.subagents = self.registry.subagents

    @property
    def target_scope(self) -> Scope:
        if self.scope_filter == "GLOBAL":
            return Scope.GLOBAL
        return Scope.WORKSPACE

    def _init_colors(self) -> None:
        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)   # Active / Valid
                curses.init_pair(2, curses.COLOR_CYAN, -1)    # Section Header / Scope
                curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Warning / Overridden
                curses.init_pair(4, curses.COLOR_RED, -1)     # Error / Invalid
                curses.init_pair(5, curses.COLOR_WHITE, -1)   # Dim / Default
                curses.init_pair(6, curses.COLOR_MAGENTA, -1) # Title / Accents
                self.has_colors = True
            except Exception:
                self.has_colors = False

    def _color(self, pair_idx: int, extra: int = 0) -> int:
        if self.has_colors:
            try:
                return curses.color_pair(pair_idx) | extra
            except Exception:
                return extra
        return extra

    def _safe_addstr(self, stdscr: Any, y: int, x: int, text: str, attr: int = 0) -> None:
        try:
            max_y, max_x = stdscr.getmaxyx()
            if y < 0 or y >= max_y or x < 0 or x >= max_x:
                return
            avail = max_x - x
            if len(text) > avail:
                text = text[:avail]
            if not text:
                return
            stdscr.addstr(y, x, text, attr)
        except Exception:
            pass

    def get_current_items_grouped(self) -> List[Tuple[str, List[Union[Skill, Rule, Subagent]]]]:
        """Return categorized sections of skills, rules, and subagents according to active scope and filter."""
        query = self.filter_text.strip().lower()

        def match_filter(item: Union[Skill, Rule, Subagent]) -> bool:
            if not query:
                return True
            name = item.name.lower()
            desc = item.description.lower()
            return query in name or query in desc

        ws_skills = [s for s in self.skills if s.scope == Scope.WORKSPACE and match_filter(s)]
        ws_rules = [r for r in self.rules if r.scope == Scope.WORKSPACE and match_filter(r)]
        ws_subagents = [a for a in self.subagents if a.scope == Scope.WORKSPACE and match_filter(a)]
        gl_skills = [s for s in self.skills if s.scope == Scope.GLOBAL and match_filter(s)]
        gl_rules = [r for r in self.rules if r.scope == Scope.GLOBAL and match_filter(r)]
        gl_subagents = [a for a in self.subagents if a.scope == Scope.GLOBAL and match_filter(a)]

        sections: List[Tuple[str, List[Union[Skill, Rule, Subagent]]]] = []
        if self.scope_filter in ("ALL", "WORKSPACE"):
            if ws_skills:
                sections.append((f"WORKSPACE SKILLS ({len(ws_skills)})", ws_skills))
            if ws_rules:
                sections.append((f"WORKSPACE RULES ({len(ws_rules)})", ws_rules))
            if ws_subagents:
                sections.append((f"WORKSPACE SUBAGENTS ({len(ws_subagents)})", ws_subagents))

        if self.scope_filter in ("ALL", "GLOBAL"):
            if gl_skills:
                sections.append((f"GLOBAL SKILLS ({len(gl_skills)})", gl_skills))
            if gl_rules:
                sections.append((f"GLOBAL RULES ({len(gl_rules)})", gl_rules))
            if gl_subagents:
                sections.append((f"GLOBAL SUBAGENTS ({len(gl_subagents)})", gl_subagents))

        return sections

    def get_flattened_selectable_items(self) -> List[Union[Skill, Rule, Subagent]]:
        """Return flat list of all currently visible items across groups."""
        items: List[Union[Skill, Rule, Subagent]] = []
        for _, group_items in self.get_current_items_grouped():
            items.extend(group_items)
        return items

    @property
    def selected_item(self) -> Optional[Union[Skill, Rule, Subagent]]:
        items = self.get_flattened_selectable_items()
        if not items:
            return None
        self.selected_index = max(0, min(len(items) - 1, self.selected_index))
        return items[self.selected_index]

    def _render_markdown(self, text: str, width: int) -> List[Tuple[str, int]]:
        """Clean markdown renderer converting headers, bullets, and blocks into wrapped terminal lines."""
        lines: List[Tuple[str, int]] = []
        in_code_block = False

        for raw_line in text.splitlines():
            line = raw_line.rstrip()

            # Code fence toggle
            if line.startswith("```"):
                if not in_code_block:
                    lang = line[3:].strip() or "code"
                    lines.append((f"┌─ [ {lang} ]" + "─" * max(0, width - len(lang) - 8), self._color(2)))
                    in_code_block = True
                else:
                    lines.append(("└" + "─" * max(0, width - 2), self._color(2)))
                    in_code_block = False
                continue

            if in_code_block:
                lines.append((f"│ {line[:max(0, width - 4)]}", self._color(5)))
                continue

            # Empty lines
            if not line.strip():
                lines.append(("", 0))
                continue

            # Headings
            if line.startswith("# "):
                title = line[2:].strip()
                lines.append((f"◆ {title}", self._color(2, curses.A_BOLD)))
                continue
            if line.startswith("## "):
                title = line[3:].strip()
                lines.append((f"▸ {title}", self._color(2, curses.A_BOLD)))
                continue
            if line.startswith("### "):
                title = line[4:].strip()
                lines.append((f"▪ {title}", self._color(2)))
                continue

            # Table rows (must contain multiple pipes and be aligned)
            if line.startswith("|") and line.endswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if all(re.match(r"^:?-+:?$", c) for c in cells):
                    sep = "─┼─".join("─" * max(4, len(c)) for c in cells)
                    lines.append((f"─{sep}─", self._color(5)))
                    continue
                clean_cells = [re.sub(r"[*`]", "", c) for c in cells]
                table_row = " │ ".join(clean_cells)
                lines.append((table_row, self._color(5)))
                continue

            # Bullet points
            bullet_match = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
            if bullet_match:
                indent = len(bullet_match.group(1))
                content = re.sub(r"[*`]", "", bullet_match.group(2))
                wrapped = textwrap.wrap(content, width=max(10, width - indent - 4))
                if wrapped:
                    lines.append((" " * indent + f"• {wrapped[0]}", self._color(5)))
                    for extra in wrapped[1:]:
                        lines.append((" " * (indent + 2) + extra, self._color(5)))
                continue

            # Standard paragraph
            clean_text = re.sub(r"[*`]", "", line)
            wrapped = textwrap.wrap(clean_text, width=max(10, width - 2))
            for part in wrapped:
                lines.append((part, self._color(5)))

        if in_code_block:
            lines.append(("└" + "─" * max(0, width - 2), self._color(2)))

        return lines

    def _draw_top_banner(self, stdscr: Any, max_x: int) -> None:
        title = " agy-skills "
        scope_badge = f" [SCOPE: {self.scope_filter}] "
        filter_badge = f" [FILTER: {self.filter_text}] " if self.filter_text else ""

        banner_left = f"{title}{scope_badge}{filter_badge}"
        active_tok = self.registry.get_total_active_tokens()
        budget = self.registry.token_budget
        pct = (active_tok / budget) * 100.0 if budget > 0 else 0.0
        banner_right = f"Context: {active_tok:,}/{budget:,} tok ({pct:.1f}%) "

        total_needed = len(banner_left) + len(banner_right)
        if total_needed > max_x - 1:
            banner_left = banner_left[:max(0, max_x - len(banner_right) - 2)]

        filler_len = max(0, max_x - len(banner_left) - len(banner_right) - 1)
        full_banner = banner_left + (" " * filler_len) + banner_right
        self._safe_addstr(stdscr, 0, 0, full_banner[:max_x - 1], self._color(6, curses.A_REVERSE | curses.A_BOLD))

    def _draw_split_view(self, stdscr: Any, max_y: int, max_x: int) -> None:
        top_y = 1
        bottom_y = max_y - 3
        content_h = max(1, bottom_y - top_y + 1)

        left_w = max(28, min(int(max_x * 0.42), 48))
        right_w = max(10, max_x - left_w - 1)

        # Draw vertical divider
        for y in range(top_y, bottom_y + 1):
            self._safe_addstr(stdscr, y, left_w, "│", self._color(5, curses.A_DIM))

        grouped = self.get_current_items_grouped()
        flat_items = self.get_flattened_selectable_items()

        # Left Pane - List items
        row_y = top_y
        flat_idx = 0

        if not flat_items:
            self._safe_addstr(stdscr, top_y + 1, 2, "(No matching skills, rules, or subagents)", self._color(5, curses.A_DIM))
        else:
            # Build list rows with group headers
            display_rows: List[Tuple[bool, str, Optional[Union[Skill, Rule, Subagent]], int]] = []
            for title, items in grouped:
                display_rows.append((True, title, None, -1))
                for itm in items:
                    display_rows.append((False, "", itm, flat_idx))
                    flat_idx += 1

            # Adjust scroll offset so selected_index is visible
            selected_row_idx = 0
            for idx, (_, _, itm, f_idx) in enumerate(display_rows):
                if f_idx == self.selected_index:
                    selected_row_idx = idx
                    break

            if selected_row_idx < self.scroll_offset:
                self.scroll_offset = selected_row_idx
            elif selected_row_idx >= self.scroll_offset + content_h:
                self.scroll_offset = selected_row_idx - content_h + 1

            visible_rows = display_rows[self.scroll_offset : self.scroll_offset + content_h]
            for is_header, header_title, item, f_idx in visible_rows:
                if row_y > bottom_y:
                    break

                if is_header:
                    self._safe_addstr(stdscr, row_y, 1, f" {header_title}", self._color(2, curses.A_BOLD))
                elif item is not None:
                    is_selected = (f_idx == self.selected_index)
                    badge = "●" if item.is_active else "○"
                    tok_str = f"~{item.tokens}t"

                    # Name truncated to fit left pane
                    avail_name = max(6, left_w - len(tok_str) - 8)
                    display_name = item.name[:avail_name]
                    padding = " " * max(1, left_w - 6 - len(display_name) - len(tok_str))

                    line_text = f" {badge} {display_name}{padding}{tok_str} "
                    if is_selected:
                        attr = self._color(1 if item.is_active else 5, curses.A_REVERSE | curses.A_BOLD)
                    else:
                        attr = self._color(1 if item.is_active else 5)
                        if item.is_overridden:
                            attr = self._color(3, curses.A_DIM)

                    self._safe_addstr(stdscr, row_y, 1, line_text[:left_w - 1], attr)

                row_y += 1

        # Right Pane - Inspector view
        sel = self.selected_item
        inspect_x = left_w + 2
        inspect_w = right_w - 3

        if sel is None:
            self._safe_addstr(stdscr, top_y + 1, inspect_x, "Select a skill, rule, or subagent from the list to inspect.", self._color(5, curses.A_DIM))
            return

        # Header card
        card_y = top_y
        if isinstance(sel, Skill):
            kind = "SKILL"
        elif isinstance(sel, Subagent):
            kind = "SUBAGENT"
        else:
            kind = "RULE"

        status_text = "Active" if sel.is_active else "Disabled"
        if sel.is_overridden:
            status_text += " (Overridden by workspace)"

        self._safe_addstr(stdscr, card_y, inspect_x, f"{kind}: {sel.name}", self._color(2, curses.A_BOLD))
        card_y += 1

        scope_str = f"Scope:  {sel.scope.value.upper()}"
        stat_str = f"Status: {status_text}"
        self._safe_addstr(stdscr, card_y, inspect_x, f"{scope_str:<24} {stat_str}", self._color(5))
        card_y += 1

        tok_str = f"Tokens: ~{sel.tokens:,} tok"
        if isinstance(sel, Rule):
            size_str = f"Size: {sel.size_bytes:,} B ({sel.size_bytes / 1024:.1f} KB)"
            self._safe_addstr(stdscr, card_y, inspect_x, f"{tok_str:<24} {size_str}", self._color(5))
        elif isinstance(sel, Subagent):
            model_str = f"Model: {sel.model}"
            self._safe_addstr(stdscr, card_y, inspect_x, f"{tok_str:<24} {model_str}", self._color(5))
        else:
            self._safe_addstr(stdscr, card_y, inspect_x, tok_str, self._color(5))
        card_y += 1

        target_path = sel.skill_file if isinstance(sel, Skill) else sel.path
        self._safe_addstr(stdscr, card_y, inspect_x, f"Path:   {str(target_path)[:inspect_w - 8]}", self._color(5, curses.A_DIM))
        card_y += 1

        if not sel.is_valid:
            err_msg = "; ".join(sel.validation_errors)
            self._safe_addstr(stdscr, card_y, inspect_x, f"Compliance: ✖ {err_msg[:inspect_w - 14]}", self._color(4, curses.A_BOLD))
            card_y += 1

        # Divider between header card and body
        self._safe_addstr(stdscr, card_y, inspect_x, "─" * max(4, inspect_w - 2), self._color(5, curses.A_DIM))
        card_y += 1

        # Render detail markdown body
        content_to_render = ""
        if isinstance(sel, Skill):
            content_to_render = f"### Description\n{sel.description}\n\n"
            if sel.body:
                content_to_render += f"### Documentation\n{sel.body}"
        elif isinstance(sel, Subagent):
            content_to_render = f"### Description\n{sel.description}\n\n"
            if sel.tools:
                content_to_render += "### Tools\n" + "\n".join(f"- `{t}`" for t in sel.tools) + "\n\n"
            if sel.body:
                content_to_render += f"### Instructions\n{sel.body}"
        else:
            content_to_render = sel.raw_content

        rendered_lines = self._render_markdown(content_to_render, inspect_w)
        avail_detail_lines = max(1, bottom_y - card_y + 1)

        # Clamp detail scroll
        max_scroll = max(0, len(rendered_lines) - avail_detail_lines)
        self.detail_scroll = max(0, min(max_scroll, self.detail_scroll))

        visible_detail = rendered_lines[self.detail_scroll : self.detail_scroll + avail_detail_lines]
        for idx, (d_line, d_attr) in enumerate(visible_detail):
            self._safe_addstr(stdscr, card_y + idx, inspect_x, d_line[:inspect_w], d_attr)

    def _get_footer_text(self, max_x: int) -> str:
        """Return responsive shortcut hint bar that strictly fits within terminal width."""
        candidates = [
            "[Space] Toggle  [x] Delete  [Tab] Scope  [e] Edit  [/] Filter  [d/u] Scroll  [q] Quit",
            "[Space] Toggle  [x] Delete  [Tab] Scope  [e] Edit  [/] Filter  [q] Quit",
            "[Space] Toggle  [x] Delete  [Tab] Scope  [/] Filter  [q] Quit",
            "[Space] Tog  [x] Del  [Tab] Scp  [/] Filter  [q] Quit",
            "[Space] Tog  [x] Del  [/] Filter  [q] Quit",
            "[/] Filter  [q] Quit",
            "[q] Quit",
        ]
        for c in candidates:
            if len(c) <= max_x - 1:
                return c
        return "[q]"[:max(0, max_x - 1)]

    def _draw_bottom_bar(self, stdscr: Any, max_y: int, max_x: int) -> None:
        meter_y = max_y - 2
        hint_y = max_y - 1

        active_tok = self.registry.get_total_active_tokens()
        budget = self.registry.token_budget
        pct = (active_tok / budget) * 100.0 if budget > 0 else 0.0

        bar_len = max(6, min(24, max_x - 45))
        filled = min(bar_len, max(0, int(round((active_tok / budget) * bar_len)))) if budget > 0 else 0
        bar = "▓" * filled + "░" * (bar_len - filled)

        gauge_text = f"Context: [{bar}] {active_tok:,} / {budget:,} tok ({pct:.1f}%)"
        self._safe_addstr(stdscr, meter_y, 1, gauge_text[:max_x - 2], self._color(1 if pct <= 100 else 4, curses.A_BOLD))

        if self.is_filtering:
            prompt = f"Filter: {self.filter_buffer}█ (Enter to apply, Esc to cancel)"
            self._safe_addstr(stdscr, hint_y, 1, prompt[:max_x - 2], self._color(2, curses.A_BOLD))
        elif self.status_message:
            self._safe_addstr(stdscr, hint_y, 1, self.status_message[:max_x - 2], self._color(3, curses.A_BOLD))
            self.status_message = ""
        else:
            footer = self._get_footer_text(max_x)
            self._safe_addstr(stdscr, hint_y, 1, footer[:max_x - 2], self._color(5, curses.A_DIM))

    def _cycle_scope(self) -> None:
        """Cycle scope filter: ALL -> WORKSPACE -> GLOBAL -> ALL."""
        cycle = {"ALL": "WORKSPACE", "WORKSPACE": "GLOBAL", "GLOBAL": "ALL"}
        self.scope_filter = cycle.get(self.scope_filter, "ALL")
        self.selected_index = 0
        self.scroll_offset = 0
        self.detail_scroll = 0

    def _open_editor(self, stdscr: Any) -> None:
        """Suspend curses, open the selected file in $EDITOR, restore curses upon exit."""
        item = self.selected_item
        if not item:
            return

        file_to_edit = item.skill_file if isinstance(item, Skill) else item.path
        if not file_to_edit.exists():
            return

        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
        curses.endwin()
        try:
            subprocess.call([editor, str(file_to_edit)])
        except Exception as exc:
            print(f"Error launching editor '{editor}': {exc}", file=sys.stderr)
        finally:
            stdscr.clear()
            curses.doupdate()
            self.refresh_data()

    def _delete_selected_item(self, stdscr: Any) -> None:
        """Prompt confirmation and delete the currently selected item."""
        item = self.selected_item
        if not item:
            return

        max_y, max_x = stdscr.getmaxyx()
        prompt_y = max_y - 1
        prompt = f"Delete '{item.name}' ({item.scope.value}) from disk? [y/N]: "
        self._safe_addstr(stdscr, prompt_y, 1, prompt[:max_x - 2], self._color(4, curses.A_BOLD))
        stdscr.refresh()

        try:
            ch = stdscr.getch()
        except KeyboardInterrupt:
            return

        if ch in (ord("y"), ord("Y")):
            try:
                name = item.name
                self.registry.delete_item(item)
                self.refresh_data()
                flat = self.get_flattened_selectable_items()
                self.selected_index = max(0, min(len(flat) - 1, self.selected_index))
                self.detail_scroll = 0
                self.status_message = f"✔ Deleted '{name}' from disk."
            except Exception as exc:
                self.status_message = f"Error deleting: {exc}"
        else:
            self.status_message = "Deletion canceled."

    def run_curses(self, stdscr: Any) -> None:
        """Main event loop for curses application."""
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        self._init_colors()
        self.refresh_data()

        while True:
            stdscr.clear()
            max_y, max_x = stdscr.getmaxyx()

            if max_y < 8 or max_x < 30:
                self._safe_addstr(stdscr, 0, 0, "Terminal too small.", self._color(4))
                stdscr.refresh()
                ch = stdscr.getch()
                if ch in (ord("q"), 27):
                    break
                continue

            self._draw_top_banner(stdscr, max_x)
            self._draw_split_view(stdscr, max_y, max_x)
            self._draw_bottom_bar(stdscr, max_y, max_x)
            stdscr.refresh()

            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                break

            if ch == curses.KEY_RESIZE:
                continue

            # Filtering mode input handling
            if self.is_filtering:
                if ch in (10, 13, curses.KEY_ENTER):  # Enter
                    self.filter_text = self.filter_buffer.strip()
                    self.is_filtering = False
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.detail_scroll = 0
                elif ch in (27,):  # Esc
                    self.is_filtering = False
                    self.filter_buffer = self.filter_text
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    self.filter_buffer = self.filter_buffer[:-1]
                elif 32 <= ch <= 126:
                    self.filter_buffer += chr(ch)
                continue

            # Standard navigation & commands
            if ch in (ord("q"), ord("Q")):
                break
            elif ch == 27:  # Esc clears filter or exits
                if self.filter_text:
                    self.filter_text = ""
                    self.filter_buffer = ""
                    self.selected_index = 0
                else:
                    break
            elif ch in (curses.KEY_DOWN, ord("j")):
                flat = self.get_flattened_selectable_items()
                if flat:
                    self.selected_index = min(len(flat) - 1, self.selected_index + 1)
                    self.detail_scroll = 0
            elif ch in (curses.KEY_UP, ord("k")):
                self.selected_index = max(0, self.selected_index - 1)
                self.detail_scroll = 0
            elif ch in (ord(" "), 10, 13, curses.KEY_ENTER):  # Space or Enter toggles
                item = self.selected_item
                if item:
                    try:
                        self.registry.toggle_item(item)
                    except Exception as exc:
                        self.status_message = f"Error: {exc}"
            elif ch in (ord("\t"), 9):  # Tab cycles scope
                self._cycle_scope()
            elif ch in (ord("/"),):  # / begins filter
                self.is_filtering = True
                self.filter_buffer = self.filter_text
            elif ch in (ord("e"), ord("E")):
                self._open_editor(stdscr)
            elif ch in (ord("x"), ord("X"), curses.KEY_DC):  # x or Delete key deletes
                self._delete_selected_item(stdscr)
            elif ch in (curses.KEY_NPAGE, ord("d")):
                self.detail_scroll += 5
            elif ch in (curses.KEY_PPAGE, ord("u")):
                self.detail_scroll = max(0, self.detail_scroll - 5)

    def run(self) -> None:
        """Run application inside curses wrapper."""
        curses.wrapper(self.run_curses)

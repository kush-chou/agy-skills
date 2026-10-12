"""Curses-based split-view TUI for Antigravity skills, rules, subagents, plugins, MCP, and marketplace."""

import curses
import locale
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple, Union

from ..catalog import CURATED_CATALOG, CatalogSkillPack, check_installed_status
from ..discovery import CustomizationRegistry
from ..models import MCPServer, Plugin, Rule, Scope, Skill, Subagent


class SkillManagerTUI:
    """Full-featured split-pane TUI for managing Antigravity context budgets and customizations."""

    def __init__(self, registry: CustomizationRegistry):
        self.registry = registry
        self.skills: List[Skill] = []
        self.rules: List[Rule] = []
        self.subagents: List[Subagent] = []
        self.plugins: List[Plugin] = []
        self.mcp_servers: List[MCPServer] = []
        self.marketplace_packs: List[CatalogSkillPack] = []

        # Tabs: "skills", "rules", "subagents", "plugins", "mcp", "marketplace", "status"
        self.tabs = ["skills", "rules", "subagents", "plugins", "mcp", "marketplace", "status"]
        self.active_tab_idx: int = 0
        self.prev_tab_idx: int = 0

        self.selected_index: int = 0
        self.scroll_offset: int = 0
        self.detail_scroll: int = 0

        self.filter_text: str = ""
        self.target_scope: Scope = Scope.WORKSPACE
        self.has_colors: bool = False

    def _color(self, pair_idx: int, extra: int = 0) -> int:
        """Safely return curses color pair with extra attributes if colors are supported."""
        if self.has_colors:
            try:
                return curses.color_pair(pair_idx) | extra
            except Exception:
                return extra
        return extra

    @property
    def active_tab(self) -> str:
        return self.tabs[self.active_tab_idx]

    def refresh_data(self) -> None:
        self.skills, self.rules = self.registry.discover_all()
        self.subagents = self.registry.subagents
        self.plugins = self.registry.plugins
        self.mcp_servers = self.registry.mcp_servers
        check_installed_status(self.registry.workspace_root, self.registry.home_dir)
        self.marketplace_packs = list(CURATED_CATALOG)

    def get_current_items_grouped(self) -> List[Tuple[str, List[Any]]]:
        """Return categorized sections of items for the currently selected tab."""
        tab = self.active_tab
        query = self.filter_text.lower().strip()

        def match_filter(item: Any) -> bool:
            if not query:
                return True
            name = getattr(item, "name", "").lower()
            desc = getattr(item, "description", "").lower()
            role = getattr(item, "role", "").lower()
            author = getattr(item, "author", "").lower()
            category = getattr(item, "category", "").lower()
            tools = " ".join(getattr(item, "tools", [])).lower()
            return (
                query in name
                or query in desc
                or query in role
                or query in author
                or query in category
                or query in tools
            )

        if tab == "skills":
            ws_skills = [s for s in self.skills if s.scope == Scope.WORKSPACE and match_filter(s)]
            bi_skills = [s for s in self.skills if s.scope == Scope.BUILTIN and match_filter(s)]
            gl_skills = [s for s in self.skills if s.scope == Scope.GLOBAL and match_filter(s)]
            cat_skills = [s for s in self.skills if s.scope == Scope.CATALOG and match_filter(s)]

            sections = []
            if ws_skills or not self.filter_text:
                sections.append((f"WORKSPACE ({len(ws_skills)})", ws_skills))
            if bi_skills or not self.filter_text:
                sections.append((f"BUILT-IN ({len(bi_skills)})", bi_skills))
            if gl_skills:
                sections.append((f"GLOBAL ({len(gl_skills)})", gl_skills))
            if cat_skills or not self.filter_text:
                sections.append((f"CATALOG AVAILABLE ({len(cat_skills)})", cat_skills))
            return sections

        elif tab == "rules":
            ws_rules = [r for r in self.rules if r.scope == Scope.WORKSPACE and match_filter(r)]
            gl_rules = [r for r in self.rules if r.scope == Scope.GLOBAL and match_filter(r)]
            sections = []
            if ws_rules or not self.filter_text:
                sections.append((f"WORKSPACE ({len(ws_rules)})", ws_rules))
            if gl_rules:
                sections.append((f"GLOBAL ({len(gl_rules)})", gl_rules))
            return sections

        elif tab == "subagents":
            bi_subs = [s for s in self.subagents if s.scope == Scope.BUILTIN and match_filter(s)]
            pl_subs = [s for s in self.subagents if s.tier == "PLUGIN" and match_filter(s)]
            ws_subs = [s for s in self.subagents if s.scope == Scope.WORKSPACE and match_filter(s)]
            sections = []
            if bi_subs:
                sections.append((f"BUILT-IN ({len(bi_subs)})", bi_subs))
            if pl_subs:
                sections.append((f"PLUGINS / EXTENSIONS ({len(pl_subs)})", pl_subs))
            if ws_subs:
                sections.append((f"WORKSPACE ({len(ws_subs)})", ws_subs))
            return sections

        elif tab == "plugins":
            plugs = [p for p in self.plugins if match_filter(p)]
            return [(f"INSTALLED PLUGINS ({len(plugs)})", plugs)]

        elif tab == "mcp":
            system_mcps = [
                m for m in self.mcp_servers
                if not ("_" in m.name or m.name.startswith("data-agent-kit")) and match_filter(m)
            ]
            plugin_mcps = [
                m for m in self.mcp_servers
                if ("_" in m.name or m.name.startswith("data-agent-kit")) and match_filter(m)
            ]
            sections = []
            if system_mcps:
                sections.append((f"SYSTEM MCP SERVERS ({len(system_mcps)})", system_mcps))
            if plugin_mcps:
                sections.append((f"PLUGIN MCP SERVERS ({len(plugin_mcps)})", plugin_mcps))
            return sections

        elif tab == "marketplace":
            top10 = [p for p in self.marketplace_packs if p.stars != "Official" and match_filter(p)]
            official = [p for p in self.marketplace_packs if p.stars == "Official" and match_filter(p)]
            sections = []
            if top10:
                sections.append((f"TOP 10 SKILLLEADERBOARD PACKS ({len(top10)})", top10))
            if official:
                sections.append((f"VOLTAGENT OFFICIAL PACKS ({len(official)})", official))
            return sections

        return []

    def get_flattened_selectable_items(self) -> List[Any]:
        """Return flat list of selectable items for current tab."""
        items: List[Any] = []
        for _, section_items in self.get_current_items_grouped():
            items.extend(section_items)
        return items

    def run(self) -> None:
        if not sys.stdin.isatty():
            print("Note: Running non-interactively; displaying summary list.")
            from ..cli import print_list
            print_list(self.registry)
            return

        try:
            locale.setlocale(locale.LC_ALL, "")
        except Exception:
            pass

        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr) -> None:
        curses.curs_set(0)
        curses.use_default_colors()

        self.has_colors = curses.has_colors()
        # Initialize color pairs
        if self.has_colors:
            # Pair 1: Inverted Cyan background with Black text (Selected item row)
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            # Pair 2: Cyan text (Active bullet ●, card metadata)
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            # Pair 3: Yellow text (Overridden ⇄, warning)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            # Pair 4: Blue text
            curses.init_pair(4, curses.COLOR_BLUE, -1)
            # Pair 5: Red text (Errors)
            curses.init_pair(5, curses.COLOR_RED, -1)
            # Pair 6: Header white/cyan
            curses.init_pair(6, curses.COLOR_WHITE, -1)
            # Pair 7: Footer bar
            curses.init_pair(7, curses.COLOR_WHITE, -1)
            # Pair 8: Magenta (Section dividers)
            curses.init_pair(8, curses.COLOR_MAGENTA, -1)
            # Pair 9: Gray / Dim white (Inactive bullet ○)
            curses.init_pair(9, curses.COLOR_WHITE, -1)
            # Pair 10: Top Blue Banner (White text on Blue background)
            curses.init_pair(10, curses.COLOR_WHITE, curses.COLOR_BLUE)
            # Pair 11: Green (Card box border and title)
            curses.init_pair(11, curses.COLOR_GREEN, -1)
            # Pair 12: Cyan text on black
            curses.init_pair(12, curses.COLOR_CYAN, -1)

        self.refresh_data()

        while True:
            stdscr.clear()
            max_y, max_x = stdscr.getmaxyx()

            if max_y < 12 or max_x < 50:
                self._safe_addstr(stdscr, 0, 0, "Terminal window too small. Please resize.", curses.A_BOLD)
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('q'), 27):
                    break
                continue

            # Render UI components
            self._draw_top_banner(stdscr, max_x)
            self._draw_tab_bar(stdscr, max_x)

            if self.active_tab == "status":
                self._draw_status_dashboard(stdscr, max_y, max_x)
            else:
                self._draw_split_view(stdscr, max_y, max_x)

            self._draw_footer(stdscr, max_y, max_x)
            stdscr.refresh()

            key = stdscr.getch()

            if key in (ord('q'), 27):  # q or ESC
                break
            elif key in (ord('1'), ord('2'), ord('3'), ord('4'), ord('5'), ord('6'), ord('7')):
                self.prev_tab_idx = self.active_tab_idx
                self.active_tab_idx = int(chr(key)) - 1
                self.selected_index = 0
                self.scroll_offset = 0
                self.detail_scroll = 0
            elif key == ord('m'):  # [m] Key: Toggle Marketplace View
                if self.active_tab == "marketplace":
                    self.active_tab_idx = self.prev_tab_idx if self.prev_tab_idx != 5 else 0
                else:
                    self.prev_tab_idx = self.active_tab_idx
                    self.active_tab_idx = 5
                self.selected_index = 0
                self.scroll_offset = 0
                self.detail_scroll = 0
            elif key in (curses.KEY_LEFT, ord('[')):
                self.prev_tab_idx = self.active_tab_idx
                self.active_tab_idx = (self.active_tab_idx - 1) % len(self.tabs)
                self.selected_index = 0
                self.scroll_offset = 0
                self.detail_scroll = 0
            elif key in (curses.KEY_RIGHT, ord(']')):
                self.prev_tab_idx = self.active_tab_idx
                self.active_tab_idx = (self.active_tab_idx + 1) % len(self.tabs)
                self.selected_index = 0
                self.scroll_offset = 0
                self.detail_scroll = 0
            elif key in (curses.KEY_UP, ord('k')):
                items = self.get_flattened_selectable_items()
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self.detail_scroll = 0
            elif key in (curses.KEY_DOWN, ord('j')):
                items = self.get_flattened_selectable_items()
                if self.selected_index < len(items) - 1:
                    self.selected_index += 1
                    self.detail_scroll = 0
            elif key in (curses.KEY_PPAGE, ord('u')):  # Page Up
                self.detail_scroll = max(0, self.detail_scroll - 6)
            elif key in (curses.KEY_NPAGE, ord('d')) and key != ord('d'):  # Page Down
                self.detail_scroll += 6
            elif key in (ord('b'), ord('\n'), 10, curses.KEY_ENTER):  # 'b' or Enter -> Breakdown Inspector
                items = self.get_flattened_selectable_items()
                if 0 <= self.selected_index < len(items):
                    selected = items[self.selected_index]
                    if isinstance(selected, Plugin) and selected.breakdowns:
                        self._open_breakdown_inspector(stdscr, selected)
            elif key in (ord(' '), ord('i')):  # Space or 'i' -> Toggle / Install
                self._handle_toggle()
            elif key == ord('a'):  # Activate All
                items = self.get_flattened_selectable_items()
                self.registry.activate_all(items)
            elif key == ord('d'):  # Deactivate All
                items = self.get_flattened_selectable_items()
                self.registry.deactivate_all(items)
            elif key == ord('e'):  # Edit item in $EDITOR
                self._handle_edit(stdscr)
            elif key == ord('\t'):  # Tab -> Switch Target Scope
                self.target_scope = (
                    Scope.GLOBAL if self.target_scope == Scope.WORKSPACE else Scope.WORKSPACE
                )
            elif key == ord('r'):  # Refresh
                self.refresh_data()
            elif key == ord('/'):  # Filter prompt
                self._prompt_filter(stdscr, max_y, max_x)

    def _safe_addstr(self, stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
        """Safely write string to curses window within bounds."""
        max_y, max_x = stdscr.getmaxyx()
        if 0 <= y < max_y and 0 <= x < max_x:
            fit_text = text[:max_x - x]
            try:
                stdscr.attron(attr)
                stdscr.addstr(y, x, fit_text)
                stdscr.attroff(attr)
            except curses.error:
                pass

    def _draw_top_banner(self, stdscr, max_x: int) -> None:
        """Draw top banner with blue background and real-time context token progress meter."""
        scope_label = self.target_scope.value.upper()
        left_text = f"+ agy-skills [{scope_label}]" if max_x >= 65 else "+ agy-skills"

        active_tokens = self.registry.get_total_active_tokens()
        budget = self.registry.token_budget
        pct = (active_tokens / budget) * 100.0 if budget > 0 else 0.0

        if max_x >= 100:
            bar_len = 20
        elif max_x >= 85:
            bar_len = 16
        elif max_x >= 72:
            bar_len = 10
        else:
            bar_len = 0

        if bar_len > 0:
            filled_len = min(bar_len, max(0, int(round((pct / 100.0) * bar_len))))
            bar_chars = ("▓" * filled_len) + ("░" * (bar_len - filled_len))
            right_text = f"Context: [{bar_chars}] {active_tokens:,}/{budget:,} tok ({pct:.1f}%)"
        else:
            right_text = f"Context: {active_tokens:,}/{budget:,} tok ({pct:.1f}%)"

        spacing = max(1, max_x - len(left_text) - len(right_text) - 1)
        full_line = (left_text + (" " * spacing) + right_text).ljust(max_x - 1)[:max_x - 1]

        attr = self._color(10, curses.A_BOLD) if self.has_colors else curses.A_REVERSE
        self._safe_addstr(stdscr, 0, 0, full_line, attr)

    def _draw_tab_bar(self, stdscr, max_x: int) -> None:
        """Draw secondary tab bar with number keys and TARGET scope."""
        tab_names = [
            ("1: Skills", 0),
            ("2: Rules", 1),
            ("3: Subagents", 2),
            ("4: Plugins", 3),
            ("5: MCP", 4),
            ("6: Market", 5),
            ("7: Status", 6),
        ]

        x = 1
        tab_spacing = 2 if max_x >= 100 else 1
        for label, idx in tab_names:
            if idx == self.active_tab_idx:
                tab_text = f"[{label}]"
                attr = self._color(2, curses.A_BOLD)
            else:
                tab_text = f" {label} " if max_x >= 100 else f"{label}"
                attr = self._color(6)

            self._safe_addstr(stdscr, 1, x, tab_text, attr)
            x += len(tab_text) + tab_spacing

        # Right side TARGET badge: only draw if there is plenty of room so it never gets cut off
        target_badge = f"TARGET: [{self.target_scope.value.upper()}]"
        if max_x >= x + len(target_badge) + 3:
            badge_x = max_x - len(target_badge) - 2
            attr_badge = self._color(2, curses.A_BOLD)
            self._safe_addstr(stdscr, 1, badge_x, target_badge, attr_badge)

    def _draw_split_view(self, stdscr, max_y: int, max_x: int) -> None:
        """Draw split panel view with categorized list on left and inspector card on right."""
        if max_x >= 110:
            split_x = max(42, min(52, int(max_x * 0.38)))
        elif max_x >= 90:
            split_x = max(38, int(max_x * 0.40))
        else:
            split_x = max(36, int(max_x * 0.45))

        content_height = max_y - 3  # Lines 2 to max_y - 2

        # Draw vertical separator
        div_attr = self._color(8) if self.has_colors else curses.A_DIM
        for y in range(2, max_y - 1):
            self._safe_addstr(stdscr, y, split_x, "│", div_attr)

        # Build flattened display rows for left pane
        grouped = self.get_current_items_grouped()
        display_rows: List[Tuple[bool, Any, int]] = []  # (is_header, data, selectable_idx)

        selectable_count = 0
        for section_title, section_items in grouped:
            display_rows.append((True, section_title, -1))
            for item in section_items:
                display_rows.append((False, item, selectable_count))
                selectable_count += 1

        selectable_items = self.get_flattened_selectable_items()
        if self.selected_index >= len(selectable_items):
            self.selected_index = max(0, len(selectable_items) - 1)

        # Keep selected item comfortably in view
        selected_display_row = 0
        for r_idx, (is_header, data, sel_idx) in enumerate(display_rows):
            if not is_header and sel_idx == self.selected_index:
                selected_display_row = r_idx
                break

        if selected_display_row < self.scroll_offset:
            self.scroll_offset = selected_display_row
        elif selected_display_row >= self.scroll_offset + content_height:
            self.scroll_offset = selected_display_row - content_height + 1

        # Render visible rows in left pane
        for row_i in range(content_height):
            y = 2 + row_i
            list_idx = self.scroll_offset + row_i

            if list_idx >= len(display_rows):
                break

            is_header, data, sel_idx = display_rows[list_idx]

            if is_header:
                # Render Section Header (e.g. ─ WORKSPACE (5) ─)
                title = str(data)
                dash_count = max(1, (split_x - len(title) - 4) // 2)
                dashes = "─" * dash_count
                hdr_str = f" {dashes} {title} {dashes} "[:split_x - 1]
                hdr_attr = self._color(8, curses.A_BOLD)
                self._safe_addstr(stdscr, y, 0, hdr_str, hdr_attr)
            else:
                item = data
                is_selected = (sel_idx == self.selected_index)

                # Bullet indicator
                is_active = getattr(item, "is_active", True)
                is_overridden = getattr(item, "is_overridden", False)

                if is_overridden:
                    bullet = "⇄"
                elif is_active:
                    bullet = "●"
                else:
                    bullet = "○"

                name = item.name
                if isinstance(item, MCPServer):
                    tok_str = f"{item.tools_count}t"
                elif hasattr(item, "stars"):
                    tok_str = f"★{item.stars}"
                else:
                    tokens = getattr(item, "tokens", 0)
                    tok_str = f"~{tokens}t"

                # Row text layout with guaranteed breathing room
                tok_col = split_x - len(tok_str) - 1
                available_name_len = max(8, tok_col - 5)  # 3 chars prefix " ● ", 2 spaces buffer before tok_str

                if len(name) > available_name_len:
                    disp_name = name[:available_name_len - 1] + "…"
                else:
                    disp_name = name

                if is_selected:
                    # Inverted Cyan highlight across entire width
                    sel_attr = self._color(1, curses.A_BOLD) if self.has_colors else curses.A_REVERSE
                    self._safe_addstr(stdscr, y, 0, " " * split_x, sel_attr)
                    self._safe_addstr(stdscr, y, 1, bullet, sel_attr)
                    self._safe_addstr(stdscr, y, 3, disp_name, sel_attr)
                    self._safe_addstr(stdscr, y, tok_col, tok_str, sel_attr)
                else:
                    # Unselected: draw bullet and text with proper colors
                    bullet_attr = (
                        self._color(3) if is_overridden
                        else self._color(2) if is_active
                        else self._color(9)
                    )

                    self._safe_addstr(stdscr, y, 0, " ")
                    self._safe_addstr(stdscr, y, 1, bullet, bullet_attr)
                    self._safe_addstr(stdscr, y, 3, disp_name)
                    self._safe_addstr(stdscr, y, tok_col, tok_str, self._color(2))

        # Right pane rendering
        if selectable_items and 0 <= self.selected_index < len(selectable_items):
            selected_item = selectable_items[self.selected_index]
            self._draw_inspector_pane(stdscr, selected_item, split_x + 2, 2, max_x - split_x - 3, content_height)
        else:
            self._safe_addstr(stdscr, 3, split_x + 4, "No customizations matching this filter.", curses.A_DIM)

        # Re-ensure vertical divider is drawn
        for y in range(2, max_y - 1):
            self._safe_addstr(stdscr, y, split_x, "│", div_attr)

    def _draw_inspector_pane(
        self, stdscr, item: Any, start_x: int, start_y: int, width: int, height: int
    ) -> None:
        """Draw top metadata card box and rendered markdown preview below."""
        card_w = width - 2
        if card_w < 20:
            return

        if isinstance(item, Plugin):
            self._draw_plugin_inspector(stdscr, item, start_x, start_y, width, height)
            return

        box_color = self._color(11)
        title_color = self._color(11, curses.A_BOLD)
        meta_color = self._color(12)

        # 1. Prepare Box Metadata Lines
        item_name = item.name
        if isinstance(item, Skill):
            entity_type = "SKILL"
        elif isinstance(item, Rule):
            entity_type = "RULE"
        elif isinstance(item, Subagent):
            entity_type = "SUBAGENT"
        elif isinstance(item, Plugin):
            entity_type = "PLUGIN"
        elif isinstance(item, MCPServer):
            entity_type = "MCP SERVER"
        else:
            entity_type = "MARKETPLACE PACK"

        tier = getattr(item, "tier", "WORKSPACE")
        tokens = getattr(item, "tokens", 0)

        meta_lines = []
        if isinstance(item, MCPServer):
            meta_lines.append(f"Type: MCP SERVER · Active: {'● Enabled' if item.is_active else '○ Disabled'} · {item.tools_count} Tools")
            if item.path:
                meta_lines.append(f"Path: {item.path}")
            if item.tools:
                sample_tools = ", ".join(item.tools[:5])
                if len(item.tools) > 5:
                    sample_tools += f" ... (+{len(item.tools) - 5} more)"
                meta_lines.append(f"Tools: {sample_tools}")
        elif hasattr(item, "repo") and hasattr(item, "stars"):
            inst_badge = "✔ Installed" if item.is_installed else "○ Available (Press Space to Install)"
            meta_lines.append(f"Type: MARKETPLACE · Category: {item.category} · ★ {item.stars}")
            meta_lines.append(f"Repo: {item.repo} · Status: {inst_badge}")
            meta_lines.append(f"Slash Trigger: {item.slash_trigger} · ~{item.tokens} tok")
            meta_lines.append(f"Author: {item.author}")
        else:
            meta_lines.append(f"Type: {entity_type} · Tier: {tier} · ~{tokens} tok")
            author = getattr(item, "author", "")
            if author:
                meta_lines.append(f"Author: {author}")
            trigger = getattr(item, "slash_trigger", "")
            if trigger:
                meta_lines.append(f"Slash Trigger: {trigger}")
            elif isinstance(item, Subagent):
                meta_lines.append(f"Role: {item.role}")
                meta_lines.append(f"Model: {item.model}")
            elif isinstance(item, Rule):
                size_kb = f"{item.size_bytes / 1024:.2f} KB"
                meta_lines.append(f"Size: {item.size_bytes:,} bytes ({size_kb}) · Limit: 24 KB")

        desc = getattr(item, "description", "")
        wrapped_desc = textwrap.wrap(desc, width=card_w - 4) if desc else []

        # 2. Draw Top Box Card
        title_header = f" {item_name} "
        top_dashes = "─" * max(1, card_w - 4 - len(title_header))
        top_border = f"┌──{title_header}{top_dashes}┐"
        self._safe_addstr(stdscr, start_y, start_x, top_border[:card_w], box_color)

        curr_y = start_y + 1

        # Title line inside
        self._safe_addstr(stdscr, curr_y, start_x, "│", box_color)
        self._safe_addstr(stdscr, curr_y, start_x + 2, item_name, title_color)
        self._safe_addstr(stdscr, curr_y, start_x + card_w - 1, "│", box_color)
        curr_y += 1

        # Metadata lines
        for m_line in meta_lines:
            self._safe_addstr(stdscr, curr_y, start_x, "│", box_color)
            self._safe_addstr(stdscr, curr_y, start_x + 2, m_line[:card_w - 4], meta_color)
            self._safe_addstr(stdscr, curr_y, start_x + card_w - 1, "│", box_color)
            curr_y += 1

        # Blank divider row inside card
        self._safe_addstr(stdscr, curr_y, start_x, "│", box_color)
        self._safe_addstr(stdscr, curr_y, start_x + card_w - 1, "│", box_color)
        curr_y += 1

        # Wrapped description
        for d_line in wrapped_desc[:4]:
            self._safe_addstr(stdscr, curr_y, start_x, "│", box_color)
            self._safe_addstr(stdscr, curr_y, start_x + 2, d_line[:card_w - 4], self._color(6))
            self._safe_addstr(stdscr, curr_y, start_x + card_w - 1, "│", box_color)
            curr_y += 1

        # Bottom card border
        bot_dashes = "─" * (card_w - 2)
        bot_border = f"└{bot_dashes}┘"
        self._safe_addstr(stdscr, curr_y, start_x, bot_border[:card_w], box_color)
        curr_y += 2

        # 3. Content Preview Below Box (Rendered Markdown Body)
        preview_height = height - (curr_y - start_y)
        if preview_height <= 0:
            return

        if isinstance(item, MCPServer):
            body_parts = []
            if item.instructions:
                body_parts.append(f"## Server Instructions\n{item.instructions}\n")
            body_parts.append(f"## Registered MCP Tools ({item.tools_count})")
            for t in item.tools:
                body_parts.append(f"- **{t}**")
            body_raw = "\n".join(body_parts)
        elif hasattr(item, "repo") and hasattr(item, "stars"):
            body_parts = [
                f"# {item.name.replace('-', ' ').title()}",
                f"\n**Upstream Source**: {item.source_url}",
                f"**Stars**: ★ {item.stars} · **Category**: {item.category}\n",
                f"## Overview\n{item.description}\n",
                f"## Turnkey Installation",
                f"- Press `[Space]` or `[i]` to install pack to `[{self.target_scope.value.upper()}]`.",
                f"- Press `[Tab]` to switch target scope (Workspace vs Global).",
                f"- Slash Trigger: `{item.slash_trigger}`",
            ]
            body_raw = "\n".join(body_parts)
        else:
            body_raw = (
                getattr(item, "body", "")
                or getattr(item, "raw_content", "")
                or getattr(item, "system_prompt", "")
            )

        rendered_lines = self._render_markdown(body_raw, card_w)

        # Render preview lines with scroll offset
        for p_idx in range(preview_height):
            line_idx = p_idx + self.detail_scroll
            if line_idx >= len(rendered_lines):
                break

            txt, attr = rendered_lines[line_idx]
            rendered_y = curr_y + p_idx
            self._safe_addstr(stdscr, rendered_y, start_x, txt[:card_w], attr)

    def _render_markdown(self, markdown_text: str, width: int) -> List[Tuple[str, int]]:
        """Cleanly render markdown text for curses terminal display."""
        if not markdown_text:
            return []

        rendered: List[Tuple[str, int]] = []
        raw_lines = markdown_text.splitlines()
        in_code_block = False
        table_buffer: List[str] = []

        def clean_inline(text: str) -> str:
            # Strip links [label](url) -> label
            t = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
            # Strip bold **text** or __text__
            t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
            t = re.sub(r"__(.*?)__", r"\1", t)
            # Strip inline code `code`
            t = re.sub(r"`(.*?)`", r"\1", t)
            # Strip italic *text* or _text_
            t = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", t)
            return t.strip()

        def flush_table(buf: List[str]):
            if not buf:
                return
            rows = []
            for t_line in buf:
                parts = [c.strip() for c in t_line.split("|")]
                if len(parts) >= 2 and parts[0] == "":
                    parts = parts[1:]
                if len(parts) >= 1 and parts[-1] == "":
                    parts = parts[:-1]
                if parts:
                    rows.append(parts)

            if not rows:
                return

            has_sep = False
            sep_idx = -1
            for idx, r in enumerate(rows):
                if all(re.match(r"^:?-+:?$", c) for c in r):
                    has_sep = True
                    sep_idx = idx
                    break

            if not has_sep:
                for b_line in buf:
                    clean_text = clean_inline(b_line)
                    for w_l in textwrap.wrap(clean_text, width=max(10, width - 2)):
                        rendered.append((w_l, self._color(6)))
                return

            header_row = rows[0] if sep_idx > 0 else []
            data_rows = [r for idx, r in enumerate(rows) if idx != sep_idx and (sep_idx == 0 or idx > sep_idx)]

            num_cols = max(len(r) for r in rows if not all(re.match(r"^:?-+:?$", c) for c in r))
            if num_cols == 0:
                return

            clean_headers = [clean_inline(header_row[i]) if i < len(header_row) else "" for i in range(num_cols)]
            clean_data = [
                [clean_inline(row[i]) if i < len(row) else "" for i in range(num_cols)]
                for row in data_rows
            ]

            col_widths = [len(h) for h in clean_headers]
            for r in clean_data:
                for i, c in enumerate(r):
                    col_widths[i] = max(col_widths[i], len(c))
            col_widths = [max(3, w) for w in col_widths]

            total_dividers = (num_cols - 1) * 3
            avail_w = max(num_cols * 4, width - total_dividers)
            total_content_w = sum(col_widths)
            if total_content_w > avail_w:
                scale = avail_w / total_content_w
                col_widths = [max(4, int(w * scale)) for w in col_widths]

            hdr_parts = [clean_headers[i].ljust(col_widths[i])[:col_widths[i]] for i in range(num_cols)]
            rendered.append((" │ ".join(hdr_parts), self._color(2, curses.A_BOLD)))
            sep_parts = ["─" * col_widths[i] for i in range(num_cols)]
            rendered.append(("─┼─".join(sep_parts), self._color(9)))
            for r in clean_data:
                row_parts = [r[i].ljust(col_widths[i])[:col_widths[i]] for i in range(num_cols)]
                rendered.append((" │ ".join(row_parts), self._color(6)))
            rendered.append(("", 0))

        for line in raw_lines:
            stripped = line.strip()

            if "|" in stripped and not in_code_block:
                table_buffer.append(stripped)
                continue
            elif table_buffer:
                flush_table(table_buffer)
                table_buffer = []

            if stripped.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_lang = stripped[3:].strip()
                    lang_lbl = f" [ {code_lang} ]" if code_lang else " [code]"
                    code_w = max(10, width - 2)
                    dash_cnt = max(0, code_w - len(lang_lbl) - 2)
                    rendered.append((f"┌─{lang_lbl}{'─' * dash_cnt}┐"[:width], self._color(3, curses.A_BOLD)))
                else:
                    in_code_block = False
                    code_w = max(10, width - 2)
                    dash_cnt = max(0, code_w - 2)
                    rendered.append((f"└{'─' * dash_cnt}┘"[:width], self._color(3)))
                continue

            if in_code_block:
                code_w = max(10, width - 2)
                inner_w = max(0, code_w - 4)
                code_line = f"│ {line[:inner_w].ljust(inner_w)} │"
                rendered.append((code_line[:width], self._color(3)))
                continue

            if not stripped:
                if rendered and rendered[-1][0] != "":
                    rendered.append(("", 0))
                continue

            if re.match(r"^((\-\s*){3,}|(\*\s*){3,}|(_\s*){3,})$", stripped):
                rendered.append(("─" * min(width, 48), self._color(9)))
                continue

            if stripped.startswith("# "):
                h_text = clean_inline(stripped[2:])
                rendered.append((f"◆ {h_text}", self._color(8, curses.A_BOLD)))
                rendered.append(("─" * min(width, len(h_text) + 2), self._color(8)))
                continue

            if stripped.startswith("## "):
                h_text = clean_inline(stripped[3:])
                rendered.append((f"▸ {h_text}", self._color(2, curses.A_BOLD)))
                continue

            if stripped.startswith("### "):
                h_text = clean_inline(stripped[4:])
                rendered.append((f"• {h_text}", self._color(4, curses.A_BOLD)))
                continue

            if stripped.startswith("#### "):
                h_text = clean_inline(stripped[5:])
                rendered.append((f"  {h_text}", self._color(6, curses.A_BOLD)))
                continue

            bullet_match = re.match(r"^(\*|\-|\+)\s+(.*)$", stripped)
            if bullet_match:
                item_text = clean_inline(bullet_match.group(2))
                wrapped = textwrap.wrap(item_text, width=max(10, width - 6))
                if wrapped:
                    rendered.append((f"  • {wrapped[0]}", self._color(6)))
                    for w_l in wrapped[1:]:
                        rendered.append((f"    {w_l}", self._color(6)))
                else:
                    rendered.append(("  •", self._color(6)))
                continue

            num_match = re.match(r"^(\d+\.)\s+(.*)$", stripped)
            if num_match:
                prefix = num_match.group(1)
                item_text = clean_inline(num_match.group(2))
                indent_len = len(prefix) + 3
                wrapped = textwrap.wrap(item_text, width=max(10, width - indent_len - 2))
                if wrapped:
                    rendered.append((f"  {prefix} {wrapped[0]}", self._color(6)))
                    for w_l in wrapped[1:]:
                        rendered.append((f"{' ' * indent_len}{w_l}", self._color(6)))
                else:
                    rendered.append((f"  {prefix}", self._color(6)))
                continue

            clean_text = clean_inline(stripped)
            for w_l in textwrap.wrap(clean_text, width=max(10, width - 2)):
                rendered.append((w_l, self._color(6)))

        if table_buffer:
            flush_table(table_buffer)

        if in_code_block:
            code_w = max(10, width - 2)
            dash_cnt = max(0, code_w - 2)
            rendered.append((f"└{'─' * dash_cnt}┘"[:width], self._color(3)))

        return rendered

    def _draw_plugin_inspector(
        self, stdscr, item: Plugin, start_x: int, start_y: int, width: int, height: int
    ) -> None:
        """Draw rich Customizations view mirroring the Antigravity IDE GUI."""
        card_w = width - 2
        if card_w < 20:
            return

        lines: List[Tuple[str, int]] = []

        # 1. Breadcrumb Header
        lines.append((f"Customizations / {item.name}", self._color(6, curses.A_BOLD)))
        lines.append(("", 0))

        # 2. Description
        if item.description:
            for d_line in textwrap.wrap(item.description, width=card_w - 2):
                lines.append((d_line, self._color(6)))
            lines.append(("", 0))

        # 3. Suggested Prompts / Examples
        if item.suggested_prompts:
            lines.append(("Suggested Prompts / Examples:", self._color(3, curses.A_BOLD)))
            for sp in item.suggested_prompts[:3]:
                for sp_line in textwrap.wrap(f'• "{sp}"', width=card_w - 4):
                    lines.append((f"  {sp_line}", self._color(6)))
            lines.append(("", 0))

        # 4. Resources
        if item.resources:
            lines.append(("Resources", self._color(3, curses.A_BOLD)))
            for res in item.resources:
                title = res.get("title", "")
                url = res.get("url", "")
                lines.append((f"  • {title} [↗]", self._color(2, curses.A_UNDERLINE)))
                if url and card_w > 50:
                    lines.append((f"    {url}", self._color(9)))
            lines.append(("", 0))

        # 5. Commands (Skills)
        if item.commands:
            lines.append((f"Commands ({len(item.commands)}) ▼", self._color(2, curses.A_BOLD)))
            for cmd_trig, cmd_desc, cmd_tok in item.commands:
                tok_badge = f"(~{cmd_tok} tok)"
                hdr = f"  {cmd_trig:<30} {tok_badge}"
                lines.append((hdr[:card_w], self._color(2, curses.A_BOLD)))
                if cmd_desc:
                    for desc_l in textwrap.wrap(cmd_desc, width=card_w - 6):
                        lines.append((f"    {desc_l}", self._color(6)))
            lines.append(("", 0))

        # 6. Agents
        if item.agents:
            lines.append((f"Agents ({len(item.agents)}) ▼", self._color(11, curses.A_BOLD)))
            for ag_name, ag_desc, ag_tok in item.agents:
                tok_badge = f"(~{ag_tok} tok)"
                hdr = f"  {ag_name:<30} {tok_badge}"
                lines.append((hdr[:card_w], self._color(11, curses.A_BOLD)))
                if ag_desc:
                    for desc_l in textwrap.wrap(ag_desc, width=card_w - 6):
                        lines.append((f"    {desc_l}", self._color(6)))
            lines.append(("", 0))

        # 7. MCP servers
        if item.mcp_servers or item.mcp_tools:
            cnt = len(item.mcp_servers) or len(item.mcp_tools)
            lines.append((f"MCP servers ({cnt}) ▼", self._color(8, curses.A_BOLD)))
            for srv in item.mcp_servers:
                lines.append((f"  {srv}"[:card_w], self._color(8)))
            lines.append(("", 0))

        # 8. Rules
        if item.rules:
            lines.append((f"Rules ({len(item.rules)}) ▼", self._color(3, curses.A_BOLD)))
            for r_name, r_desc, r_tok in item.rules:
                tok_badge = f"(~{r_tok} tok)" if r_tok else ""
                lines.append((f"  {r_name:<30} {tok_badge}"[:card_w], self._color(3, curses.A_BOLD)))
                if r_desc:
                    for desc_l in textwrap.wrap(r_desc, width=card_w - 6):
                        lines.append((f"    {desc_l}", self._color(6)))
            lines.append(("", 0))

        # 9. Context usage
        budget = 20_000
        pct = (item.tokens / budget) * 100.0
        lines.append((f"Context usage ({item.tokens:,} tokens)", self._color(6, curses.A_BOLD)))
        lines.append((f"Customizations    {item.tokens:,} / {budget:,} tokens ({pct:.1f}%)", self._color(2)))

        bar_len = min(28, card_w - 4)
        s_chars = int(round((item.skills_tokens / budget) * bar_len))
        m_chars = int(round((item.mcp_tokens / budget) * bar_len))
        a_chars = int(round((item.agents_tokens / budget) * bar_len))
        r_chars = int(round((item.rules_tokens / budget) * bar_len))
        filled_total = s_chars + m_chars + a_chars + r_chars
        empty_chars = max(0, bar_len - filled_total)
        bar_str = ("█" * s_chars) + ("▓" * m_chars) + ("▒" * a_chars) + ("░" * r_chars) + ("·" * empty_chars)
        lines.append((f"[{bar_str}]", self._color(2, curses.A_BOLD)))

        if item.skills_tokens or item.commands:
            s_pct = (item.skills_tokens / budget) * 100.0
            cmd_count = len(item.commands)
            lines.append((
                f"  • Skills ({item.skills_tokens:,} tokens) {s_pct:.1f}%      [b] Show {cmd_count} breakdowns",
                self._color(2),
            ))

        if item.mcp_tokens or item.mcp_tools:
            m_pct = (item.mcp_tokens / budget) * 100.0
            m_count = len(item.mcp_tools)
            warn_str = f"  ⚠️ {item.excluded_tools_count} excluded" if item.excluded_tools_count else ""
            lines.append((
                f"  • Mcp Tools ({item.mcp_tokens:,} tokens) {m_pct:.1f}%{warn_str}      [b] Show {m_count} breakdowns",
                self._color(11),
            ))

        if item.agents_tokens or item.agents:
            a_pct = (item.agents_tokens / budget) * 100.0
            a_count = len(item.agents)
            lines.append((
                f"  • Subagents ({item.agents_tokens:,} tokens) {a_pct:.1f}%      [b] Show {a_count} breakdowns",
                self._color(4),
            ))

        if item.rules_tokens or item.rules:
            r_pct = (item.rules_tokens / budget) * 100.0
            r_count = len(item.rules)
            lines.append((
                f"  • Rules ({item.rules_tokens:,} tokens) {r_pct:.1f}%      [b] Show {r_count} breakdowns",
                self._color(3),
            ))

        lines.append(("", 0))
        lines.append((
            f"Version {item.version} · Status: {'● Enabled' if item.is_active else '○ Disabled (Press Space to toggle)'}",
            self._color(9),
        ))
        lines.append((
            "Tip: Press [b] or [Enter] to open interactive breakdown & cherry-pick components.",
            self._color(10, curses.A_BOLD),
        ))

        # Render lines with detail_scroll offset
        for p_idx in range(height):
            line_idx = p_idx + self.detail_scroll
            if line_idx >= len(lines):
                break
            txt, attr = lines[line_idx]
            self._safe_addstr(stdscr, start_y + p_idx, start_x, txt[:card_w], attr)

    def _open_breakdown_inspector(self, stdscr, plugin: Plugin) -> None:
        """Modal subcomponent inspector & cherry-picker for power users."""
        if not plugin.breakdowns:
            return

        selected_b_idx = 0
        b_scroll = 0

        while True:
            max_y, max_x = stdscr.getmaxyx()
            stdscr.clear()

            modal_w = min(110, max_x - 4)
            modal_h = min(28, max_y - 4)
            start_x = (max_x - modal_w) // 2
            start_y = (max_y - modal_h) // 2

            # Outer box
            box_attr = self._color(2, curses.A_BOLD)
            title = f" [Breakdown Inspector] Customizations / {plugin.name} ({plugin.tokens:,} tokens) "
            top_dashes = "─" * max(1, modal_w - 2 - len(title))
            self._safe_addstr(stdscr, start_y, start_x, f"┌{title}{top_dashes}┐", box_attr)

            for my in range(1, modal_h - 1):
                self._safe_addstr(stdscr, start_y + my, start_x, "│" + " " * (modal_w - 2) + "│", box_attr)

            bot_dashes = "─" * (modal_w - 2)
            self._safe_addstr(stdscr, start_y + modal_h - 1, start_x, f"└{bot_dashes}┘", box_attr)

            # Sub-header: instructions
            instr = " [↑/↓] Navigate  [Space] Toggle Component  [a/d] All/None  [Esc/q/Enter] Done "
            self._safe_addstr(stdscr, start_y + 1, start_x + 2, instr, self._color(10, curses.A_BOLD))

            # Budget bar inside modal
            pct = (plugin.tokens / 20_000) * 100.0
            meter_line = f" Plugin Context: {plugin.tokens:,} / 20,000 tokens ({pct:.1f}%) "
            self._safe_addstr(stdscr, start_y + 2, start_x + 2, meter_line, self._color(6))

            content_rows = modal_h - 6
            if selected_b_idx < b_scroll:
                b_scroll = selected_b_idx
            elif selected_b_idx >= b_scroll + content_rows:
                b_scroll = selected_b_idx - content_rows + 1

            for r_i in range(content_rows):
                b_idx = b_scroll + r_i
                if b_idx >= len(plugin.breakdowns):
                    break
                b = plugin.breakdowns[b_idx]
                curr_y = start_y + 4 + r_i

                is_sel = (b_idx == selected_b_idx)
                bullet = "●" if b.is_active else "○"
                bullet_attr = self._color(2) if b.is_active else self._color(9)
                cat_badge = f"[{b.category.upper()}]"
                tok_badge = f"{b.tokens:,} tok ({(b.tokens / 20000) * 100:.1f}%)"
                if b.is_excluded:
                    tok_badge += " ⚠️ excl"

                name_str = b.name
                desc_str = b.description.replace("\n", " ")
                line_str = f" {bullet} {cat_badge:<12} {name_str:<26} {tok_badge:<18} {desc_str}"
                line_str = line_str[:modal_w - 4]

                if is_sel:
                    attr = self._color(1, curses.A_BOLD) if self.has_colors else curses.A_REVERSE
                    self._safe_addstr(stdscr, curr_y, start_x + 2, line_str.ljust(modal_w - 4), attr)
                else:
                    self._safe_addstr(stdscr, curr_y, start_x + 2, " ")
                    self._safe_addstr(stdscr, curr_y, start_x + 3, bullet, bullet_attr)
                    self._safe_addstr(stdscr, curr_y, start_x + 5, f"{cat_badge:<12}", self._color(4))
                    self._safe_addstr(stdscr, curr_y, start_x + 18, f"{name_str:<26}", curses.A_BOLD)
                    self._safe_addstr(stdscr, curr_y, start_x + 45, f"{tok_badge:<18}", self._color(2))
                    self._safe_addstr(stdscr, curr_y, start_x + 64, desc_str[:modal_w - 66], self._color(6))

            stdscr.refresh()
            k = stdscr.getch()

            if k in (27, ord('q'), ord('\n'), curses.KEY_ENTER, ord('b')):
                break
            elif k in (curses.KEY_UP, ord('k')):
                if selected_b_idx > 0:
                    selected_b_idx -= 1
            elif k in (curses.KEY_DOWN, ord('j')):
                if selected_b_idx < len(plugin.breakdowns) - 1:
                    selected_b_idx += 1
            elif k == ord(' '):  # Toggle subcomponent
                curr_b = plugin.breakdowns[selected_b_idx]
                self.registry.toggle_plugin_component(plugin.name, curr_b.name)
            elif k == ord('a'):  # Enable all
                for b in plugin.breakdowns:
                    if not b.is_active:
                        self.registry.toggle_plugin_component(plugin.name, b.name)
            elif k == ord('d'):  # Disable all
                for b in plugin.breakdowns:
                    if b.is_active:
                        self.registry.toggle_plugin_component(plugin.name, b.name)

    def _draw_status_dashboard(self, stdscr, max_y: int, max_x: int) -> None:
        """Draw full status & context window health dashboard."""
        y = 3
        active_tokens = self.registry.get_total_active_tokens()
        budget = self.registry.token_budget
        pct = (active_tokens / budget) * 100.0 if budget > 0 else 0.0

        bar_len = min(40, max_x - 30)
        filled_len = min(bar_len, max(0, int(round((pct / 100.0) * bar_len))))
        bar_chars = ("▓" * filled_len) + ("░" * (bar_len - filled_len))

        self._safe_addstr(stdscr, y, 4, "=== Antigravity Context Window & Customization Health ===", curses.A_BOLD)
        y += 2

        self._safe_addstr(
            stdscr,
            y,
            4,
            f"Context Consumption: [{bar_chars}] {active_tokens:,} / {budget:,} tok ({pct:.1f}% used)",
            self._color(2, curses.A_BOLD),
        )
        y += 2

        breakdown = self.registry.get_token_breakdown()
        self._safe_addstr(stdscr, y, 4, "Customization Footprint:", curses.A_UNDERLINE)
        y += 1

        labels = [
            ("Workspace Skills", breakdown["workspace_skills"]),
            ("Built-in Skills", breakdown["builtin_skills"]),
            ("Global Skills", breakdown["global_skills"]),
            ("Catalog Active Skills", breakdown["catalog_skills"]),
            ("Antigravity Rules", breakdown["rules"]),
            ("Active Subagents", breakdown["subagents"]),
            ("Active Plugins", breakdown.get("plugins", (0, 0))),
            ("Active MCP Servers", breakdown.get("mcp_servers", (0, 0))),
        ]

        for label, (count, tok) in labels:
            row = f"  • {label:<24}: {count:>3} active ({tok:>5,} tok/items)"
            self._safe_addstr(stdscr, y, 4, row)
            y += 1

        y += 1
        self._safe_addstr(stdscr, y, 4, "Antigravity Compliance Audit:", curses.A_UNDERLINE)
        y += 1

        invalid_skills = [s for s in self.skills if not s.is_valid]
        invalid_rules = [r for r in self.rules if not r.is_valid]

        if not invalid_skills and not invalid_rules:
            self._safe_addstr(stdscr, y, 4, "  ✔ All customizations adhere to Antigravity 24 KB limits and naming specs.", self._color(11))
            y += 1
        else:
            if invalid_skills:
                self._safe_addstr(stdscr, y, 4, f"  ✖ {len(invalid_skills)} skill(s) have validation issues.", self._color(5))
                y += 1
            if invalid_rules:
                self._safe_addstr(stdscr, y, 4, f"  ✖ {len(invalid_rules)} rule(s) exceed 24 KB hard cap.", self._color(5))
                y += 1

        y += 1
        self._safe_addstr(stdscr, y, 4, "Environment Configuration:", curses.A_UNDERLINE)
        y += 1
        self._safe_addstr(stdscr, y, 4, f"  • Workspace Root : {self.registry.workspace_root}")
        y += 1
        self._safe_addstr(stdscr, y, 4, f"  • Global Config  : {self.registry.global_config_dir}")
        y += 1
        self._safe_addstr(stdscr, y, 4, f"  • Target Scope   : [{self.target_scope.value.upper()}] (Press [Tab] to toggle)")

    def _get_footer_text(self, max_x: int) -> str:
        """Return responsive footer shortcut string tailored to terminal width."""
        if max_x >= 115:
            return "[1-7] Tabs  [b/Enter] Breakdowns  [Space/i] Toggle/Install  [a/d] All/None  [Tab] Scope  [/] Filter  [q] Quit"
        elif max_x >= 98:
            return "[1-7] Tabs  [b] Breakdowns  [Space] Toggle  [a/d] All/None  [Tab] Scope  [/] Filter  [q] Quit"
        elif max_x >= 80:
            return "[1-7] Tabs [b] Detail [Space] Toggle [a/d] All [Tab] Scope [/] Filter [q] Quit"
        elif max_x >= 60:
            return "[1-7] Tabs [Space] Toggle [Tab] Scope [/] Filter [q] Quit"
        else:
            return "[1-7] Tabs [Space] Toggle [/] Filter [q] Quit"

    def _draw_footer(self, stdscr, max_y: int, max_x: int) -> None:
        """Draw bottom shortcut bar."""
        footer_text = self._get_footer_text(max_x)
        line = footer_text.ljust(max_x - 1)[:max_x - 1]
        attr = self._color(7, curses.A_BOLD) if self.has_colors else curses.A_REVERSE
        self._safe_addstr(stdscr, max_y - 1, 0, line, attr)

    def _handle_toggle(self) -> None:
        """Toggle active state of currently selected item or install from marketplace."""
        items = self.get_flattened_selectable_items()
        if items and 0 <= self.selected_index < len(items):
            item = items[self.selected_index]
            self.registry.toggle_item(item, target_scope=self.target_scope)
            self.refresh_data()

    def _handle_edit(self, stdscr) -> None:
        """Open source file of selected item in $EDITOR."""
        items = self.get_flattened_selectable_items()
        if not items or not (0 <= self.selected_index < len(items)):
            return

        item = items[self.selected_index]
        target_file = getattr(item, "skill_file", None) or getattr(item, "path", None)
        if isinstance(item, MCPServer) and item.path:
            inst = item.path / "instructions.md"
            target_file = inst if inst.exists() else item.path
        elif hasattr(item, "install_path") and item.install_path:
            target_file = item.install_path / "SKILL.md"

        if not target_file or not os.path.exists(target_file):
            return

        curses.def_prog_mode()
        curses.endwin()

        editor = os.environ.get("EDITOR", "nano")
        os.system(f"{editor} '{target_file}'")

        curses.reset_prog_mode()
        curses.curs_set(0)
        self.refresh_data()

    def _prompt_filter(self, stdscr, max_y: int, max_x: int) -> None:
        """Prompt user for interactive search filter."""
        curses.echo()
        curses.curs_set(1)
        try:
            prompt = " Filter customizations (ENTER to apply, empty to clear): "
            self._safe_addstr(stdscr, max_y - 1, 0, prompt.ljust(max_x - 1), curses.A_REVERSE)
            stdscr.refresh()
            query_bytes = stdscr.getstr(max_y - 1, len(prompt), 32)
            self.filter_text = query_bytes.decode("utf-8", errors="ignore").strip()
            self.selected_index = 0
            self.scroll_offset = 0
            self.detail_scroll = 0
        except curses.error:
            pass
        finally:
            curses.noecho()
            curses.curs_set(0)

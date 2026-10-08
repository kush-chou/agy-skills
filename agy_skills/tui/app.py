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
        left_text = f"+ agy-skills [{scope_label}]"

        active_tokens = self.registry.get_total_active_tokens()
        budget = self.registry.token_budget
        pct = min(100.0, (active_tokens / budget) * 100.0) if budget > 0 else 0.0

        bar_len = 18
        filled_len = int(round((pct / 100.0) * bar_len))
        bar_chars = ("▓" * filled_len) + ("░" * (bar_len - filled_len))

        right_text = f"Context: [{bar_chars}] {active_tokens:,}/{budget:,} tok ({pct:.1f}%)"

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
        for label, idx in tab_names:
            if idx == self.active_tab_idx:
                tab_text = f"[{label}]"
                attr = self._color(2, curses.A_BOLD)
            else:
                tab_text = f" {label} "
                attr = self._color(6)

            self._safe_addstr(stdscr, 1, x, tab_text, attr)
            x += len(tab_text) + 2

        # Right side TARGET badge
        target_badge = f"TARGET: [{self.target_scope.value.upper()}]"
        badge_x = max(x, max_x - len(target_badge) - 2)
        attr_badge = self._color(2, curses.A_BOLD)
        self._safe_addstr(stdscr, 1, badge_x, target_badge, attr_badge)

    def _draw_split_view(self, stdscr, max_y: int, max_x: int) -> None:
        """Draw split panel view with categorized list on left and inspector card on right."""
        split_x = max(34, max_x // 3)
        content_height = max_y - 3  # Lines 2 to max_y - 2

        # Draw vertical separator
        vline_char = getattr(curses, "ACS_VLINE", "│")
        for y in range(2, max_y - 1):
            try:
                stdscr.addch(y, split_x, vline_char)
            except Exception:
                self._safe_addstr(stdscr, y, split_x, "│")

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

                # Row text layout
                prefix = f" {bullet} {name}"
                max_prefix_len = split_x - len(tok_str) - 3
                if len(prefix) > max_prefix_len:
                    prefix = prefix[:max_prefix_len - 1] + "…"

                spacing = max(1, split_x - len(prefix) - len(tok_str) - 1)
                full_row = (prefix + (" " * spacing) + tok_str).ljust(split_x)[:split_x]

                if is_selected:
                    # Inverted Cyan highlight across entire width
                    sel_attr = self._color(1, curses.A_BOLD) if self.has_colors else curses.A_REVERSE
                    self._safe_addstr(stdscr, y, 0, full_row, sel_attr)
                else:
                    # Unselected: draw bullet and text with proper colors
                    bullet_attr = (
                        self._color(3) if is_overridden
                        else self._color(2) if is_active
                        else self._color(9)
                    )

                    self._safe_addstr(stdscr, y, 0, " ")
                    self._safe_addstr(stdscr, y, 1, bullet, bullet_attr)
                    self._safe_addstr(stdscr, y, 3, name[:max_prefix_len - 3])
                    self._safe_addstr(stdscr, y, split_x - len(tok_str) - 1, tok_str, self._color(2))

        # Right pane rendering
        if selectable_items and 0 <= self.selected_index < len(selectable_items):
            selected_item = selectable_items[self.selected_index]
            self._draw_inspector_pane(stdscr, selected_item, split_x + 2, 2, max_x - split_x - 3, content_height)
        else:
            self._safe_addstr(stdscr, 3, split_x + 4, "No customizations matching this filter.", curses.A_DIM)

    def _draw_inspector_pane(
        self, stdscr, item: Any, start_x: int, start_y: int, width: int, height: int
    ) -> None:
        """Draw top metadata card box and rendered markdown preview below."""
        card_w = width - 2
        if card_w < 20:
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

        lines = body_raw.splitlines()

        # Render preview lines with scroll offset
        for p_idx in range(preview_height):
            line_idx = p_idx + self.detail_scroll
            if line_idx >= len(lines):
                break

            line_text = lines[line_idx]
            rendered_y = curr_y + p_idx

            trimmed = line_text[:card_w]
            attr = 0

            if trimmed.startswith("# "):
                attr = self._color(8, curses.A_BOLD)
            elif trimmed.startswith("## "):
                attr = self._color(2, curses.A_BOLD)
            elif trimmed.startswith("### "):
                attr = self._color(4, curses.A_BOLD)
            elif re.match(r"^\s*(\d+\.|\-|\*)\s+\*\*", trimmed):
                attr = self._color(6, curses.A_BOLD)
            elif trimmed.startswith("```"):
                attr = self._color(3)
            else:
                attr = self._color(6)

            self._safe_addstr(stdscr, rendered_y, start_x, trimmed, attr)

    def _draw_status_dashboard(self, stdscr, max_y: int, max_x: int) -> None:
        """Draw full status & context window health dashboard."""
        y = 3
        active_tokens = self.registry.get_total_active_tokens()
        budget = self.registry.token_budget
        pct = min(100.0, (active_tokens / budget) * 100.0) if budget > 0 else 0.0

        bar_len = min(40, max_x - 30)
        filled_len = int(round((pct / 100.0) * bar_len))
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

    def _draw_footer(self, stdscr, max_y: int, max_x: int) -> None:
        """Draw bottom shortcut bar."""
        footer_shortcuts = (
            "[1-7] Tabs  [m] Market  [↑/↓] Nav  [Space/i] Toggle/Install  [a/d] All/None  [Tab] Scope  [/] Filter  [q] Quit"
        )
        line = footer_shortcuts.ljust(max_x - 1)[:max_x - 1]
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

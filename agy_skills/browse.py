import os
import curses
import textwrap
from typing import List, Tuple, Optional, Dict
from .types import SkillInfo, ScopeContext
from .manager import SkillManager

class SkillBrowser:
    def __init__(self, manager: SkillManager):
        self.mgr = manager
        self.scope = manager.scope
        self.selected_idx = 0
        self.scroll_offset = 0
        self.preview_scroll = 0
        self.search_mode = False
        self.query = ""
        self.status_msg = ""
        self.target_scope = "workspace"  # or "shared", "global"
        self.preview_cache: Dict[str, List[Tuple[str, str]]] = {}

    def get_structured_items(self) -> List[Tuple[bool, str, Optional[SkillInfo], bool]]:
        """
        Returns list of (is_header, label, Optional[SkillInfo], is_active).
        Headers are unselectable visual anchors.
        """
        ws, shared, builtin, catalog = self.mgr.scan_all()
        q = self.query.strip().lower()

        def match(name: str, info: SkillInfo) -> bool:
            if not q:
                return True
            return q in name.lower() or q in info.description.lower()

        filtered_ws = [info for name, info in sorted(ws.items()) if match(name, info)]
        filtered_shared = [info for name, info in sorted(shared.items()) if match(name, info)]
        filtered_builtin = [info for name, info in sorted(builtin.items()) if match(name, info)]
        filtered_catalog = [info for name, info in sorted(catalog.items()) if match(name, info)]

        items: List[Tuple[bool, str, Optional[SkillInfo], bool]] = []

        if filtered_ws:
            items.append((True, f"── WORKSPACE ({len(filtered_ws)}) ──", None, False))
            for s in filtered_ws:
                items.append((False, s.name, s, True))

        if filtered_shared:
            items.append((True, f"── SHARED USER ({len(filtered_shared)}) ──", None, False))
            for s in filtered_shared:
                items.append((False, s.name, s, True))

        if filtered_builtin:
            items.append((True, f"── BUILT-IN ({len(filtered_builtin)}) ──", None, False))
            for s in filtered_builtin:
                items.append((False, s.name, s, True))

        if filtered_catalog:
            items.append((True, f"── CATALOG AVAILABLE ({len(filtered_catalog)}) ──", None, False))
            for s in filtered_catalog:
                items.append((False, s.name, s, False))

        return items

    def get_selectable_indices(self, items) -> List[int]:
        return [i for i, item in enumerate(items) if not item[0]]

    def load_skill_preview(self, info: SkillInfo, width: int) -> List[Tuple[str, str]]:
        """
        Returns list of (line_text, style_tag).
        Applies word wrapping to respect right pane width.
        """
        cache_key = f"{info.path}_{width}"
        if cache_key in self.preview_cache:
            return self.preview_cache[cache_key]

        out: List[Tuple[str, str]] = []

        # 1. Hero Card
        box_w = max(30, min(width - 2, 72))
        top_border = "┌" + "─" * (box_w - 2) + "┐"
        bot_border = "└" + "─" * (box_w - 2) + "┘"

        out.append((top_border, "border"))
        title_line = f"│  {info.name}"
        out.append((title_line.ljust(box_w - 1) + "│", "hero_title"))
        
        tier_str = f"│  Tier: {info.tier.upper()}"
        if info.is_symlink:
            tier_str += "  [🔗 Symlinked]"
        out.append((tier_str.ljust(box_w - 1) + "│", "hero_meta"))

        slash_str = f"│  Slash Trigger: /{info.name}"
        out.append((slash_str.ljust(box_w - 1) + "│", "hero_meta"))
        
        # Word wrap description in card
        desc_wrap = textwrap.wrap(info.description, width=box_w - 6)
        if desc_wrap:
            out.append(("│" + " " * (box_w - 2) + "│", "hero_meta"))
            for dw in desc_wrap:
                out.append((f"│  {dw}".ljust(box_w - 1) + "│", "hero_desc"))

        out.append((bot_border, "border"))
        out.append(("", "normal"))

        # 2. Body Runbook Preview
        try:
            with open(info.path, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.read().splitlines()

            # Frontmatter separation
            content_lines = []
            if raw_lines and raw_lines[0].strip() == "---":
                in_fm = True
                for i in range(1, len(raw_lines)):
                    if raw_lines[i].strip() == "---":
                        content_lines = raw_lines[i+1:]
                        break
            else:
                content_lines = raw_lines

            in_code_block = False
            wrap_w = max(24, width - 4)

            for line in content_lines:
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    out.append((f"  {line}", "code"))
                    continue

                if in_code_block:
                    out.append((f"  {line}", "code"))
                    continue

                if line.startswith("#"):
                    out.append((line, "heading"))
                elif line.startswith("- ") or line.startswith("* "):
                    bullet_text = line[2:]
                    wrapped = textwrap.wrap(bullet_text, width=wrap_w - 4)
                    if wrapped:
                        out.append((f"  • {wrapped[0]}", "bullet"))
                        for subw in wrapped[1:]:
                            out.append((f"    {subw}", "normal"))
                    else:
                        out.append(("  •", "bullet"))
                elif not stripped:
                    out.append(("", "normal"))
                else:
                    wrapped = textwrap.wrap(line, width=wrap_w)
                    for wl in wrapped:
                        out.append((wl, "normal"))

        except Exception as e:
            out.append((f"Error loading runbook: {e}", "error"))

        self.preview_cache[cache_key] = out
        return out

    def run(self):
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        stdscr.timeout(100)

        # Color pairs setup
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # Cyan / Active
        curses.init_pair(2, curses.COLOR_GREEN, -1)    # Green / Accent
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Yellow / Warning
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # Headers / Titles
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN) # Inverted selection
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE) # Brand header bar
        curses.init_pair(7, curses.COLOR_CYAN, -1)     # Dim borders

        while True:
            max_y, max_x = stdscr.getmaxyx()
            if max_y < 14 or max_x < 60:
                stdscr.clear()
                stdscr.addstr(0, 0, "Terminal window too small for agy-skills browser.")
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('q'), 27):
                    break
                continue

            items = self.get_structured_items()
            selectable = self.get_selectable_indices(items)

            if not selectable:
                selected_item_idx = -1
            else:
                if self.selected_idx >= len(selectable):
                    self.selected_idx = max(0, len(selectable) - 1)
                selected_item_idx = selectable[self.selected_idx]

            stdscr.clear()

            def safe_addstr(y, x, text, attr=0):
                if y < 0 or y >= max_y or x < 0 or x >= max_x:
                    return
                avail = max_x - x
                if y == max_y - 1:
                    avail = max(0, avail - 1)
                t = str(text)[:avail]
                if t:
                    try:
                        stdscr.addstr(y, x, t, attr)
                    except curses.error:
                        pass

            # 1. Header Bar
            proj_tag = f"WORKSPACE: {os.path.basename(self.scope.workspace_root) if self.scope.workspace_root else 'GLOBAL'}"
            header_left = f" ⚡ agy-skills browse  [{proj_tag}]"
            scope_badge = f"TARGET SCOPE: [{self.target_scope.upper()}] "
            padding = max(0, max_x - len(header_left) - len(scope_badge))
            full_header = header_left + (" " * padding) + scope_badge
            safe_addstr(0, 0, full_header[:max_x], curses.color_pair(6) | curses.A_BOLD)

            # Split geometry
            left_width = min(max(34, max_x // 3), 44)
            right_width = max_x - left_width - 1
            content_height = max_y - 3

            # Draw Vertical Divider
            for y in range(1, max_y - 2):
                if left_width < max_x:
                    try:
                        stdscr.addch(y, left_width, curses.ACS_VLINE, curses.color_pair(7) | curses.A_DIM)
                    except curses.error:
                        pass

            # 2. Render Left Pane (Categorized Tree)
            visible_rows = content_height
            if selected_item_idx != -1:
                if selected_item_idx < self.scroll_offset:
                    self.scroll_offset = selected_item_idx
                elif selected_item_idx >= self.scroll_offset + visible_rows:
                    self.scroll_offset = selected_item_idx - visible_rows + 1

            row = 1
            for idx in range(self.scroll_offset, min(len(items), self.scroll_offset + visible_rows)):
                is_header, label, info, is_active = items[idx]

                if is_header:
                    safe_addstr(row, 1, label[:left_width-2], curses.color_pair(4) | curses.A_BOLD)
                else:
                    is_selected = (idx == selected_item_idx)
                    bullet = "●" if is_active else "○"
                    symlink_tag = "🔗 " if (info and info.is_symlink) else ""
                    color = curses.color_pair(1) if is_active else curses.A_DIM

                    line_str = f"  {bullet} {symlink_tag}{info.name if info else label}"
                    line_str = line_str[:left_width-1].ljust(left_width-1)

                    if is_selected:
                        safe_addstr(row, 0, line_str, curses.color_pair(5) | curses.A_BOLD)
                    else:
                        safe_addstr(row, 0, line_str, color)

                row += 1

            # 3. Render Right Pane (Hero Card + Markdown Preview)
            if selected_item_idx != -1 and items[selected_item_idx][2]:
                selected_info = items[selected_item_idx][2]
                preview_lines = self.load_skill_preview(selected_info, right_width)

                p_row = 1
                for p_idx in range(self.preview_scroll, min(len(preview_lines), self.preview_scroll + visible_rows)):
                    text, style = preview_lines[p_idx]
                    ptext = text[:right_width-1]
                    px = left_width + 2

                    if style == "border":
                        safe_addstr(p_row, px, ptext, curses.color_pair(7) | curses.A_DIM)
                    elif style == "hero_title":
                        safe_addstr(p_row, px, ptext, curses.color_pair(2) | curses.A_BOLD)
                    elif style == "hero_meta":
                        safe_addstr(p_row, px, ptext, curses.color_pair(1))
                    elif style == "hero_desc":
                        safe_addstr(p_row, px, ptext, curses.A_BOLD)
                    elif style == "heading":
                        safe_addstr(p_row, px, ptext, curses.color_pair(4) | curses.A_BOLD)
                    elif style == "bullet":
                        safe_addstr(p_row, px, ptext, curses.color_pair(1))
                    elif style == "code":
                        safe_addstr(p_row, px, ptext, curses.A_DIM)
                    elif style == "error":
                        safe_addstr(p_row, px, ptext, curses.color_pair(3))
                    else:
                        safe_addstr(p_row, px, ptext)

                    p_row += 1

                # Preview Scroll Indicator if overflowing
                total_p = len(preview_lines)
                if total_p > visible_rows:
                    pct = int((self.preview_scroll / max(1, total_p - visible_rows)) * 100)
                    scroll_tag = f" {pct}% "
                    safe_addstr(1, max_x - len(scroll_tag) - 2, scroll_tag, curses.color_pair(7) | curses.A_BOLD)

            # 4. Status and Prompt Footer
            footer_y = max_y - 2
            help_y = max_y - 1

            if self.search_mode:
                prompt = f" 🔍 Filter: /{self.query}█"
                safe_addstr(footer_y, 0, prompt.ljust(max_x), curses.color_pair(3) | curses.A_BOLD)
            elif self.status_msg:
                safe_addstr(footer_y, 0, f"  {self.status_msg}".ljust(max_x), curses.color_pair(2) | curses.A_BOLD)
            else:
                safe_addstr(footer_y, 0, " " * (max_x - 1))

            help_bar = " [↑/↓] Nav  [Space/Enter] Toggle  [Tab] Scope  [/] Filter  [J/K] Scroll  [q] Quit"
            safe_addstr(help_y, 0, help_bar.ljust(max_x), curses.A_DIM)

            stdscr.refresh()

            # Handle Input
            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                break

            if ch == -1:
                continue

            # In Search Input Mode
            if self.search_mode:
                if ch in (10, 13):  # Enter
                    self.search_mode = False
                elif ch == 27:      # Escape
                    self.search_mode = False
                    self.query = ""
                    self.selected_idx = 0
                    self.preview_scroll = 0
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    self.query = self.query[:-1]
                    self.selected_idx = 0
                    self.preview_scroll = 0
                elif 32 <= ch <= 126:
                    self.query += chr(ch)
                    self.selected_idx = 0
                    self.preview_scroll = 0
                continue

            # Standard Navigation Mode
            if ch in (ord('q'), 27): # q or Esc
                break

            elif ch in (curses.KEY_UP, ord('k')):
                if self.selected_idx > 0:
                    self.selected_idx -= 1
                    self.preview_scroll = 0

            elif ch in (curses.KEY_DOWN, ord('j')):
                if self.selected_idx < len(selectable) - 1:
                    self.selected_idx += 1
                    self.preview_scroll = 0

            elif ch == ord('K'):  # Shift-K scroll preview up
                self.preview_scroll = max(0, self.preview_scroll - 4)

            elif ch == ord('J'):  # Shift-J scroll preview down
                self.preview_scroll += 4

            elif ch == ord('\t'):  # Tab switches target scope
                scopes = ["workspace", "shared", "global"]
                curr_idx = scopes.index(self.target_scope)
                self.target_scope = scopes[(curr_idx + 1) % len(scopes)]
                self.status_msg = f"Target activation scope set to: {self.target_scope.upper()}"

            elif ch == ord('/'):
                self.search_mode = True
                self.status_msg = ""

            elif ch in (ord(' '), 10, 13):  # Space or Enter: Toggle enable/disable
                if selected_item_idx != -1 and items[selected_item_idx][2]:
                    sel_info = items[selected_item_idx][2]
                    _, _, _, is_active = items[selected_item_idx]

                    if is_active:
                        if sel_info.tier == "builtin":
                            self.status_msg = f"Built-in skill '{sel_info.name}' is immutable."
                        else:
                            ok, msg = self.mgr.disable(sel_info.name, target_tier=sel_info.tier)
                            self.status_msg = msg
                            self.preview_cache.clear()
                    else:
                        ok, msg = self.mgr.enable(sel_info.name, target_tier=self.target_scope)
                        self.status_msg = msg
                        self.preview_cache.clear()

def open_browser():
    from .scope import resolve_scope
    scope = resolve_scope()
    mgr = SkillManager(scope)
    browser = SkillBrowser(mgr)
    browser.run()

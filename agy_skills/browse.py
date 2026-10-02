import os
import curses
from typing import List, Tuple, Optional
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
        self.preview_cache = {}

    def get_items(self) -> List[Tuple[str, SkillInfo, bool]]:
        """
        Returns flat list of (category_label, skill_info, is_active).
        Applies filter if query is present.
        """
        ws, shared, builtin, catalog = self.mgr.scan_all()
        items = []

        q = self.query.strip().lower()

        # Workspace
        for name, info in sorted(ws.items()):
            if not q or q in name.lower() or q in info.description.lower():
                items.append(("Workspace", info, True))

        # Shared
        for name, info in sorted(shared.items()):
            if not q or q in name.lower() or q in info.description.lower():
                items.append(("Shared", info, True))

        # Builtin
        for name, info in sorted(builtin.items()):
            if not q or q in name.lower() or q in info.description.lower():
                items.append(("Builtin", info, True))

        # Catalog
        for name, info in sorted(catalog.items()):
            if not q or q in name.lower() or q in info.description.lower():
                items.append(("Catalog", info, False))

        return items

    def load_skill_preview(self, info: SkillInfo) -> List[str]:
        if info.path in self.preview_cache:
            return self.preview_cache[info.path]

        lines = [
            f"Name: {info.name}",
            f"Tier: {info.tier.upper()}  |  Path: {info.path}",
        ]
        if info.is_symlink:
            target = os.path.realpath(info.path)
            lines.append(f"Symlink -> {target}")
        lines.append(f"Description: {info.description}")
        lines.append("-" * 60)

        try:
            with open(info.path, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.read().splitlines()

            # Frontmatter separation
            in_fm = False
            fm_lines = []
            content_lines = []
            
            if raw_lines and raw_lines[0].strip() == "---":
                in_fm = True
                for i in range(1, len(raw_lines)):
                    if raw_lines[i].strip() == "---":
                        content_lines = raw_lines[i+1:]
                        break
                    fm_lines.append(raw_lines[i])
            else:
                content_lines = raw_lines

            for l in content_lines:
                lines.append(l)

        except Exception as e:
            lines.append(f"(Could not load content: {e})")

        self.preview_cache[info.path] = lines
        return lines

    def run(self):
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        stdscr.timeout(100)

        # Color pairs setup
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # Cyan / Active
        curses.init_pair(2, curses.COLOR_GREEN, -1)    # Green / Success
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Yellow / Warning
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # Headers
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN) # Inverted selection
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE) # Title bar

        while True:
            max_y, max_x = stdscr.getmaxyx()
            if max_y < 12 or max_x < 50:
                stdscr.clear()
                stdscr.addstr(0, 0, "Terminal window too small for agy-skills browser.")
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('q'), 27):
                    break
                continue

            items = self.get_items()
            if self.selected_idx >= len(items):
                self.selected_idx = max(0, len(items) - 1)

            # Draw layout
            stdscr.clear()

            # 1. Header Bar
            header_text = f" agy-skills browse · Scope: {self.target_scope.upper()} · {len(items)} skills"
            stdscr.attron(curses.color_pair(6) | curses.A_BOLD)
            stdscr.addstr(0, 0, header_text.ljust(max_x)[:max_x])
            stdscr.attroff(curses.color_pair(6) | curses.A_BOLD)

            # Split geometry
            left_width = min(max(34, max_x // 3), 48)
            right_width = max_x - left_width - 1
            content_height = max_y - 3

            # Draw Vertical Divider
            for y in range(1, max_y - 2):
                stdscr.addch(y, left_width, curses.ACS_VLINE)

            # 2. Render Left Pane (List)
            current_category = None
            row = 1
            visible_rows = content_height

            # Keep selected_idx in view
            if self.selected_idx < self.scroll_offset:
                self.scroll_offset = self.selected_idx
            elif self.selected_idx >= self.scroll_offset + visible_rows:
                self.scroll_offset = self.selected_idx - visible_rows + 1

            for idx in range(self.scroll_offset, min(len(items), self.scroll_offset + visible_rows)):
                cat, info, is_active = items[idx]
                is_selected = (idx == self.selected_idx)
                bullet = "●" if is_active else "○"
                color = curses.color_pair(1) if is_active else curses.A_DIM

                line_str = f" {bullet} {info.name}"
                line_str = line_str[:left_width-1].ljust(left_width-1)

                if is_selected:
                    stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
                    stdscr.addstr(row, 0, line_str)
                    stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
                else:
                    stdscr.attron(color)
                    stdscr.addstr(row, 0, line_str)
                    stdscr.attroff(color)

                row += 1

            # 3. Render Right Pane (Preview)
            if items and self.selected_idx < len(items):
                _, selected_info, _ = items[self.selected_idx]
                preview_lines = self.load_skill_preview(selected_info)
                p_row = 1
                for p_idx in range(self.preview_scroll, min(len(preview_lines), self.preview_scroll + visible_rows)):
                    pline = preview_lines[p_idx][:right_width-1]
                    if pline.startswith("#"):
                        stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
                        stdscr.addstr(p_row, left_width + 1, pline)
                        stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
                    elif pline.startswith("Name:") or pline.startswith("Tier:"):
                        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                        stdscr.addstr(p_row, left_width + 1, pline)
                        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                    elif pline.startswith("Description:"):
                        stdscr.attron(curses.A_BOLD)
                        stdscr.addstr(p_row, left_width + 1, pline)
                        stdscr.attroff(curses.A_BOLD)
                    elif pline.startswith("-"):
                        stdscr.attron(curses.A_DIM)
                        stdscr.addstr(p_row, left_width + 1, pline)
                        stdscr.attroff(curses.A_DIM)
                    else:
                        stdscr.addstr(p_row, left_width + 1, pline)
                    p_row += 1

            # 4. Status and Prompt Footer
            footer_y = max_y - 2
            help_y = max_y - 1

            if self.search_mode:
                prompt = f"Search: /{self.query}"
                stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                stdscr.addstr(footer_y, 0, prompt.ljust(max_x)[:max_x])
                stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            elif self.status_msg:
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                stdscr.addstr(footer_y, 0, f" {self.status_msg}".ljust(max_x)[:max_x])
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            else:
                stdscr.addstr(footer_y, 0, " " * max_x)

            help_bar = " ↑/↓:Nav · Space/Enter:Toggle · Tab:Scope · /:Find · J/K:Scroll · q:Quit"
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(help_y, 0, help_bar.ljust(max_x)[:max_x])
            stdscr.attroff(curses.A_DIM)

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
                if self.selected_idx < len(items) - 1:
                    self.selected_idx += 1
                    self.preview_scroll = 0

            elif ch == ord('K'):  # Shift-K scroll preview up
                self.preview_scroll = max(0, self.preview_scroll - 3)

            elif ch == ord('J'):  # Shift-J scroll preview down
                self.preview_scroll += 3

            elif ch == ord('\t'):  # Tab switches target scope
                scopes = ["workspace", "shared", "global"]
                curr_idx = scopes.index(self.target_scope)
                self.target_scope = scopes[(curr_idx + 1) % len(scopes)]
                self.status_msg = f"Target activation scope set to: {self.target_scope.upper()}"

            elif ch == ord('/'):
                self.search_mode = True
                self.status_msg = ""

            elif ch in (ord(' '), 10, 13):  # Space or Enter: Toggle enable/disable
                if items and self.selected_idx < len(items):
                    _, sel_info, is_active = items[self.selected_idx]
                    if is_active:
                        if sel_info.tier == "builtin":
                            self.status_msg = f"Built-in skill '{sel_info.name}' is always active."
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

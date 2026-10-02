import os
import curses
import textwrap
from typing import List, Tuple, Optional, Dict, Any
from .types import SkillInfo, RuleInfo, SubagentInfo, ScopeContext, ContextBudget
from .manager import SkillManager

TAB_SKILLS = 0
TAB_RULES = 1
TAB_SUBAGENTS = 2
TAB_PLUGINS = 3

class SkillBrowser:
    def __init__(self, manager: SkillManager):
        self.mgr = manager
        self.scope = manager.scope
        self.active_tab = TAB_SKILLS
        self.selected_idx = 0
        self.scroll_offset = 0
        self.preview_scroll = 0
        self.search_mode = False
        self.query = ""
        self.status_msg = ""
        self.target_scope = "workspace"  # or "shared", "global"
        self.preview_cache: Dict[str, List[Tuple[str, str]]] = {}

        # Mini Editor State
        self.edit_mode = False
        self.edit_lines: List[str] = []
        self.edit_cur_y = 0
        self.edit_cur_x = 0
        self.edit_scroll_y = 0
        self.edit_scroll_x = 0
        self.edit_target_info: Optional[Any] = None
        self.edit_target_type: str = ""
        self.edit_dirty = False
        self.save_modal = False
        self.save_prompt_mode = ""  # "save_or_fork"

    def get_items_for_current_tab(self) -> List[Tuple[bool, str, Optional[Any], bool, str]]:
        q = self.query.strip().lower()

        if self.active_tab == TAB_SKILLS:
            ws, shared, builtin, catalog = self.mgr.scan_all()
            def match(s: SkillInfo) -> bool:
                return not q or q in s.name.lower() or q in s.description.lower()

            f_ws = [s for s in sorted(ws.values(), key=lambda x: x.name) if match(s)]
            f_shared = [s for s in sorted(shared.values(), key=lambda x: x.name) if match(s)]
            f_builtin = [s for s in sorted(builtin.values(), key=lambda x: x.name) if match(s)]
            f_cat = [s for s in sorted(catalog.values(), key=lambda x: x.name) if match(s)]

            items = []
            if f_ws:
                items.append((True, f"── WORKSPACE ({len(f_ws)}) ──", None, False, "skill"))
                for s in f_ws:
                    items.append((False, s.name, s, True, "skill"))
            if f_shared:
                items.append((True, f"── SHARED USER ({len(f_shared)}) ──", None, False, "skill"))
                for s in f_shared:
                    items.append((False, s.name, s, True, "skill"))
            if f_builtin:
                items.append((True, f"── BUILT-IN ({len(f_builtin)}) ──", None, False, "skill"))
                for s in f_builtin:
                    items.append((False, s.name, s, True, "skill"))
            if f_cat:
                items.append((True, f"── CATALOG AVAILABLE ({len(f_cat)}) ──", None, False, "skill"))
                for s in f_cat:
                    items.append((False, s.name, s, False, "skill"))
            return items

        elif self.active_tab == TAB_RULES:
            active, available = self.mgr.scan_rules()
            def match_r(r: RuleInfo) -> bool:
                return not q or q in r.name.lower() or q in r.description.lower()

            f_active = [r for r in sorted(active.values(), key=lambda x: x.name) if match_r(r)]
            f_avail = [r for r in sorted(available.values(), key=lambda x: x.name) if match_r(r)]

            items = []
            if f_active:
                items.append((True, f"── ACTIVE RULES ({len(f_active)}) ──", None, False, "rule"))
                for r in f_active:
                    items.append((False, r.name, r, True, "rule"))
            if f_avail:
                items.append((True, f"── AVAILABLE RULES ({len(f_avail)}) ──", None, False, "rule"))
                for r in f_avail:
                    items.append((False, r.name, r, False, "rule"))
            return items

        elif self.active_tab == TAB_SUBAGENTS:
            active, available = self.mgr.scan_subagents()
            def match_a(a: SubagentInfo) -> bool:
                return not q or q in a.name.lower() or q in a.description.lower() or q in a.role.lower()

            f_active = [a for a in sorted(active.values(), key=lambda x: x.name) if match_a(a)]
            f_avail = [a for a in sorted(available.values(), key=lambda x: x.name) if match_a(a)]

            items = []
            if f_active:
                items.append((True, f"── ACTIVE SUBAGENTS ({len(f_active)}) ──", None, False, "subagent"))
                for a in f_active:
                    items.append((False, a.name, a, True, "subagent"))
            if f_avail:
                items.append((True, f"── AVAILABLE SUBAGENTS ({len(f_avail)}) ──", None, False, "subagent"))
                for a in f_avail:
                    items.append((False, a.name, a, False, "subagent"))
            return items

        elif self.active_tab == TAB_PLUGINS:
            ws, shared, builtin, catalog = self.mgr.scan_all()
            all_skills = {**ws, **shared, **builtin, **catalog}
            rules_active, rules_avail = self.mgr.scan_rules()
            all_rules = {**rules_active, **rules_avail}

            collections: Dict[str, List[Tuple[Any, bool, str]]] = {}

            for s in all_skills.values():
                coll = s.collection
                collections.setdefault(coll, [])
                is_active = (s.tier in ("workspace", "shared", "builtin"))
                collections[coll].append((s, is_active, "skill"))

            for r in all_rules.values():
                coll = r.collection
                collections.setdefault(coll, [])
                is_active = (r.tier in ("workspace", "global"))
                collections[coll].append((r, is_active, "rule"))

            items = []
            for coll_name in sorted(collections.keys()):
                group_items = collections[coll_name]
                active_count = sum(1 for _, is_act, _ in group_items if is_act)
                items.append((True, f"📦 {coll_name} ({active_count}/{len(group_items)} active) [a:All d:None]", None, False, "plugin"))
                for obj, is_act, itype in sorted(group_items, key=lambda x: x[0].name):
                    items.append((False, obj.name, obj, is_act, itype))
            return items

        return []

    def get_selectable_indices(self, items) -> List[int]:
        return [i for i, item in enumerate(items) if not item[0]]

    def load_item_preview(self, info: Any, itype: str, width: int) -> List[Tuple[str, str]]:
        cache_key = f"{info.path}_{width}_{itype}"
        if cache_key in self.preview_cache:
            return self.preview_cache[cache_key]

        out: List[Tuple[str, str]] = []
        box_w = max(30, min(width - 4, 76))
        top_border = "┌" + "─" * (box_w - 2) + "┐"
        bot_border = "└" + "─" * (box_w - 2) + "┘"

        out.append((top_border, "border"))
        title_content = f"  {info.name}"
        out.append((f"│{title_content.ljust(box_w - 2)}│", "hero_title"))
        
        sym_status = " [active link]" if info.is_symlink else ""
        meta_1 = f"  Type: {itype.upper()} · Tier: {info.tier.upper()} · Tokens: ~{info.token_cost}{sym_status}"
        out.append((f"│{meta_1.ljust(box_w - 2)}│", "hero_meta"))

        if itype == "skill":
            meta_2 = f"  Slash Trigger: /{info.name}  [Press 'e' to Edit in Nano]"
            out.append((f"│{meta_2.ljust(box_w - 2)}│", "hero_meta"))
        elif itype == "rule":
            status_str = "ALWAYS-ON" if getattr(info, "is_always_on", False) else "CONDITIONAL"
            meta_2 = f"  Rule Mode: {status_str}  [Press 'e' to Edit in Nano]"
            out.append((f"│{meta_2.ljust(box_w - 2)}│", "hero_meta"))
        elif itype == "subagent":
            meta_2 = f"  Role: {getattr(info, 'role', 'Worker')}  [Press 'e' to Edit in Nano]"
            out.append((f"│{meta_2.ljust(box_w - 2)}│", "hero_meta"))

        desc = getattr(info, "description", "")
        desc_wrap = textwrap.wrap(desc, width=box_w - 6)
        if desc_wrap:
            out.append((f"│{' ' * (box_w - 2)}│", "hero_meta"))
            for dw in desc_wrap:
                line_content = f"  {dw}"
                out.append((f"│{line_content.ljust(box_w - 2)}│", "hero_desc"))

        out.append((bot_border, "border"))
        out.append(("", "normal"))

        try:
            with open(info.path, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.read().splitlines()

            content_lines = []
            if raw_lines and raw_lines[0].strip() == "---":
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
            out.append((f"Error loading file: {e}", "error"))

        self.preview_cache[cache_key] = out
        return out

    def enter_edit_mode(self, info: Any, itype: str):
        if not info or not os.path.isfile(info.path):
            self.status_msg = "Cannot edit: source file not found."
            return
        try:
            with open(info.path, "r", encoding="utf-8", errors="replace") as f:
                self.edit_lines = f.read().splitlines()
            if not self.edit_lines:
                self.edit_lines = [""]
            self.edit_mode = True
            self.edit_target_info = info
            self.edit_target_type = itype
            self.edit_cur_y = 0
            self.edit_cur_x = 0
            self.edit_scroll_y = 0
            self.edit_scroll_x = 0
            self.edit_dirty = False
            self.save_modal = False
            self.status_msg = f"Nano Editor: editing {info.name}"
        except Exception as e:
            self.status_msg = f"Failed to open editor: {e}"

    def write_out_file(self, fork: bool = False) -> Tuple[bool, str]:
        if not self.edit_target_info:
            return False, "No active target file."

        content = "\n".join(self.edit_lines) + "\n"

        if fork:
            # Fork into workspace as <name>-user/SKILL.md
            base_dir = self.scope.workspace_skills_dir if self.edit_target_type == "skill" else self.scope.workspace_rules_dir
            fork_name = f"{self.edit_target_info.name}-user"
            os.makedirs(base_dir, exist_ok=True)
            if self.edit_target_type == "skill":
                target_dir = os.path.join(base_dir, fork_name)
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, "SKILL.md")
            else:
                target_path = os.path.join(base_dir, f"{fork_name}.md")

            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.edit_dirty = False
                self.preview_cache.clear()
                return True, f"✅ Forked as '{fork_name}' at {target_path}"
            except Exception as e:
                return False, f"Failed to fork: {e}"
        else:
            # Save in place
            target_path = self.edit_target_info.path
            # If target_path is a symlink, write directly to realpath
            real_path = os.path.realpath(target_path)
            try:
                with open(real_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.edit_dirty = False
                self.preview_cache.clear()
                return True, f"✅ Saved in place to {real_path}"
            except Exception as e:
                return False, f"Failed to save: {e}"

    def run(self):
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        curses.use_default_colors()
        stdscr.timeout(-1)

        # Color pairs setup
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # Cyan / Active
        curses.init_pair(2, curses.COLOR_GREEN, -1)    # Green / Accent
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Yellow / Warning
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # Headers / Titles
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN) # Inverted selection
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE) # Brand header bar
        curses.init_pair(7, curses.COLOR_CYAN, -1)     # Dim borders
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE) # Nano status deck

        while True:
            max_y, max_x = stdscr.getmaxyx()
            if max_y < 14 or max_x < 65:
                stdscr.erase()
                stdscr.addstr(0, 0, "Terminal window too small for agy-skills browser.")
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('q'), 27):
                    break
                continue

            budget = self.mgr.calculate_budget()
            items = self.get_items_for_current_tab()
            selectable = self.get_selectable_indices(items)

            if not selectable:
                selected_item_idx = -1
            else:
                if self.selected_idx >= len(selectable):
                    self.selected_idx = max(0, len(selectable) - 1)
                selected_item_idx = selectable[self.selected_idx]

            stdscr.erase()

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

            # 1. Header Bar with Budget Gauge
            filled_blocks = int((budget.percentage / 100.0) * 10)
            gauge = "█" * filled_blocks + "░" * (10 - filled_blocks)
            budget_str = f"Context: [{gauge}] {budget.total_tokens:,}/{budget.max_tokens:,} tok ({budget.percentage:.1f}%)"
            
            proj_name = os.path.basename(self.scope.workspace_root) if self.scope.workspace_root else "GLOBAL"
            mode_tag = " [NANO EDIT MODE]" if self.edit_mode else ""
            header_left = f" ⚡ agy-skills [{proj_name}]{mode_tag}"
            padding = max(0, max_x - len(header_left) - len(budget_str) - 2)
            full_header = header_left + (" " * padding) + budget_str + " "
            safe_addstr(0, 0, full_header[:max_x], curses.color_pair(6) | curses.A_BOLD)

            # 2. Tab Navigation Bar
            tab_labels = ["1: Skills", "2: Rules", "3: Subagents", "4: Plugins"]
            tab_bar = " "
            for i, label in enumerate(tab_labels):
                if i == self.active_tab:
                    tab_bar += f" [{label}] "
                else:
                    tab_bar += f"  {label}  "
            
            tab_bar_padded = tab_bar.ljust(max_x - 22) + f"TARGET: [{self.target_scope.upper()}] "
            safe_addstr(1, 0, tab_bar_padded[:max_x], curses.A_BOLD)

            # Split geometry: allow comfortable room for long skill names
            left_width = min(max(44, max_x // 3 + 4), 54)
            right_width = max_x - left_width - 1
            content_height = max_y - 4

            # Draw Vertical Divider
            for y in range(1, max_y - 2):
                if left_width < max_x:
                    try:
                        stdscr.addch(y, left_width, curses.ACS_VLINE, curses.color_pair(7) | curses.A_DIM)
                    except curses.error:
                        pass

            # 3. Render Left Pane (Items & Headers)
            visible_rows = content_height
            if selected_item_idx != -1:
                if selected_item_idx < self.scroll_offset:
                    self.scroll_offset = selected_item_idx
                elif selected_item_idx >= self.scroll_offset + visible_rows:
                    self.scroll_offset = selected_item_idx - visible_rows + 1

            row = 2
            for idx in range(self.scroll_offset, min(len(items), self.scroll_offset + visible_rows)):
                is_header, label, info, is_active, itype = items[idx]

                if is_header:
                    safe_addstr(row, 1, label[:left_width-2], curses.color_pair(4) | curses.A_BOLD)
                else:
                    is_selected = (idx == selected_item_idx)
                    bullet = "●" if is_active else "○"
                    symlink_tag = "⇄ " if (info and getattr(info, "is_symlink", False)) else ""
                    color = curses.color_pair(1) if is_active else curses.A_DIM

                    tok_tag = f" ~{info.token_cost}t" if info else ""
                    avail_name_w = left_width - len(tok_tag) - len(symlink_tag) - 6
                    item_name = info.name if info else label
                    disp_name = item_name[:avail_name_w]

                    line_str = f"  {bullet} {symlink_tag}{disp_name}".ljust(left_width - len(tok_tag) - 1) + tok_tag

                    if is_selected:
                        safe_addstr(row, 0, line_str, curses.color_pair(5) | curses.A_BOLD)
                    else:
                        safe_addstr(row, 0, line_str, color)

                row += 1

            # 4. Render Right Pane (Preview vs Nano Mini-Editor)
            if self.edit_mode:
                curses.curs_set(1)  # Show cursor in editor
                # Keep cursor in view
                if self.edit_cur_y < self.edit_scroll_y:
                    self.edit_scroll_y = self.edit_cur_y
                elif self.edit_cur_y >= self.edit_scroll_y + visible_rows:
                    self.edit_scroll_y = self.edit_cur_y - visible_rows + 1

                e_row = 2
                for line_idx in range(self.edit_scroll_y, min(len(self.edit_lines), self.edit_scroll_y + visible_rows)):
                    raw_l = self.edit_lines[line_idx]
                    display_l = raw_l[self.edit_scroll_x:self.edit_scroll_x + right_width - 1]
                    safe_addstr(e_row, left_width + 2, display_l)
                    e_row += 1

                # Place hardware cursor
                screen_cur_y = 2 + (self.edit_cur_y - self.edit_scroll_y)
                screen_cur_x = left_width + 2 + (self.edit_cur_x - self.edit_scroll_x)
                if 2 <= screen_cur_y < max_y - 2 and left_width + 2 <= screen_cur_x < max_x:
                    stdscr.move(screen_cur_y, screen_cur_x)

            else:
                curses.curs_set(0)  # Hide cursor in browse mode
                if selected_item_idx != -1 and items[selected_item_idx][2]:
                    selected_info = items[selected_item_idx][2]
                    itype = items[selected_item_idx][4]
                    preview_lines = self.load_item_preview(selected_info, itype, right_width)

                    p_row = 2
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

                    # Only show scroll percentage if content actually overflows
                    total_p = len(preview_lines)
                    if total_p > visible_rows and self.preview_scroll > 0:
                        pct = int((self.preview_scroll / max(1, total_p - visible_rows)) * 100)
                        scroll_tag = f" {pct}% "
                        safe_addstr(1, max_x - len(scroll_tag) - 2, scroll_tag, curses.color_pair(7) | curses.A_BOLD)

            # 5. Status and Action Deck
            footer_y = max_y - 2
            help_y = max_y - 1

            if self.save_modal:
                prompt = " ^O WriteOut: [Enter/S] Save In-Place  |  [F] Fork as '(user)'  |  [Esc/C] Cancel"
                safe_addstr(footer_y, 0, prompt.ljust(max_x), curses.color_pair(3) | curses.A_BOLD)
                safe_addstr(help_y, 0, " Choose destination...".ljust(max_x), curses.A_DIM)

            elif self.edit_mode:
                dirty_tag = " [Modified]" if self.edit_dirty else ""
                cur_pos = f"Line {self.edit_cur_y + 1}/{len(self.edit_lines)} Col {self.edit_cur_x + 1}"
                status_bar = f"  NANO: {self.edit_target_info.name}{dirty_tag}  ·  {cur_pos}"
                safe_addstr(footer_y, 0, status_bar.ljust(max_x), curses.color_pair(2) | curses.A_BOLD)

                nano_help = " ^O WriteOut (Save/Fork)   ^X Exit   ^K Cut Line   ^U Paste   Arrows/Typing"
                safe_addstr(help_y, 0, nano_help.ljust(max_x), curses.color_pair(8))

            elif self.search_mode:
                prompt = f" 🔍 Filter: /{self.query}█"
                safe_addstr(footer_y, 0, prompt.ljust(max_x), curses.color_pair(3) | curses.A_BOLD)
                safe_addstr(help_y, 0, " Type search string... Press Enter to confirm, Esc to cancel".ljust(max_x), curses.A_DIM)
            elif self.status_msg:
                safe_addstr(footer_y, 0, f"  {self.status_msg}".ljust(max_x), curses.color_pair(2) | curses.A_BOLD)
                help_bar = " [1-4] Tabs  [↑/↓] Nav  [Space] Toggle  [e] Edit in Nano  [Tab] Scope  [/] Filter  [q] Quit"
                safe_addstr(help_y, 0, help_bar.ljust(max_x), curses.A_DIM)
            else:
                safe_addstr(footer_y, 0, " " * (max_x - 1))
                help_bar = " [1-4] Tabs  [↑/↓] Nav  [Space] Toggle  [e] Edit in Nano  [Tab] Scope  [/] Filter  [q] Quit"
                safe_addstr(help_y, 0, help_bar.ljust(max_x), curses.A_DIM)

            stdscr.refresh()

            # Handle Input
            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                break

            if ch == -1:
                continue

            # In Save Modal
            if self.save_modal:
                if ch in (10, 13, ord('s'), ord('S'), ord('y'), ord('Y')):
                    ok, msg = self.write_out_file(fork=False)
                    self.status_msg = msg
                    self.save_modal = False
                elif ch in (ord('f'), ord('F')):
                    ok, msg = self.write_out_file(fork=True)
                    self.status_msg = msg
                    self.save_modal = False
                elif ch in (27, ord('c'), ord('C'), 3):  # Esc or Ctrl+C
                    self.save_modal = False
                    self.status_msg = "Save cancelled."
                continue

            # In Nano Edit Mode
            if self.edit_mode:
                # Ctrl+O: Save / Fork dialog
                if ch in (15,):  # Ctrl+O
                    self.save_modal = True
                    continue

                # Ctrl+X: Exit editor
                elif ch in (24,):  # Ctrl+X
                    if self.edit_dirty:
                        self.save_modal = True
                    else:
                        self.edit_mode = False
                        self.status_msg = f"Closed editor for {self.edit_target_info.name}."
                    continue

                # Navigation
                elif ch == curses.KEY_UP:
                    if self.edit_cur_y > 0:
                        self.edit_cur_y -= 1
                        self.edit_cur_x = min(self.edit_cur_x, len(self.edit_lines[self.edit_cur_y]))
                elif ch == curses.KEY_DOWN:
                    if self.edit_cur_y < len(self.edit_lines) - 1:
                        self.edit_cur_y += 1
                        self.edit_cur_x = min(self.edit_cur_x, len(self.edit_lines[self.edit_cur_y]))
                elif ch == curses.KEY_LEFT:
                    if self.edit_cur_x > 0:
                        self.edit_cur_x -= 1
                    elif self.edit_cur_y > 0:
                        self.edit_cur_y -= 1
                        self.edit_cur_x = len(self.edit_lines[self.edit_cur_y])
                elif ch == curses.KEY_RIGHT:
                    if self.edit_cur_x < len(self.edit_lines[self.edit_cur_y]):
                        self.edit_cur_x += 1
                    elif self.edit_cur_y < len(self.edit_lines) - 1:
                        self.edit_cur_y += 1
                        self.edit_cur_x = 0

                # Backspace
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    curr_l = self.edit_lines[self.edit_cur_y]
                    if self.edit_cur_x > 0:
                        self.edit_lines[self.edit_cur_y] = curr_l[:self.edit_cur_x - 1] + curr_l[self.edit_cur_x:]
                        self.edit_cur_x -= 1
                        self.edit_dirty = True
                    elif self.edit_cur_y > 0:
                        prev_l = self.edit_lines[self.edit_cur_y - 1]
                        self.edit_cur_x = len(prev_l)
                        self.edit_lines[self.edit_cur_y - 1] = prev_l + curr_l
                        del self.edit_lines[self.edit_cur_y]
                        self.edit_cur_y -= 1
                        self.edit_dirty = True

                # Enter / Newline
                elif ch in (10, 13):
                    curr_l = self.edit_lines[self.edit_cur_y]
                    left = curr_l[:self.edit_cur_x]
                    right = curr_l[self.edit_cur_x:]
                    self.edit_lines[self.edit_cur_y] = left
                    self.edit_lines.insert(self.edit_cur_y + 1, right)
                    self.edit_cur_y += 1
                    self.edit_cur_x = 0
                    self.edit_dirty = True

                # Normal characters
                elif 32 <= ch <= 126 or ch == 9:  # printable or tab
                    insert_char = "    " if ch == 9 else chr(ch)
                    curr_l = self.edit_lines[self.edit_cur_y]
                    self.edit_lines[self.edit_cur_y] = curr_l[:self.edit_cur_x] + insert_char + curr_l[self.edit_cur_x:]
                    self.edit_cur_x += len(insert_char)
                    self.edit_dirty = True

                continue

            # In Search Input Mode
            if self.search_mode:
                if ch in (10, 13):
                    self.search_mode = False
                elif ch == 27:
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
            if ch in (ord('1'), ord('2'), ord('3'), ord('4')):
                self.active_tab = ch - ord('1')
                self.selected_idx = 0
                self.scroll_offset = 0
                self.preview_scroll = 0
                continue

            if ch in (ord('q'), 27):
                break

            elif ch == ord('e'):  # Enter nano editor
                if selected_item_idx != -1 and items[selected_item_idx][2]:
                    sel_info = items[selected_item_idx][2]
                    itype = items[selected_item_idx][4]
                    self.enter_edit_mode(sel_info, itype)

            elif ch in (curses.KEY_UP, ord('k')):
                if self.selected_idx > 0:
                    self.selected_idx -= 1
                    self.preview_scroll = 0

            elif ch in (curses.KEY_DOWN, ord('j')):
                if self.selected_idx < len(selectable) - 1:
                    self.selected_idx += 1
                    self.preview_scroll = 0

            elif ch == ord('K'):
                self.preview_scroll = max(0, self.preview_scroll - 4)

            elif ch == ord('J'):
                self.preview_scroll += 4

            elif ch == ord('\t'):
                scopes = ["workspace", "shared", "global"]
                curr_idx = scopes.index(self.target_scope)
                self.target_scope = scopes[(curr_idx + 1) % len(scopes)]
                self.status_msg = f"Target activation scope set to: {self.target_scope.upper()}"

            elif ch == ord('/'):
                self.search_mode = True
                self.status_msg = ""

            elif ch in (ord(' '), 10, 13):
                if selected_item_idx != -1 and items[selected_item_idx][2]:
                    sel_info = items[selected_item_idx][2]
                    _, _, _, is_active, itype = items[selected_item_idx]

                    if itype == "skill":
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
                    else:
                        self.status_msg = f"Toggled {itype} '{sel_info.name}'."

def open_browser():
    from .scope import resolve_scope
    scope = resolve_scope()
    mgr = SkillManager(scope)
    browser = SkillBrowser(mgr)
    browser.run()

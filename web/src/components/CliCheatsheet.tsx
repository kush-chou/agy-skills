'use client';

import React, { useState } from 'react';
import { Terminal, Copy, Check } from 'lucide-react';

interface CliCmd {
  name: string;
  command: string;
  description: string;
  output: string;
}

const CLI_COMMANDS: CliCmd[] = [
  {
    name: 'tui',
    command: 'agy-skills',
    description: 'Launch the full curses split-view context manager in your terminal.',
    output: `[Tabs: 1-Skills 2-Rules 3-Subagents 4-Plugins 5-MCP 6-Built-in 7-Tokens]
Active Context: 3,420 / 20,000 tokens (17.1%) [||||...............]

[X] superpowers          [WORKSPACE]   ~110t   ✔ valid
[X] ui-ux-pro-max         [WORKSPACE]   ~140t   ✔ valid
[X] gpui-framework        [PLUGIN]      ~160t   ✔ valid
[ ] dicom-rs-monai        [PLUGIN]      ~95t    ✔ valid

[1-7] Tabs  [b/Enter] Breakdowns  [Space] Toggle  [Tab] Scope  [q] Quit`,
  },
  {
    name: 'inspect',
    command: 'agy-skills inspect gemini-api',
    description: 'Inspect exact Antigravity IDE GUI hierarchy, category tokens, and component breakdown.',
    output: `======================================================================
  Customizations / gemini-api (v2.2.0)
======================================================================
  Status:  ● Active
  Scope:   PLUGIN
  Context: 1,314 / 20,000 tokens (6.6%)

--- Category Breakdown ---
  • Skills     (566 tokens) 2.8% [3 item(s)]
  • Mcp Tools  (748 tokens) 3.7% [2 item(s)] ⚠️ 1 excluded

--- Component Breakdown ---
  ● [SKILL]    gemini-api-dev                   ~240 tok  Gemini API text, multi-turn...
  ● [SKILL]    gemini-live-api-dev              ~180 tok  Bidirectional streaming...
  ● [SKILL]    gemini-omni-flash-api            ~146 tok  Generative video editing...
  ● [MCP]      gemini_search_docs               ~374 tok  Search Google Gemini API docs
  ● [MCP]      gemini_get_doc                   ~374 tok  Retrieve documentation page
  ○ [MCP]      gemini_batch_generate            ~350 tok  (EXCLUDED - lazy-loaded)`,
  },
  {
    name: 'tokens',
    command: 'agy-skills tokens',
    description: 'Audit context window usage against the 20,000 token limit with breakdown metrics.',
    output: `======================================================================
  Antigravity IDE 2.0 Context Token Budget Audit
======================================================================
Active Context:  4,734 / 20,000 tokens (23.7%)
[██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 23.7%
Headroom Remaining: 15,266 tokens (76.3%)

--- Token Usage by Category ---
  Category     Active Tokens     Budget %       Components
  -------------------------------------------------------------
  Skills               1,820         9.1%       14 active
  Rules                  982         4.9%        2 active
  Subagents              165         0.8%        2 active
  Mcp Tools            1,767         8.8%        4 active
  Total Context:       4,734        23.7%

--- Top Context Consumers ---
  1. gemini-api (plugin)                    1,314 tokens (6.6%)
  2. AGENTS.md (rule)                         680 tokens (3.4%)
  3. StitchMCP (mcp)                          420 tokens (2.1%)
  4. GEMINI.md (rule)                         302 tokens (1.5%)`,
  },
  {
    name: 'toggle',
    command: 'agy-skills toggle gemini-api --sub gemini_search_docs',
    description: 'Granularly cherry-pick and toggle subcomponents inside plugins without disabling the plugin.',
    output: `Component 'gemini_search_docs' inside plugin 'gemini-api' is now DISABLED.
Active context recalculated: 4,360 / 20,000 tokens (21.8%)
Saved overrides to ~/.gemini/config/agy_skills_overrides.json`,
  },
  {
    name: 'list',
    command: 'agy-skills list',
    description: 'Print formatted overview of all discovered skills, rules, and token estimates.',
    output: `📂 Workspace Root: /Users/developer/codebase
📊 Active Context:  4,734 / 20,000 tokens (23.7%)

=== Antigravity Skills (14 found) ===
  • superpowers                 [WORKSPACE]   ~110t   ✔ valid
  • ui-ux-pro-max                [WORKSPACE]   ~140t   ✔ valid
  • gpui-framework               [PLUGIN]      ~160t   ✔ valid
  • iroh-p2p                     [PLUGIN]      ~120t   ✔ valid

=== Antigravity Rules (2 found) ===
  • GEMINI.md                    [WORKSPACE]   ~302t   ✔ valid (0.8 KB)
  • AGENTS.md                    [PLUGIN]      ~680t   ✔ valid (1.9 KB)`,
  },
  {
    name: 'lint',
    command: 'agy-skills lint',
    description: 'Validate kebab-case naming, directory symmetry, and 24 KB rule size budget.',
    output: `🔍 Running Antigravity Validation Suite...

✔ All 14 skills conform to Antigravity frontmatter schema.
✔ All directory names match skill package identifiers.
✔ All rules are within the 24 KB Antigravity size budget.

0 errors, 0 warnings. Workspace healthy.`,
  },
  {
    name: 'search',
    command: 'agy-skills search superpowers',
    description: 'Search curated skill leaderboard and official VoltAgent packs.',
    output: `🌐 Antigravity Skill Marketplace (Matching 'superpowers'):
   Showing 1 verified pack(s) from SkillLeaderboard

  • superpowers                ★ 292k     ~110t  Core Workflows   ○ Available
    Autonomous agent acceleration, self-correction cognitive loops...
    Trigger: /superpowers        Source: https://github.com/obra/superpowers`,
  },
  {
    name: 'install',
    command: 'agy-skills install superpowers',
    description: 'Download and atomically install a verified pack into .agents/skills/.',
    output: `==> Fetching pack 'superpowers' from obra/superpowers...
✔ Downloaded and unpacked to /Users/developer/codebase/.agents/skills/superpowers
✔ Validated SKILL.md schema and directory symmetry
✔ Added to workspace context (~110 tokens)

Pack 'superpowers' installed successfully!`,
  },
  {
    name: 'mcp',
    command: 'agy-skills mcp',
    description: 'List all registered Model Context Protocol (MCP) servers and tool counts.',
    output: `=== Antigravity MCP Servers (6 found) ===
  • StitchMCP                  [15 tools]  ● active     (~/.gemini/antigravity/mcp/StitchMCP)
  • canva                      [49 tools]  ● active     (~/.gemini/antigravity/mcp/canva)
  • playwright                 [25 tools]  ● active     (~/.gemini/antigravity/mcp/playwright)
  • jules                      [8 tools]   ● active     (~/.gemini/antigravity/mcp/jules)`,
  },
];

export function CliCheatsheet() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [copied, setCopied] = useState(false);

  const activeCmd = CLI_COMMANDS[selectedIdx];

  const handleCopy = () => {
    navigator.clipboard.writeText(activeCmd.command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="cli" className="py-16 sm:py-24 border-t border-white/5 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-950/30 px-3 py-1 text-xs font-mono font-medium text-emerald-300 mb-4">
            <Terminal className="h-3.5 w-3.5 text-emerald-400" />
            <span>Command-Line Interface</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white font-sans">
            Full CLI Reference & Automations
          </h2>
          <p className="mt-3 text-slate-400 text-sm sm:text-base">
            Script your CI pipelines, lint incoming skills, or manage context programmatically with standard POSIX flags.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center justify-center gap-2 overflow-x-auto pb-4 mb-6 font-mono text-xs">
          {CLI_COMMANDS.map((cmd, idx) => (
            <button
              key={cmd.name}
              onClick={() => setSelectedIdx(idx)}
              className={`rounded-lg px-3.5 py-1.5 transition cursor-pointer whitespace-nowrap ${
                selectedIdx === idx
                  ? 'bg-emerald-600 text-white font-bold shadow-md shadow-emerald-500/20'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              {cmd.name}
            </button>
          ))}
        </div>

        {/* Command Runner Box */}
        <div className="max-w-4xl mx-auto rounded-2xl border border-white/10 bg-[#090b10] shadow-2xl overflow-hidden font-mono text-xs">
          {/* Header Bar */}
          <div className="flex items-center justify-between border-b border-white/10 bg-slate-900/80 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="text-pink-400 font-bold">$</span>
              <span className="text-slate-100 font-semibold">{activeCmd.command}</span>
            </div>

            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-white/10 hover:text-white transition cursor-pointer"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>

          {/* Description */}
          <div className="px-5 py-2.5 bg-black/30 border-b border-white/5 text-slate-400 font-sans text-xs">
            {activeCmd.description}
          </div>

          {/* Output Console */}
          <pre className="p-5 text-slate-300 overflow-x-auto leading-relaxed select-text font-mono">
            {activeCmd.output}
          </pre>
        </div>
      </div>
    </section>
  );
}

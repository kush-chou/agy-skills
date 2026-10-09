'use client';

import React from 'react';
import { Layers, Cpu, ShieldAlert, Workflow } from 'lucide-react';

export function Architecture() {
  return (
    <section id="architecture" className="py-16 sm:py-24 border-t border-white/5 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Title */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 rounded-full border border-pink-500/30 bg-pink-950/30 px-3 py-1 text-xs font-mono font-medium text-pink-300 mb-4">
            <Layers className="h-3.5 w-3.5 text-pink-400" />
            <span>Under the Hood</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white font-sans">
            Architected for Zero Context Bleed
          </h2>
          <p className="mt-3 text-slate-400 text-sm sm:text-base">
            Modern AI agents suffer from context pollution when entire directories of tools and rules are dumped unconditionally. agy-skills introduces strict hierarchical discovery and token governors.
          </p>
        </div>

        {/* 3 Pillars Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
          {/* Pillar 1 */}
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-6 flex flex-col justify-between">
            <div>
              <div className="h-12 w-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-5">
                <Workflow className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">4-Tier Scope Hierarchy</h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Atomic discovery across:
              </p>
              <ul className="mt-3 space-y-2 text-xs font-mono text-slate-400">
                <li className="flex items-center gap-2">
                  <span className="text-indigo-400">1.</span>
                  <span>Workspace: <code className="text-white">.agents/skills/</code></span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-indigo-400">2.</span>
                  <span>Global: <code className="text-white">~/.gemini/config/</code></span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-indigo-400">3.</span>
                  <span>Built-in: <code className="text-white">antigravity/builtin/</code></span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-indigo-400">4.</span>
                  <span>Catalog: Verified Remote Packs</span>
                </li>
              </ul>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-indigo-300">
              Zero collisions via scoped resolution
            </div>
          </div>

          {/* Pillar 2 */}
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-6 flex flex-col justify-between">
            <div>
              <div className="h-12 w-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-5">
                <ShieldAlert className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">24 KB Size Budget & Linting</h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Antigravity requires system rules to remain strictly under 24 KB to protect prompt cache efficiency. agy-skills runs automated compliance checks before injection.
              </p>
              <div className="mt-4 rounded-lg bg-black/50 p-3 font-mono text-[11px] text-slate-300 border border-white/5 space-y-1">
                <div className="text-emerald-400">✔ YAML frontmatter parsed</div>
                <div className="text-emerald-400">✔ Kebab-case naming enforced</div>
                <div className="text-emerald-400">✔ Directory symmetry validated</div>
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-purple-300">
              Run anytime via `agy-skills lint`
            </div>
          </div>

          {/* Pillar 3 */}
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-6 flex flex-col justify-between">
            <div>
              <div className="h-12 w-12 rounded-xl bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400 mb-5">
                <Cpu className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">IDE & Sidecar RPC Sync</h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Communicates directly with the Antigravity Language Server RPC over Unix sockets and HTTP to activate, disable, and reload plugins live without restarting the editor.
              </p>
              <div className="mt-4 rounded-lg bg-black/50 p-3 font-mono text-[11px] text-slate-300 border border-white/5 space-y-1">
                <div className="text-slate-400">POST /plugins/setPluginEnabled</div>
                <div className="text-indigo-400">{`{ id: "rust-medtech-dev", enabled: true }`}</div>
                <div className="text-emerald-400">200 OK — sidecar notified</div>
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-pink-300">
              Instant live hot-reloading
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

'use client';

import React, { useState, useMemo } from 'react';
import { INITIAL_TUI_ITEMS, TuiItem } from '../data/tuiData';
import { Search, Terminal, Sliders, CheckSquare, Square, Info, ShieldCheck, Zap } from 'lucide-react';

const TOKEN_BUDGET = 20000;

export function TuiEmulator() {
  const [items, setItems] = useState<TuiItem[]>(INITIAL_TUI_ITEMS);
  const [currentTab, setCurrentTab] = useState<'skill' | 'rule' | 'subagent' | 'plugin' | 'mcp'>('skill');
  const [selectedId, setSelectedId] = useState<string>('s-superpowers');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Calculate dynamic token meter
  const activeTokens = useMemo(() => {
    return items.reduce((acc, item) => (item.active ? acc + item.tokens : acc), 0);
  }, [items]);

  const tokenPercent = Math.min(100, (activeTokens / TOKEN_BUDGET) * 100);

  // Filter items by current tab and search query
  const filteredItems = useMemo(() => {
    return items.filter(
      (item) =>
        item.type === currentTab &&
        (item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.description.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  }, [items, currentTab, searchQuery]);

  // Selected item details
  const selectedItem = useMemo(() => {
    return items.find((i) => i.id === selectedId) || filteredItems[0] || items[0];
  }, [items, selectedId, filteredItems]);

  const toggleItem = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, active: !item.active } : item))
    );
  };

  const getMeterColor = (pct: number) => {
    if (pct < 30) return 'bg-emerald-500';
    if (pct < 70) return 'bg-indigo-500';
    if (pct < 85) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  return (
    <section id="tui-demo" className="py-16 sm:py-24 border-t border-white/5 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Heading */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-950/30 px-3 py-1 text-xs font-mono font-medium text-purple-300 mb-4">
            <Sliders className="h-3.5 w-3.5 text-purple-400" />
            <span>Interactive Terminal Simulation</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white font-sans">
            The Split-View Context Cockpit
          </h2>
          <p className="mt-3 text-slate-400 text-sm sm:text-base">
            Click tabs and toggle items below to experience the real-time token budget governor in action.
          </p>
        </div>

        {/* TUI Window Frame */}
        <div className="rounded-2xl border border-white/15 bg-[#0b0d14] shadow-2xl shadow-indigo-950/60 overflow-hidden font-mono">
          {/* Window Header */}
          <div className="flex items-center justify-between border-b border-white/10 bg-slate-900/90 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <span className="h-3 w-3 rounded-full bg-rose-500/80 inline-block" />
                <span className="h-3 w-3 rounded-full bg-amber-500/80 inline-block" />
                <span className="h-3 w-3 rounded-full bg-emerald-500/80 inline-block" />
              </div>
              <span className="ml-3 text-xs font-semibold text-slate-300 flex items-center gap-2">
                <Terminal className="h-3.5 w-3.5 text-indigo-400" />
                agy-skills v0.1.0 — Antigravity Context Governor
              </span>
            </div>

            {/* Token Budget Gauge */}
            <div className="hidden sm:flex items-center gap-3">
              <span className="text-[11px] text-slate-400">Context Budget:</span>
              <div className="w-36 h-2 bg-slate-800 rounded-full overflow-hidden border border-white/10">
                <div
                  className={`h-full ${getMeterColor(tokenPercent)} transition-all duration-300`}
                  style={{ width: `${tokenPercent}%` }}
                />
              </div>
              <span className="text-xs font-semibold text-indigo-300">
                {activeTokens.toLocaleString()} / {TOKEN_BUDGET.toLocaleString()}t ({tokenPercent.toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* Subheader / Tabs bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-white/10 bg-black/40 px-4 py-2.5">
            {/* Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto text-xs scrollbar-none">
              {(
                [
                  { key: 'skill', label: '[1] Skills' },
                  { key: 'rule', label: '[2] Rules' },
                  { key: 'subagent', label: '[3] Subagents' },
                  { key: 'plugin', label: '[4] Plugins' },
                  { key: 'mcp', label: '[5] MCP Servers' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => {
                    setCurrentTab(tab.key);
                    const first = items.find((i) => i.type === tab.key);
                    if (first) setSelectedId(first.id);
                  }}
                  className={`px-3 py-1.5 rounded-md transition whitespace-nowrap cursor-pointer ${
                    currentTab === tab.key
                      ? 'bg-indigo-600 text-white font-bold shadow-sm shadow-indigo-500/30'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Filter Input */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="/ to filter..."
                className="w-full sm:w-48 bg-slate-900/80 border border-white/10 rounded-lg pl-8 pr-3 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/60"
              />
            </div>
          </div>

          {/* Main Split Body */}
          <div className="grid grid-cols-1 md:grid-cols-12 min-h-[380px]">
            {/* Left Pane: Items List */}
            <div className="md:col-span-7 border-b md:border-b-0 md:border-r border-white/10 p-2 space-y-1 overflow-y-auto max-h-[460px]">
              {filteredItems.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-500">
                  No items match query "{searchQuery}"
                </div>
              ) : (
                filteredItems.map((item) => {
                  const isSelected = item.id === selectedItem?.id;
                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelectedId(item.id)}
                      className={`group flex items-center justify-between p-2.5 rounded-lg text-xs cursor-pointer transition ${
                        isSelected
                          ? 'bg-indigo-950/60 border border-indigo-500/40 text-white shadow-sm'
                          : 'hover:bg-white/5 border border-transparent text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 overflow-hidden">
                        <button
                          onClick={(e) => toggleItem(item.id, e)}
                          className="text-slate-400 hover:text-white transition cursor-pointer flex-shrink-0"
                          title="Toggle active"
                        >
                          {item.active ? (
                            <CheckSquare className="h-4 w-4 text-emerald-400" />
                          ) : (
                            <Square className="h-4 w-4 text-slate-600" />
                          )}
                        </button>
                        <span className="font-semibold truncate text-white">{item.name}</span>
                        <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400 uppercase">
                          {item.badge}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 flex-shrink-0 text-[11px]">
                        <span className="text-indigo-300 font-medium">~{item.tokens}t</span>
                        <span
                          className={`h-2 w-2 rounded-full ${
                            item.active ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-slate-600'
                          }`}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Right Pane: Item Inspector */}
            <div className="md:col-span-5 p-4 sm:p-6 bg-slate-950/40 flex flex-col justify-between">
              {selectedItem ? (
                <div className="space-y-4">
                  {/* Top Bar of Inspector */}
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-400">
                        {selectedItem.type.toUpperCase()} INSPECTOR
                      </span>
                      <h3 className="text-lg font-bold text-white mt-0.5">{selectedItem.name}</h3>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        selectedItem.active
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      {selectedItem.active ? 'ACTIVE' : 'DISABLED'}
                    </span>
                  </div>

                  {/* Metadata Fields */}
                  <div className="space-y-2 rounded-xl bg-white/5 p-3.5 border border-white/5 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Scope:</span>
                      <span className="text-slate-200 font-semibold">{selectedItem.badge}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Context Cost:</span>
                      <span className="text-indigo-300 font-semibold">~{selectedItem.tokens} tokens</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Schema Linter:</span>
                      <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        {selectedItem.statusText || '✔ validated'}
                      </span>
                    </div>
                    <div className="pt-1 border-t border-white/5 text-[11px] text-slate-400 break-all">
                      <span className="text-slate-500">Target:</span> {selectedItem.path}
                    </div>
                  </div>

                  {/* Description Box */}
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold mb-1.5 flex items-center gap-1.5">
                      <Info className="h-3 w-3 text-indigo-400" /> Description & Capabilities
                    </h4>
                    <p className="text-xs text-slate-300 leading-relaxed bg-black/30 p-3 rounded-lg border border-white/5 font-sans">
                      {selectedItem.description}
                    </p>
                  </div>

                  {/* Toggle Action Button */}
                  <div className="pt-2">
                    <button
                      onClick={() => toggleItem(selectedItem.id)}
                      className={`w-full py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer ${
                        selectedItem.active
                          ? 'bg-rose-500/10 border border-rose-500/30 text-rose-300 hover:bg-rose-500/20'
                          : 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20'
                      }`}
                    >
                      <Zap className="h-3.5 w-3.5" />
                      {selectedItem.active ? 'Disable in Workspace' : 'Enable in Workspace'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-500">Select an item to view metadata</div>
              )}

              {/* Status bar prompt */}
              <div className="mt-6 pt-3 border-t border-white/10 text-[10px] text-slate-400 flex items-center justify-between">
                <span>[1-5] Tabs</span>
                <span>[Space] Toggle</span>
                <span>[/] Search</span>
                <span>[q] Exit</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

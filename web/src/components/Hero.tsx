'use client';

import React, { useState } from 'react';
import { Copy, Check, Sparkles, ChevronRight, ArrowDown } from 'lucide-react';

export function Hero() {
  const [activeTab, setActiveTab] = useState<'curl' | 'pip' | 'clone'>('curl');
  const [copied, setCopied] = useState(false);

  const commands = {
    curl: 'curl -fsSL https://agy-skills.sh | sh',
    pip: 'pip install agy-skills',
    clone: 'git clone https://github.com/kush-chou/agy-skills.git && cd agy-skills && ./agy-skills.sh',
  };

  const currentCommand = commands[activeTab];

  const handleCopy = () => {
    navigator.clipboard.writeText(currentCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="relative overflow-hidden pt-12 pb-16 lg:pt-20 lg:pb-24">
      {/* Background Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-gradient-to-tr from-indigo-600/20 via-purple-600/20 to-pink-500/10 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute -top-10 right-10 w-72 h-72 bg-blue-500/10 blur-[90px] rounded-full pointer-events-none" />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10 text-center">
        {/* Release / Status Badge */}
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-950/40 px-3.5 py-1.5 text-xs font-medium text-indigo-300 backdrop-blur-md mb-8">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Antigravity 2.0 & Gemini CLI Counterpart</span>
          <span className="text-white/30">|</span>
          <span className="text-slate-400">v0.1.0 Ready</span>
          <ChevronRight className="h-3.5 w-3.5 text-indigo-400" />
        </div>

        {/* Headline */}
        <h1 className="mx-auto max-w-4xl text-4xl font-extrabold tracking-tight text-white sm:text-6xl lg:text-7xl font-sans">
          The Package & Context Manager for{' '}
          <span className="bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400 bg-clip-text text-transparent">
            AI Coding Agents
          </span>
        </h1>

        {/* Subhead */}
        <p className="mx-auto mt-6 max-w-2xl text-base sm:text-lg text-slate-300 font-normal leading-relaxed">
          High-velocity, non-destructive discovery and activation of agent skills, behavioral rules, subagents, and Model Context Protocol (MCP) servers with strict token budget metering.
        </p>

        {/* Install Box */}
        <div className="mx-auto mt-10 max-w-2xl">
          <div className="rounded-2xl border border-white/10 bg-slate-950/80 p-2 shadow-2xl shadow-indigo-950/50 backdrop-blur-xl">
            {/* Tabs */}
            <div className="flex items-center justify-between border-b border-white/10 px-3 pb-2 text-xs font-mono">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('curl')}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    activeTab === 'curl'
                      ? 'bg-indigo-600/30 text-indigo-300 font-semibold border border-indigo-500/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  curl installer
                </button>
                <button
                  onClick={() => setActiveTab('pip')}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    activeTab === 'pip'
                      ? 'bg-indigo-600/30 text-indigo-300 font-semibold border border-indigo-500/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  pip
                </button>
                <button
                  onClick={() => setActiveTab('clone')}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    activeTab === 'clone'
                      ? 'bg-indigo-600/30 text-indigo-300 font-semibold border border-indigo-500/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  git source
                </button>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
                <Sparkles className="h-3 w-3 text-amber-400" />
                <span>Zero config</span>
              </div>
            </div>

            {/* Command & Copy */}
            <div className="flex items-center justify-between gap-4 p-4 font-mono text-sm sm:text-base">
              <div className="flex items-center gap-3 overflow-x-auto text-left text-slate-100 select-all scrollbar-none">
                <span className="text-pink-400 font-bold">$</span>
                <span className="whitespace-nowrap">{currentCommand}</span>
              </div>

              <button
                onClick={handleCopy}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-2 font-medium text-white shadow-md shadow-indigo-500/25 hover:from-indigo-400 hover:to-purple-500 transition cursor-pointer flex-shrink-0"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-emerald-200" />
                    <span className="text-xs">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    <span className="text-xs">Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick Info Points */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-400 font-mono">
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              macOS & Linux support
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
              Python 3.9+ runtime
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-purple-400" />
              100% Non-destructive
            </span>
          </div>
        </div>

        {/* Scroll down prompt */}
        <div className="mt-12 flex justify-center">
          <a
            href="#tui-demo"
            className="group flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-slate-400 hover:text-white transition"
          >
            <span>Try the interactive TUI simulator</span>
            <ArrowDown className="h-3.5 w-3.5 group-hover:translate-y-1 transition" />
          </a>
        </div>
      </div>
    </section>
  );
}

'use client';

import React, { useState } from 'react';
import { Terminal, Check, Copy } from 'lucide-react';

export function Navbar() {
  const [copied, setCopied] = useState(false);

  const copyCommand = () => {
    navigator.clipboard.writeText('curl -fsSL https://agy-skills.sh | sh');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-black/60 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <a href="#" className="flex items-center gap-3 group">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 p-0.5 shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition">
            <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-slate-950">
              <Terminal className="h-5 w-5 text-indigo-400 group-hover:text-indigo-300 transition" />
            </div>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
              agy-skills<span className="text-indigo-400">.sh</span>
            </span>
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Antigravity Context</span>
          </div>
        </a>

        {/* Navigation links */}
        <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
          <a href="#tui-demo" className="hover:text-white transition">Live TUI</a>
          <a href="#marketplace" className="hover:text-white transition">Skill Marketplace</a>
          <a href="#architecture" className="hover:text-white transition">Architecture</a>
          <a href="#cli" className="hover:text-white transition">CLI Reference</a>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={copyCommand}
            className="hidden sm:flex items-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3.5 py-1.5 text-xs font-mono font-medium text-indigo-300 hover:bg-indigo-500/20 hover:border-indigo-500/50 transition cursor-pointer"
            title="Click to copy install command"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            <span>curl -fsSL https://agy-skills.sh | sh</span>
          </button>

          <a
            href="https://github.com/kush-chou/agy-skills"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10 hover:text-white transition"
            aria-label="GitHub Repository"
          >
            <svg className="h-5 w-5 fill-current" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}

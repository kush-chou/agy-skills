'use client';

import React, { useState, useMemo } from 'react';
import { CATALOG_SKILLS, SkillPack } from '../data/catalog';
import { Search, Star, Copy, Check, ExternalLink, Sparkles, Terminal } from 'lucide-react';

const CATEGORIES = [
  'All',
  'Core Workflows',
  'Code Intelligence',
  'UI/UX & Design',
  'Cloud & Database',
  'Scientific & Bio',
  'Documents',
  'Developer Tools',
];

export function Marketplace() {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [search, setSearch] = useState<string>('');
  const [copiedPack, setCopiedPack] = useState<string | null>(null);

  const filteredPacks = useMemo(() => {
    return CATALOG_SKILLS.filter((pack) => {
      const matchCat = selectedCategory === 'All' || pack.category === selectedCategory;
      const matchSearch =
        pack.name.toLowerCase().includes(search.toLowerCase()) ||
        pack.description.toLowerCase().includes(search.toLowerCase()) ||
        pack.author.toLowerCase().includes(search.toLowerCase()) ||
        pack.slashTrigger.toLowerCase().includes(search.toLowerCase());
      return matchCat && matchSearch;
    });
  }, [selectedCategory, search]);

  const copyInstall = (packName: string) => {
    navigator.clipboard.writeText(`agy-skills install ${packName}`);
    setCopiedPack(packName);
    setTimeout(() => setCopiedPack(null), 2000);
  };

  return (
    <section id="marketplace" className="py-16 sm:py-24 border-t border-white/5 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-950/30 px-3 py-1 text-xs font-mono font-medium text-indigo-300 mb-3">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              <span>Curated Skill Leaderboard & VoltAgent Index</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white font-sans">
              Agent Skill Marketplace
            </h2>
            <p className="mt-2 text-slate-400 text-sm sm:text-base max-w-xl">
              Turnkey install community superpowers and official tool packs directly into your workspace or global config with a single command.
            </p>
          </div>

          {/* Search Bar */}
          <div className="relative w-full md:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search skills, triggers, authors..."
              className="w-full rounded-xl border border-white/10 bg-slate-900/80 pl-9 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/60"
            />
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-4 mb-8 text-xs font-medium scrollbar-none">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`rounded-lg px-3.5 py-1.5 transition whitespace-nowrap cursor-pointer ${
                selectedCategory === cat
                  ? 'bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-500/20'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPacks.map((pack: SkillPack) => {
            const isCopied = copiedPack === pack.name;
            return (
              <div
                key={pack.name}
                className="group relative flex flex-col justify-between rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-transparent p-6 hover:border-indigo-500/40 hover:from-indigo-950/20 transition-all duration-200"
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="rounded-md bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 text-[11px] font-mono font-medium text-indigo-300">
                      {pack.category}
                    </span>

                    <div className="flex items-center gap-2">
                      <span className="flex items-center gap-1 text-[11px] font-mono text-amber-300">
                        <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                        {pack.stars}
                      </span>
                      <span className="text-[11px] font-mono text-slate-500">
                        ~{pack.tokens}t
                      </span>
                    </div>
                  </div>

                  {/* Title & Author */}
                  <div className="mb-2">
                    <h3 className="text-lg font-bold text-white group-hover:text-indigo-300 transition">
                      {pack.name}
                    </h3>
                    <p className="text-xs font-mono text-slate-400">by {pack.author}</p>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed mb-4">
                    {pack.description}
                  </p>
                </div>

                <div>
                  {/* Slash Trigger & Source */}
                  <div className="flex items-center justify-between border-t border-white/5 pt-3 mb-3 text-[11px] font-mono">
                    <span className="text-purple-300 bg-purple-950/40 border border-purple-500/20 px-2 py-0.5 rounded">
                      {pack.slashTrigger}
                    </span>
                    <a
                      href={pack.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-400 hover:text-white flex items-center gap-1 transition"
                    >
                      <span>repo</span>
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>

                  {/* Copy Install Command */}
                  <button
                    onClick={() => copyInstall(pack.name)}
                    className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-black/40 hover:bg-white/10 p-2 text-xs font-mono text-slate-300 transition cursor-pointer"
                  >
                    <div className="flex items-center gap-1.5 truncate">
                      <Terminal className="h-3.5 w-3.5 text-indigo-400 flex-shrink-0" />
                      <span className="text-slate-400">agy-skills install</span>
                      <span className="text-white font-semibold truncate">{pack.name}</span>
                    </div>
                    {isCopied ? (
                      <span className="flex items-center gap-1 text-emerald-400 text-[11px] flex-shrink-0 font-sans">
                        <Check className="h-3 w-3" /> Copied
                      </span>
                    ) : (
                      <Copy className="h-3.5 w-3.5 text-slate-400 group-hover:text-white flex-shrink-0" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

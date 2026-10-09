import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'agy-skills — Context & Skills Manager for Antigravity & AI Coding Agents',
  description:
    'Keyboard-first package manager for Google Antigravity & Gemini CLI. Atomic discovery and activation of Skills, Rules, Subagents, Plugins, and MCP Servers.',
  keywords: [
    'antigravity',
    'skills',
    'ai coding agents',
    'gemini cli',
    'context manager',
    'mcp',
    'model context protocol',
    'superpowers',
  ],
  authors: [{ name: 'Kushagra Choudhary' }],
  openGraph: {
    title: 'agy-skills — Context & Skills Manager for Antigravity & AI Coding Agents',
    description:
      'Turnkey install community superpowers and manage context budgets with zero context bleed.',
    url: 'https://agy-skills.sh',
    siteName: 'agy-skills',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'agy-skills.sh — Antigravity Context & Skills Manager',
    description:
      'Turnkey install community superpowers and manage context budgets with zero context bleed.',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} dark scroll-smooth`}>
      <body className="min-h-screen bg-[#07080d] text-slate-100 font-sans antialiased">
        {children}
      </body>
    </html>
  );
}

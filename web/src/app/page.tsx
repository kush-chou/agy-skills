import { Navbar } from '@/components/Navbar';
import { Hero } from '@/components/Hero';
import { TuiEmulator } from '@/components/TuiEmulator';
import { Marketplace } from '@/components/Marketplace';
import { Architecture } from '@/components/Architecture';
import { CliCheatsheet } from '@/components/CliCheatsheet';
import { Footer } from '@/components/Footer';

export default function Home() {
  return (
    <div className="min-h-screen bg-[#07080d] text-slate-100 selection:bg-indigo-500 selection:text-white">
      <Navbar />
      <main>
        <Hero />
        <TuiEmulator />
        <Marketplace />
        <Architecture />
        <CliCheatsheet />
      </main>
      <Footer />
    </div>
  );
}

'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface NavItem {
  label: string;
  href: string;
  icon: string;
  scanOnly?: boolean;
  siegeOnly?: boolean;
}

const mainNav: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: '\u2302' },
];

const scanNav: NavItem[] = [
  { label: 'Overview', href: '', icon: '\u25CB' },
  { label: 'Report', href: '/report', icon: '\u2637' },
  { label: 'Attacks', href: '/attacks', icon: '\u2694', siegeOnly: true },
  { label: 'Chaos', href: '/chaos', icon: '\u26A1' },
  { label: 'Code', href: '/code', icon: '\u2039\u203A' },
  { label: 'Graph', href: '/graph', icon: '\u25C9' },
  { label: 'Fixes', href: '/fixes', icon: '\u2692' },
  { label: 'Playbook', href: '/playbook', icon: '\u2706', siegeOnly: true },
];

interface SidebarProps {
  scanId?: string;
  isSiege?: boolean;
}

export default function Sidebar({ scanId, isSiege }: SidebarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname === href;
  };

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-300"
      >
        {mobileOpen ? '\u2715' : '\u2630'}
      </button>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-40 h-full w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col transition-transform duration-300',
          'lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-zinc-800">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-bold text-zinc-100 tracking-tight">ChaosGuard AI</h1>
              <p className="text-[10px] text-zinc-500 tracking-wider uppercase">Security Platform</p>
            </div>
          </Link>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <div className="space-y-1">
            {mainNav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                  isActive(item.href)
                    ? 'bg-zinc-800 text-zinc-100'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
                )}
              >
                <span className="text-base w-5 text-center">{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </div>

          {/* Scan Navigation */}
          {scanId && (
            <div className="mt-6">
              <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">
                Scan Details
              </p>
              <div className="space-y-1">
                {scanNav
                  .filter((item) => !item.siegeOnly || isSiege)
                  .map((item) => {
                    const href = `/scan/${scanId}${item.href}`;
                    return (
                      <Link
                        key={item.href}
                        href={href}
                        onClick={() => setMobileOpen(false)}
                        className={cn(
                          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                          isActive(href)
                            ? 'bg-zinc-800 text-zinc-100'
                            : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
                        )}
                      >
                        <span className="text-base w-5 text-center">{item.icon}</span>
                        {item.label}
                      </Link>
                    );
                  })}
              </div>
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800">
          <p className="text-[10px] text-zinc-600 text-center">
            ChaosGuard AI v1.0
          </p>
        </div>
      </aside>
    </>
  );
}

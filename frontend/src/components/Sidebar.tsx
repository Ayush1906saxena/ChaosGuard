'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import {
  HomeIcon,
  DocumentMagnifyingGlassIcon,
  ShieldExclamationIcon,
  BoltIcon,
  CodeBracketIcon,
  ShareIcon,
  WrenchScrewdriverIcon,
  BookOpenIcon,
  Bars3Icon,
  XMarkIcon,
  ChartBarIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline';
import { getUser, logout } from '@/lib/auth';

interface NavItem {
  label: string;
  href: string;
  icon: typeof HomeIcon;
  scanOnly?: boolean;
  siegeOnly?: boolean;
}

const mainNav: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: HomeIcon },
  { label: 'Metrics', href: '/metrics', icon: ChartBarIcon },
];

const scanNav: NavItem[] = [
  { label: 'Overview', href: '', icon: DocumentMagnifyingGlassIcon },
  { label: 'Report', href: '/report', icon: ShieldExclamationIcon },
  { label: 'Attacks', href: '/attacks', icon: BoltIcon, siegeOnly: true },
  { label: 'Chaos', href: '/chaos', icon: BoltIcon },
  { label: 'Code', href: '/code', icon: CodeBracketIcon },
  { label: 'Graph', href: '/graph', icon: ShareIcon },
  { label: 'Fixes', href: '/fixes', icon: WrenchScrewdriverIcon },
  { label: 'Playbook', href: '/playbook', icon: BookOpenIcon, siegeOnly: true },
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
    if (href === '/metrics') return pathname === '/metrics';
    return pathname === href;
  };

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2.5 glass-card rounded-xl text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        {mobileOpen ? <XMarkIcon className="w-5 h-5" /> : <Bars3Icon className="w-5 h-5" />}
      </button>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-30"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-40 h-full w-64 bg-[#0a0a0c]/80 backdrop-blur-xl border-r border-white/[0.04] flex flex-col transition-transform duration-300',
          'lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-white/[0.04]">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center shadow-lg shadow-red-500/20 group-hover:shadow-red-500/30 transition-shadow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-white/20 to-transparent" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-zinc-100 tracking-tight">ChaosGuard</h1>
              <p className="text-[10px] text-zinc-500 tracking-widest uppercase font-medium">AI Security</p>
            </div>
          </Link>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <div className="space-y-0.5">
            {mainNav.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200',
                    active
                      ? 'nav-active text-zinc-100 font-medium'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]'
                  )}
                >
                  <Icon className={cn('w-[18px] h-[18px] flex-shrink-0', active ? 'text-red-400' : '')} />
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Scan Navigation */}
          {scanId && (
            <div className="mt-8">
              <p className="px-3 mb-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-600">
                Scan Details
              </p>
              <div className="space-y-0.5">
                {scanNav
                  .filter((item) => !item.siegeOnly || isSiege)
                  .map((item) => {
                    const Icon = item.icon;
                    const href = `/scan/${scanId}${item.href}`;
                    const active = isActive(href);
                    return (
                      <Link
                        key={item.href}
                        href={href}
                        onClick={() => setMobileOpen(false)}
                        className={cn(
                          'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200',
                          active
                            ? 'nav-active text-zinc-100 font-medium'
                            : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]'
                        )}
                      >
                        <Icon className={cn('w-[18px] h-[18px] flex-shrink-0', active ? 'text-red-400' : '')} />
                        {item.label}
                      </Link>
                    );
                  })}
              </div>
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/[0.04] space-y-2">
          {(() => {
            const user = getUser();
            return user ? (
              <div className="flex items-center justify-between px-3 py-2">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-red-500 flex items-center justify-center text-[10px] font-bold text-white uppercase">
                    {user.username[0]}
                  </div>
                  <span className="text-xs text-zinc-400 font-medium">{user.username}</span>
                </div>
                <button
                  onClick={logout}
                  className="text-zinc-600 hover:text-red-400 transition-colors"
                  title="Sign out"
                >
                  <ArrowRightOnRectangleIcon className="w-4 h-4" />
                </button>
              </div>
            ) : null;
          })()}
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <p className="text-[10px] text-zinc-600">ChaosGuard AI v1.0</p>
          </div>
        </div>
      </aside>
    </>
  );
}

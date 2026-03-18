'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { ChevronRightIcon, HomeIcon } from '@heroicons/react/24/outline';

const labelMap: Record<string, string> = {
  scan: 'Scan',
  report: 'Report',
  findings: 'Findings',
  fixes: 'Fix Review',
  chains: 'Attack Chains',
  chaos: 'Chaos Engineering',
  playbooks: 'Playbooks',
  explorer: 'Code Explorer',
  metrics: 'Metrics',
};

export default function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split('/').filter(Boolean);

  const crumbs: { label: string; href: string }[] = [
    { label: 'Dashboard', href: '/' },
  ];

  let path = '';
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    path += '/' + seg;

    // Skip UUID segments but keep them in the path
    if (seg.match(/^[0-9a-f]{8}-/)) {
      crumbs.push({ label: seg.slice(0, 8), href: path });
    } else {
      crumbs.push({
        label: labelMap[seg] || seg.charAt(0).toUpperCase() + seg.slice(1),
        href: path,
      });
    }
  }

  return (
    <nav className="flex items-center gap-1.5 text-xs text-zinc-500 mb-6">
      {crumbs.map((crumb, i) => (
        <span key={crumb.href} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRightIcon className="w-3 h-3 text-zinc-700" />}
          {i === 0 && <HomeIcon className="w-3 h-3" />}
          {i < crumbs.length - 1 ? (
            <Link
              href={crumb.href}
              className="hover:text-zinc-300 transition-colors"
            >
              {crumb.label}
            </Link>
          ) : (
            <span className="text-zinc-400">{crumb.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

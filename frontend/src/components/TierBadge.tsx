'use client';

import { cn } from '@/lib/utils';
import type { ScanTier } from '@/lib/types';

const tierConfig: Record<ScanTier, { label: string; classes: string }> = {
  RECON: {
    label: 'Recon',
    classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  },
  HUNTER: {
    label: 'Hunter',
    classes: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  },
  SIEGE: {
    label: 'Siege',
    classes: 'bg-red-500/10 text-red-400 border-red-500/20',
  },
  LIVE: {
    label: 'Live',
    classes: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  },
};

interface TierBadgeProps {
  tier: ScanTier;
  size?: 'sm' | 'md';
  className?: string;
}

export default function TierBadge({ tier, size = 'md', className }: TierBadgeProps) {
  const config = tierConfig[tier];
  return (
    <span
      className={cn(
        'inline-flex items-center font-semibold rounded-lg border uppercase tracking-wider',
        config.classes,
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-[11px]',
        className
      )}
    >
      {config.label}
    </span>
  );
}

'use client';

import { cn } from '@/lib/utils';
import type { ScanTier } from '@/lib/types';

const tierConfig: Record<ScanTier, { label: string; icon: string; classes: string }> = {
  RECON: {
    label: 'Recon',
    icon: '',
    classes: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  },
  HUNTER: {
    label: 'Hunter',
    icon: '',
    classes: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  },
  SIEGE: {
    label: 'Siege',
    icon: '',
    classes: 'bg-red-500/15 text-red-400 border-red-500/30',
  },
  LIVE: {
    label: 'Live',
    icon: '',
    classes: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
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
        'inline-flex items-center font-semibold rounded-md border uppercase tracking-wider',
        config.classes,
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs',
        className
      )}
    >
      {config.label}
    </span>
  );
}

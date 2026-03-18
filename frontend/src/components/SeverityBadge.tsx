'use client';

import { cn } from '@/lib/utils';
import type { Severity } from '@/lib/types';

const severityConfig: Record<Severity, { label: string; classes: string; dotColor: string }> = {
  CRITICAL: {
    label: 'Critical',
    classes: 'bg-red-500/10 text-red-400 border-red-500/20',
    dotColor: 'bg-red-400',
  },
  HIGH: {
    label: 'High',
    classes: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    dotColor: 'bg-orange-400',
  },
  MEDIUM: {
    label: 'Medium',
    classes: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    dotColor: 'bg-yellow-400',
  },
  LOW: {
    label: 'Low',
    classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    dotColor: 'bg-blue-400',
  },
  INFO: {
    label: 'Info',
    classes: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    dotColor: 'bg-zinc-400',
  },
};

interface SeverityBadgeProps {
  severity: Severity;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function SeverityBadge({ severity, size = 'md', className }: SeverityBadgeProps) {
  const config = severityConfig[severity];
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-[10px]',
    md: 'px-2.5 py-0.5 text-[11px]',
    lg: 'px-3 py-1 text-xs',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-semibold rounded-lg border uppercase tracking-wider',
        config.classes,
        sizeClasses[size],
        className
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full mr-1.5', config.dotColor)} />
      {config.label}
    </span>
  );
}

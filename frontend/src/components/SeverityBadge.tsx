'use client';

import { cn } from '@/lib/utils';
import type { Severity } from '@/lib/types';

const severityConfig: Record<Severity, { label: string; classes: string }> = {
  CRITICAL: {
    label: 'Critical',
    classes: 'bg-severity-critical-bg text-severity-critical border-severity-critical-border',
  },
  HIGH: {
    label: 'High',
    classes: 'bg-severity-high-bg text-severity-high border-severity-high-border',
  },
  MEDIUM: {
    label: 'Medium',
    classes: 'bg-severity-medium-bg text-severity-medium border-severity-medium-border',
  },
  LOW: {
    label: 'Low',
    classes: 'bg-severity-low-bg text-severity-low border-severity-low-border',
  },
  INFO: {
    label: 'Info',
    classes: 'bg-severity-info-bg text-severity-info border-severity-info-border',
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
    md: 'px-2 py-0.5 text-xs',
    lg: 'px-3 py-1 text-sm',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-semibold rounded-full border uppercase tracking-wide',
        config.classes,
        sizeClasses[size],
        className
      )}
    >
      <span
        className={cn('w-1.5 h-1.5 rounded-full mr-1.5', {
          'bg-severity-critical': severity === 'CRITICAL',
          'bg-severity-high': severity === 'HIGH',
          'bg-severity-medium': severity === 'MEDIUM',
          'bg-severity-low': severity === 'LOW',
          'bg-severity-info': severity === 'INFO',
        })}
      />
      {config.label}
    </span>
  );
}

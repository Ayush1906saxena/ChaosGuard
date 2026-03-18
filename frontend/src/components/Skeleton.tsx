import { cn } from '@/lib/utils';

function SkeletonBase({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-lg bg-white/[0.04]',
        className
      )}
    />
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('glass-card rounded-2xl p-6 space-y-4', className)}>
      <SkeletonBase className="h-4 w-1/3" />
      <SkeletonBase className="h-8 w-1/2" />
      <SkeletonBase className="h-3 w-2/3" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="glass-card rounded-2xl overflow-hidden">
      <div className="border-b border-white/[0.04] px-6 py-3.5 flex gap-8">
        {[...Array(5)].map((_, i) => (
          <SkeletonBase key={i} className="h-3 w-20" />
        ))}
      </div>
      {[...Array(rows)].map((_, i) => (
        <div key={i} className="px-6 py-4 flex gap-8 border-b border-white/[0.02]">
          {[...Array(5)].map((_, j) => (
            <SkeletonBase key={j} className="h-3 w-20" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {[...Array(lines)].map((_, i) => (
        <SkeletonBase
          key={i}
          className={cn('h-3', i === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  );
}

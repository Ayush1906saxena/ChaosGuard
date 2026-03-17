'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import { getScan } from '@/lib/api';
import { extractRepoName } from '@/lib/utils';
import type { Scan, ScanStatus } from '@/lib/types';

const statusConfig: Record<ScanStatus, { label: string; color: string }> = {
  QUEUED: { label: 'Queued', color: 'bg-zinc-500' },
  CLONING: { label: 'Cloning', color: 'bg-blue-500 animate-pulse' },
  CLONING_COMPLETE: { label: 'Cloned', color: 'bg-blue-500' },
  INDEXING: { label: 'Indexing', color: 'bg-blue-500 animate-pulse' },
  INDEXING_COMPLETE: { label: 'Indexed', color: 'bg-blue-500' },
  ANALYZING: { label: 'Analyzing', color: 'bg-purple-500 animate-pulse' },
  GENERATING_FIXES: { label: 'Generating Fixes', color: 'bg-purple-500 animate-pulse' },
  COMPLETE: { label: 'Complete', color: 'bg-green-500' },
  FAILED: { label: 'Failed', color: 'bg-red-500' },
};

export default function ScanLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getScan(scanId).then(setScan).catch(() => {});
  }, [scanId]);

  const isSiege = scan?.tier === 'SIEGE';
  const statusInfo = scan ? statusConfig[scan.status] : null;

  return (
    <div className="flex min-h-screen">
      <Sidebar scanId={scanId} isSiege={isSiege} />

      <main className="flex-1 lg:ml-64">
        {/* Scan Header Bar */}
        {scan && (
          <div className="sticky top-0 z-20 bg-zinc-950/90 backdrop-blur-md border-b border-zinc-800 px-6 py-3">
            <div className="flex items-center justify-between max-w-7xl mx-auto">
              <div className="flex items-center gap-4">
                <h2 className="text-sm font-semibold text-zinc-200">
                  {extractRepoName(scan.repoUrl)}
                </h2>
                <span className="text-xs text-zinc-500 font-mono">
                  {scan.branch}
                </span>
              </div>
              <div className="flex items-center gap-3">
                {statusInfo && (
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${statusInfo.color}`} />
                    <span className="text-xs text-zinc-400">{statusInfo.label}</span>
                  </div>
                )}
                <span className="text-[10px] text-zinc-600 font-mono">
                  {scanId.slice(0, 8)}
                </span>
              </div>
            </div>
          </div>
        )}

        <div className="p-6 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}

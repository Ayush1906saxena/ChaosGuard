'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Breadcrumbs from '@/components/Breadcrumbs';
import { getScan } from '@/lib/api';
import { extractRepoName } from '@/lib/utils';
import type { Scan, ScanStatus } from '@/lib/types';

const statusConfig: Record<ScanStatus, { label: string; color: string; active: boolean }> = {
  QUEUED: { label: 'Queued', color: 'bg-zinc-500', active: false },
  CLONING: { label: 'Cloning', color: 'bg-blue-500', active: true },
  CLONING_COMPLETE: { label: 'Cloned', color: 'bg-blue-500', active: false },
  INDEXING: { label: 'Indexing', color: 'bg-blue-500', active: true },
  INDEXING_COMPLETE: { label: 'Indexed', color: 'bg-blue-500', active: false },
  ANALYZING: { label: 'Analyzing', color: 'bg-purple-500', active: true },
  GENERATING_FIXES: { label: 'Generating Fixes', color: 'bg-purple-500', active: true },
  COMPLETE: { label: 'Complete', color: 'bg-emerald-500', active: false },
  FAILED: { label: 'Failed', color: 'bg-red-500', active: false },
};

export default function ScanLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getScan(scanId)
      .then(setScan)
      .catch((err) => {
        setScanError(err instanceof Error ? err.message : 'Failed to load scan');
      });
  }, [scanId]);

  const isSiege = scan?.tier === 'SIEGE';
  const statusInfo = scan ? statusConfig[scan.status] : null;

  return (
    <div className="flex min-h-screen">
      <Sidebar scanId={scanId} isSiege={isSiege} />

      <main className="flex-1 lg:ml-64">
        {/* Scan Error Banner */}
        {scanError && (
          <div className="sticky top-0 z-20 bg-red-500/10 border-b border-red-500/20 px-6 py-3">
            <div className="flex items-center gap-3 max-w-7xl mx-auto">
              <span className="text-sm text-red-400">{scanError}</span>
              <button
                onClick={() => window.location.reload()}
                className="text-xs text-red-300 underline hover:text-red-200"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Scan Header Bar */}
        {scan && (
          <div className="sticky top-0 z-20 bg-[#050507]/80 backdrop-blur-xl border-b border-white/[0.04] px-6 py-3">
            <div className="flex items-center justify-between max-w-7xl mx-auto">
              <div className="flex items-center gap-4">
                <h2 className="text-sm font-semibold text-zinc-200">
                  {extractRepoName(scan.repoUrl)}
                </h2>
                <span className="text-xs text-zinc-600 font-mono px-2 py-0.5 rounded-md bg-white/[0.03]">
                  {scan.branch}
                </span>
              </div>
              <div className="flex items-center gap-4">
                {statusInfo && (
                  <div className="flex items-center gap-2">
                    <div className="relative flex h-2 w-2">
                      {statusInfo.active && (
                        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${statusInfo.color} opacity-75`} />
                      )}
                      <span className={`relative inline-flex rounded-full h-2 w-2 ${statusInfo.color}`} />
                    </div>
                    <span className="text-xs text-zinc-400">{statusInfo.label}</span>
                  </div>
                )}
                <span className="text-[10px] text-zinc-700 font-mono">
                  {scanId.slice(0, 8)}
                </span>
              </div>
            </div>
          </div>
        )}

        <div className="p-6 max-w-7xl mx-auto">
          <Breadcrumbs />
          {children}
        </div>
      </main>
    </div>
  );
}

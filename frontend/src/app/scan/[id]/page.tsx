'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import ScanProgress from '@/components/ScanProgress';
import TierBadge from '@/components/TierBadge';
import { getScan } from '@/lib/api';
import { formatDate, extractRepoName } from '@/lib/utils';
import type { Scan } from '@/lib/types';
import {
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

export default function ScanOverviewPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadScan = useCallback(async () => {
    try {
      const data = await getScan(scanId);
      setScan(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scan');
    }
  }, [scanId]);

  useEffect(() => {
    loadScan();
    const interval = setInterval(() => { loadScan(); }, 5000);
    return () => clearInterval(interval);
  }, [loadScan]);

  const handleScanComplete = useCallback(() => { loadScan(); }, [loadScan]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="glass-card glow-red rounded-xl px-6 py-4 text-sm text-red-400 max-w-md text-center">
          {error}
        </div>
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-zinc-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading scan...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Scan Info Header */}
      <div className="glass-card rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100 mb-1">
              {extractRepoName(scan.repoUrl)}
            </h1>
            <p className="text-sm text-zinc-600 font-mono">{scan.repoUrl}</p>
          </div>
          <div className="flex items-center gap-3">
            <TierBadge tier={scan.tier} />
            <span className="text-xs text-zinc-600">
              Started {formatDate(scan.createdAt)}
            </span>
          </div>
        </div>

        {/* Repo Metadata */}
        {scan.repoMetadata && (() => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const meta = scan.repoMetadata as any;
          return (
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3 stagger-children">
              {[
                { label: 'Language', value: meta.primaryLanguage || meta.language || 'Unknown' },
                { label: 'Files', value: (meta.sourceFileCount || meta.fileCount || 0).toLocaleString() },
                { label: 'Total Files', value: (meta.totalFiles || meta.totalLines || 0).toLocaleString() },
                { label: 'Branch', value: scan.branch },
              ].map((item) => (
                <div key={item.label} className="bg-white/[0.02] border border-white/[0.04] rounded-xl px-4 py-3">
                  <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-medium">{item.label}</p>
                  <p className="text-sm text-zinc-200 mt-1 truncate font-medium">{item.value}</p>
                </div>
              ))}
            </div>
          );
        })()}

        {/* Summary Cards */}
        {scan.summary && (
          <div className="mt-6 grid grid-cols-2 md:grid-cols-6 gap-3 stagger-children">
            {[
              { label: 'Total', value: scan.summary.totalFindings, color: 'text-zinc-100' },
              { label: 'Critical', value: scan.summary.criticalCount, color: 'text-red-400' },
              { label: 'High', value: scan.summary.highCount, color: 'text-orange-400' },
              { label: 'Medium', value: scan.summary.mediumCount, color: 'text-yellow-400' },
              { label: 'Low', value: scan.summary.lowCount, color: 'text-blue-400' },
              { label: 'Fixes', value: scan.summary.fixesGenerated, color: 'text-emerald-400' },
            ].map((item) => (
              <div key={item.label} className="bg-white/[0.02] border border-white/[0.04] rounded-xl px-3 py-3.5 text-center">
                <p className={`text-2xl font-bold ${item.color} animate-count-up`}>{item.value}</p>
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider mt-1 font-medium">{item.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Live Progress */}
      {scan.status !== 'COMPLETE' && scan.status !== 'FAILED' && (
        <ScanProgress scanId={scanId} initialStatus={scan.status} onComplete={handleScanComplete} />
      )}

      {/* Completed Status */}
      {scan.status === 'COMPLETE' && scan.summary && (
        <div className="glass-card glow-green rounded-2xl p-6 border-emerald-500/10">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <CheckCircleIcon className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-emerald-400">Scan Complete</h3>
              <p className="text-sm text-zinc-500">
                {scan.summary.agentsCompleted} agents completed &middot; {scan.summary.totalFindings} findings
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger-children">
            {[
              { label: 'Attack Chains', value: scan.summary.attackChainsFound },
              { label: 'Chaos Scenarios', value: scan.summary.chaosScenarios },
              { label: 'Fixes Generated', value: scan.summary.fixesGenerated },
              { label: 'Agents Used', value: scan.summary.totalAgents },
            ].map((item) => (
              <div key={item.label} className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-4 text-center">
                <p className="text-xl font-bold text-zinc-200">{item.value}</p>
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider mt-1 font-medium">{item.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Failed Status */}
      {scan.status === 'FAILED' && (
        <div className="glass-card glow-red rounded-2xl p-6 border-red-500/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
              <XCircleIcon className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-red-400">Scan Failed</h3>
              <p className="text-sm text-zinc-400 mt-1">
                {scan.errorMessage || 'An unexpected error occurred during the scan.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

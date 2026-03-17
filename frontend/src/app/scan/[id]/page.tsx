'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import ScanProgress from '@/components/ScanProgress';
import SeverityBadge from '@/components/SeverityBadge';
import TierBadge from '@/components/TierBadge';
import { getScan } from '@/lib/api';
import { formatDate, extractRepoName } from '@/lib/utils';
import type { Scan } from '@/lib/types';

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
    // Poll for status updates every 5 seconds while scan is in progress
    const interval = setInterval(() => {
      loadScan();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadScan]);

  const handleScanComplete = useCallback(() => {
    loadScan();
  }, [loadScan]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-6 py-4 text-sm text-red-400 max-w-md text-center">
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
    <div className="space-y-8">
      {/* Scan Info Header */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100 mb-1">
              {extractRepoName(scan.repoUrl)}
            </h1>
            <p className="text-sm text-zinc-500 font-mono">{scan.repoUrl}</p>
          </div>
          <div className="flex items-center gap-3">
            <TierBadge tier={scan.tier} />
            <span className="text-xs text-zinc-500">
              Started {formatDate(scan.createdAt)}
            </span>
          </div>
        </div>

        {/* Repo Metadata */}
        {scan.repoMetadata && (() => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const meta = scan.repoMetadata as any;
          return (
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Language', value: meta.primaryLanguage || meta.language || 'Unknown' },
                { label: 'Files', value: (meta.sourceFileCount || meta.fileCount || 0).toLocaleString() },
                { label: 'Total Files', value: (meta.totalFiles || meta.totalLines || 0).toLocaleString() },
                { label: 'Branch', value: scan.branch },
              ].map((item) => (
                <div key={item.label} className="bg-zinc-800/50 rounded-lg px-3 py-2">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{item.label}</p>
                  <p className="text-sm text-zinc-200 mt-0.5 truncate">{item.value}</p>
                </div>
              ))}
            </div>
          );
        })()}

        {/* Summary Cards */}
        {scan.summary && (
          <div className="mt-6 grid grid-cols-2 md:grid-cols-6 gap-3">
            {[
              { label: 'Total', value: scan.summary.totalFindings, color: 'text-zinc-200' },
              { label: 'Critical', value: scan.summary.criticalCount, color: 'text-red-400' },
              { label: 'High', value: scan.summary.highCount, color: 'text-orange-400' },
              { label: 'Medium', value: scan.summary.mediumCount, color: 'text-yellow-400' },
              { label: 'Low', value: scan.summary.lowCount, color: 'text-blue-400' },
              { label: 'Fixes', value: scan.summary.fixesGenerated, color: 'text-green-400' },
            ].map((item) => (
              <div key={item.label} className="bg-zinc-800/30 border border-zinc-700/30 rounded-lg px-3 py-3 text-center">
                <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">{item.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Live Progress */}
      {scan.status !== 'COMPLETE' && scan.status !== 'FAILED' && (
        <ScanProgress
          scanId={scanId}
          initialStatus={scan.status}
          onComplete={handleScanComplete}
        />
      )}

      {/* Completed Status */}
      {scan.status === 'COMPLETE' && scan.summary && (
        <div className="bg-green-500/5 border border-green-500/20 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-green-400">Scan Complete</h3>
              <p className="text-sm text-zinc-500">
                {scan.summary.agentsCompleted} agents completed | {scan.summary.totalFindings} findings
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <div className="bg-zinc-800/30 rounded-lg p-3 text-center">
              <p className="text-lg font-bold text-zinc-200">{scan.summary.attackChainsFound}</p>
              <p className="text-[10px] text-zinc-500 uppercase">Attack Chains</p>
            </div>
            <div className="bg-zinc-800/30 rounded-lg p-3 text-center">
              <p className="text-lg font-bold text-zinc-200">{scan.summary.chaosScenarios}</p>
              <p className="text-[10px] text-zinc-500 uppercase">Chaos Scenarios</p>
            </div>
            <div className="bg-zinc-800/30 rounded-lg p-3 text-center">
              <p className="text-lg font-bold text-zinc-200">{scan.summary.fixesGenerated}</p>
              <p className="text-[10px] text-zinc-500 uppercase">Fixes Generated</p>
            </div>
            <div className="bg-zinc-800/30 rounded-lg p-3 text-center">
              <p className="text-lg font-bold text-zinc-200">{scan.summary.totalAgents}</p>
              <p className="text-[10px] text-zinc-500 uppercase">Agents Used</p>
            </div>
          </div>
        </div>
      )}

      {/* Failed Status */}
      {scan.status === 'FAILED' && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
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

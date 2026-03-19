'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import TierSelector from '@/components/TierSelector';
import TierBadge from '@/components/TierBadge';
import { SkeletonTable } from '@/components/Skeleton';
import { createScan, listScans } from '@/lib/api';
import { formatDate, extractRepoName } from '@/lib/utils';
import type { ScanTier, Scan, ScanStatus } from '@/lib/types';
import {
  ArrowRightIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

const statusStyles: Record<ScanStatus, { label: string; classes: string; dot: string }> = {
  QUEUED: { label: 'Queued', classes: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20', dot: 'bg-zinc-400' },
  CLONING: { label: 'Cloning', classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20', dot: 'bg-blue-400 animate-pulse' },
  CLONING_COMPLETE: { label: 'Cloned', classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20', dot: 'bg-blue-400' },
  INDEXING: { label: 'Indexing', classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20', dot: 'bg-blue-400 animate-pulse' },
  INDEXING_COMPLETE: { label: 'Indexed', classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20', dot: 'bg-blue-400' },
  ANALYZING: { label: 'Analyzing', classes: 'bg-purple-500/10 text-purple-400 border-purple-500/20', dot: 'bg-purple-400 animate-pulse' },
  GENERATING_FIXES: { label: 'Fixing', classes: 'bg-purple-500/10 text-purple-400 border-purple-500/20', dot: 'bg-purple-400 animate-pulse' },
  COMPLETE: { label: 'Complete', classes: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', dot: 'bg-emerald-400' },
  FAILED: { label: 'Failed', classes: 'bg-red-500/10 text-red-400 border-red-500/20', dot: 'bg-red-400' },
};

export default function DashboardPage() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [tier, setTier] = useState<ScanTier>('HUNTER');
  const [targetUrl, setTargetUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentScans, setRecentScans] = useState<Scan[]>([]);
  const [loadingScans, setLoadingScans] = useState(true);
  const [scansError, setScansError] = useState<string | null>(null);

  useEffect(() => {
    loadRecentScans();
  }, []);

  async function loadRecentScans() {
    try {
      setScansError(null);
      const response = await listScans(0, 10);
      setRecentScans(response.content);
    } catch (err) {
      setScansError(err instanceof Error ? err.message : 'Failed to load recent scans. Is the backend running?');
    } finally {
      setLoadingScans(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const url = repoUrl.trim();
    if (!url) return;

    if (!url.startsWith('https://') && !url.startsWith('http://') && !url.startsWith('git@')) {
      setError('Please enter a valid repository URL (e.g. https://github.com/owner/repo)');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const req: { repoUrl: string; branch: string; tier: typeof tier; targetUrl?: string } = {
        repoUrl: repoUrl.trim(), branch, tier,
      };
      if (tier === 'LIVE' && targetUrl.trim()) {
        req.targetUrl = targetUrl.trim();
      }
      const scan = await createScan(req);
      router.push(`/scan/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start scan');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 lg:ml-64">
        <div className="max-w-5xl mx-auto px-6 py-16">
          {/* Hero Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="text-center mb-16">
            <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full glass-card mb-8">
              <div className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-400" />
              </div>
              <span className="text-[11px] text-zinc-400 font-medium tracking-widest uppercase">Autonomous Security</span>
            </div>
            <h1 className="text-6xl font-bold tracking-tight mb-5">
              <span className="gradient-text">ChaosGuard AI</span>
            </h1>
            <p className="text-lg text-zinc-500 max-w-2xl mx-auto leading-relaxed">
              Multi-agent AI security platform that autonomously scans repositories,
              discovers attack chains, runs chaos engineering, and generates verified fixes.
            </p>
          </motion.div>

          {/* Scan Form */}
          <motion.form
            onSubmit={handleSubmit}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15, ease: 'easeOut' }}
            className="space-y-8 mb-20">
            <div className="glass-card rounded-2xl p-8 animate-slide-up">
              <h2 className="text-base font-semibold text-zinc-200 mb-6 flex items-center gap-2">
                <div className="w-1 h-4 rounded-full bg-gradient-to-b from-red-500 to-orange-500" />
                New Security Scan
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-[1fr,200px] gap-4">
                {/* GitHub URL */}
                <div>
                  <label htmlFor="repoUrl" className="block text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wider">
                    Repository URL
                  </label>
                  <input
                    id="repoUrl"
                    type="url"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/owner/repository"
                    required
                    className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3.5 text-sm text-zinc-200 placeholder-zinc-600 focus:ring-2 focus:ring-red-500/30 focus:border-red-500/30 transition-all"
                  />
                </div>

                {/* Branch */}
                <div>
                  <label htmlFor="branch" className="block text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wider">
                    Branch
                  </label>
                  <input
                    id="branch"
                    type="text"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main or master"
                    className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3.5 text-sm text-zinc-200 placeholder-zinc-600 focus:ring-2 focus:ring-red-500/30 focus:border-red-500/30 transition-all"
                  />
                  <p className="text-[10px] text-zinc-600 mt-1">Auto-fallback: tries main → master if not found</p>
                </div>
              </div>
            </div>

            {/* Tier Selection */}
            <div className="animate-slide-up" style={{ animationDelay: '0.1s', animationFillMode: 'backwards' }}>
              <h3 className="text-xs font-medium text-zinc-500 mb-4 uppercase tracking-wider">Select Scan Tier</h3>
              <TierSelector selectedTier={tier} onSelect={setTier} />

              {/* Target URL for LIVE tier */}
              {tier === 'LIVE' && (
                <div className="mt-6 glass-card rounded-2xl p-6">
                  <label htmlFor="targetUrl" className="block text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wider">
                    Target URL (running application)
                  </label>
                  <input
                    id="targetUrl"
                    type="url"
                    value={targetUrl}
                    onChange={(e) => setTargetUrl(e.target.value)}
                    placeholder="http://localhost:3003"
                    required
                    className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3.5 text-sm text-zinc-200 placeholder-zinc-600 focus:ring-2 focus:ring-red-500/30 focus:border-red-500/30 transition-all"
                  />
                  <p className="text-[10px] text-zinc-600 mt-1">
                    LIVE tier runs active DAST probes (SQLi, IDOR, auth bypass) against a running target
                  </p>
                </div>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-3 glass-card glow-red rounded-xl px-5 py-4 text-sm text-red-400 animate-scale-in">
                <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !repoUrl.trim()}
              className="group w-full py-4 px-6 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 disabled:from-zinc-800 disabled:to-zinc-800 disabled:text-zinc-600 text-white font-semibold rounded-xl transition-all duration-300 text-sm tracking-wide shadow-lg shadow-red-500/20 hover:shadow-red-500/30 disabled:shadow-none flex items-center justify-center gap-2"
            >
              {loading ? (
                <span className="flex items-center gap-3">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Initializing Scan...
                </span>
              ) : (
                <>
                  Launch Scan
                  <ArrowRightIcon className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </motion.form>

          {/* Recent Scans */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3, ease: 'easeOut' }}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold text-zinc-200 flex items-center gap-2">
                <div className="w-1 h-4 rounded-full bg-gradient-to-b from-blue-500 to-purple-500" />
                Recent Scans
              </h2>
              <span className="text-xs text-zinc-600">{recentScans.length} scan{recentScans.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="glass-card rounded-2xl overflow-hidden">
              {scansError ? (
                <div className="px-6 py-8 text-center">
                  <ExclamationTriangleIcon className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                  <p className="text-sm text-zinc-400 mb-1">Could not load recent scans</p>
                  <p className="text-xs text-zinc-600 mb-4">{scansError}</p>
                  <button
                    onClick={loadRecentScans}
                    className="px-4 py-2 text-xs font-medium bg-white/[0.04] border border-white/[0.06] text-zinc-400 rounded-lg hover:bg-white/[0.08] hover:text-zinc-200 transition-colors"
                  >
                    Retry
                  </button>
                </div>
              ) : loadingScans ? (
                <div className="p-4">
                  <SkeletonTable rows={3} />
                </div>
              ) : recentScans.length === 0 ? (
                <div className="px-6 py-16 text-center">
                  <p className="text-zinc-600 text-sm">No scans yet. Launch your first scan above.</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.04]">
                      <th className="px-6 py-3.5 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Repository</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Tier</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Findings</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    {recentScans.map((scan) => {
                      const st = statusStyles[scan.status];
                      return (
                        <tr
                          key={scan.id}
                          onClick={() => router.push(`/scan/${scan.id}`)}
                          className="cursor-pointer table-row-hover group"
                        >
                          <td className="px-6 py-4">
                            <div className="font-medium text-zinc-200 group-hover:text-white transition-colors">
                              {extractRepoName(scan.repoUrl)}
                            </div>
                            <div className="text-[11px] text-zinc-600 mt-0.5 font-mono">
                              {scan.branch}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <TierBadge tier={scan.tier} size="sm" />
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border ${st.classes}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
                              {st.label}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-zinc-400 font-mono text-xs">
                              {scan.summary?.totalFindings ?? '-'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-zinc-600 text-xs">
                            {formatDate(scan.createdAt)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  );
}

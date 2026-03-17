'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import TierSelector from '@/components/TierSelector';
import TierBadge from '@/components/TierBadge';
import { createScan, listScans } from '@/lib/api';
import { formatDate, extractRepoName } from '@/lib/utils';
import type { ScanTier, Scan, ScanStatus } from '@/lib/types';

const statusStyles: Record<ScanStatus, { label: string; classes: string }> = {
  QUEUED: { label: 'Queued', classes: 'bg-zinc-700/30 text-zinc-400' },
  CLONING: { label: 'Cloning', classes: 'bg-blue-500/15 text-blue-400' },
  CLONING_COMPLETE: { label: 'Cloned', classes: 'bg-blue-500/15 text-blue-400' },
  INDEXING: { label: 'Indexing', classes: 'bg-blue-500/15 text-blue-400' },
  INDEXING_COMPLETE: { label: 'Indexed', classes: 'bg-blue-500/15 text-blue-400' },
  ANALYZING: { label: 'Analyzing', classes: 'bg-purple-500/15 text-purple-400' },
  GENERATING_FIXES: { label: 'Generating Fixes', classes: 'bg-purple-500/15 text-purple-400' },
  COMPLETE: { label: 'Complete', classes: 'bg-green-500/15 text-green-400' },
  FAILED: { label: 'Failed', classes: 'bg-red-500/15 text-red-400' },
};

export default function DashboardPage() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [tier, setTier] = useState<ScanTier>('HUNTER');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentScans, setRecentScans] = useState<Scan[]>([]);
  const [loadingScans, setLoadingScans] = useState(true);

  useEffect(() => {
    loadRecentScans();
  }, []);

  async function loadRecentScans() {
    try {
      const response = await listScans(0, 10);
      setRecentScans(response.content);
    } catch {
      // Silently handle - scans table will be empty
    } finally {
      setLoadingScans(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!repoUrl.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const scan = await createScan({ repoUrl: repoUrl.trim(), branch, tier });
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
        <div className="max-w-5xl mx-auto px-6 py-12">
          {/* Hero Section */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/20 mb-6">
              <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              <span className="text-xs text-red-400 font-medium tracking-wide">AUTONOMOUS SECURITY</span>
            </div>
            <h1 className="text-5xl font-bold tracking-tight mb-4">
              <span className="bg-gradient-to-r from-red-400 via-orange-400 to-amber-400 bg-clip-text text-transparent">
                ChaosGuard AI
              </span>
            </h1>
            <p className="text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
              Multi-agent AI security platform that autonomously scans repositories,
              discovers attack chains, runs chaos engineering scenarios, and generates
              verified fixes.
            </p>
          </div>

          {/* Scan Form */}
          <form onSubmit={handleSubmit} className="space-y-8 mb-16">
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8">
              <h2 className="text-lg font-semibold text-zinc-200 mb-6">Start a New Scan</h2>

              <div className="space-y-4">
                {/* GitHub URL */}
                <div>
                  <label htmlFor="repoUrl" className="block text-sm font-medium text-zinc-400 mb-2">
                    GitHub Repository URL
                  </label>
                  <input
                    id="repoUrl"
                    type="url"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/owner/repository"
                    required
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500/50 transition-colors"
                  />
                </div>

                {/* Branch */}
                <div>
                  <label htmlFor="branch" className="block text-sm font-medium text-zinc-400 mb-2">
                    Branch
                  </label>
                  <input
                    id="branch"
                    type="text"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500/50 transition-colors max-w-xs"
                  />
                </div>
              </div>
            </div>

            {/* Tier Selection */}
            <div>
              <h3 className="text-sm font-medium text-zinc-400 mb-4">Select Scan Tier</h3>
              <TierSelector selectedTier={tier} onSelect={setTier} />
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !repoUrl.trim()}
              className="w-full py-4 px-6 bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 disabled:from-zinc-700 disabled:to-zinc-700 disabled:text-zinc-500 text-white font-semibold rounded-xl transition-all duration-300 text-sm tracking-wide shadow-lg shadow-red-500/20 disabled:shadow-none"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Starting Scan...
                </span>
              ) : (
                'Start Scan'
              )}
            </button>
          </form>

          {/* Recent Scans */}
          <div>
            <h2 className="text-lg font-semibold text-zinc-200 mb-4">Recent Scans</h2>
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
              {loadingScans ? (
                <div className="px-6 py-12 text-center text-zinc-500 text-sm">
                  Loading recent scans...
                </div>
              ) : recentScans.length === 0 ? (
                <div className="px-6 py-12 text-center text-zinc-500 text-sm">
                  No scans yet. Start your first scan above.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                        Repository
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                        Tier
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                        Findings
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {recentScans.map((scan) => {
                      const st = statusStyles[scan.status];
                      return (
                        <tr
                          key={scan.id}
                          onClick={() => router.push(`/scan/${scan.id}`)}
                          className="cursor-pointer hover:bg-zinc-800/50 transition-colors"
                        >
                          <td className="px-6 py-4">
                            <div className="font-medium text-zinc-200">
                              {extractRepoName(scan.repoUrl)}
                            </div>
                            <div className="text-xs text-zinc-500 mt-0.5 font-mono">
                              {scan.branch}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <TierBadge tier={scan.tier} size="sm" />
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${st.classes}`}>
                              {st.label}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-zinc-400">
                            {scan.summary?.totalFindings ?? '-'}
                          </td>
                          <td className="px-6 py-4 text-zinc-500 text-xs">
                            {formatDate(scan.createdAt)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import type { BenchmarkRun } from '@/lib/types';

export default function MetricsPage() {
  const [runs, setRuns] = useState<BenchmarkRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In a real app, fetch from API. For now, show placeholder.
    setLoading(false);
  }, []);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">ChaosGuard Metrics</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Precision/recall tracking across benchmark runs on known-vulnerable repositories.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <div className="flex items-center gap-3 text-zinc-500">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading metrics...
          </div>
        </div>
      ) : runs.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center">
          <h2 className="text-lg font-medium text-zinc-300 mb-2">No benchmark data yet</h2>
          <p className="text-zinc-500 text-sm mb-4">
            Run the benchmark suite to generate precision/recall data:
          </p>
          <code className="inline-block bg-black/30 border border-white/[0.06] text-zinc-300 px-4 py-2.5 rounded-xl text-sm font-mono">
            python scripts/benchmark/run_benchmarks.py --api-url http://localhost:8080
          </code>
        </div>
      ) : (
        <div className="space-y-6 stagger-children">
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-card glow-green rounded-2xl p-6 border-emerald-500/10">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Avg Precision</div>
              <div className="text-3xl font-bold text-green-400 animate-count-up">
                {(runs.reduce((s, r) => s + r.precisionScore, 0) / runs.length * 100).toFixed(1)}%
              </div>
            </div>
            <div className="glass-card rounded-2xl p-6">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Avg Recall</div>
              <div className="text-3xl font-bold text-blue-400 animate-count-up">
                {(runs.reduce((s, r) => s + r.recallScore, 0) / runs.length * 100).toFixed(1)}%
              </div>
            </div>
            <div className="glass-card rounded-2xl p-6">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Avg F1</div>
              <div className="text-3xl font-bold text-purple-400 animate-count-up">
                {(runs.reduce((s, r) => s + r.f1Score, 0) / runs.length * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Results table */}
          <div className="glass-card rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.04] bg-white/[0.02]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Repository</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Tier</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Precision</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Recall</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">F1</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Duration</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {runs.map((run) => (
                  <tr key={run.id} className="table-row-hover">
                    <td className="px-4 py-3 font-medium text-zinc-200">{run.repoUrl.split('/').pop()}</td>
                    <td className="px-4 py-3 text-zinc-400">{run.tier}</td>
                    <td className="px-4 py-3 text-green-400 font-mono">{(run.precisionScore * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-blue-400 font-mono">{(run.recallScore * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-purple-400 font-mono">{(run.f1Score * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-zinc-400 font-mono">{run.scanDurationS.toFixed(0)}s</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">{new Date(run.runAt).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

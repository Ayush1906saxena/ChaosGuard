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
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">ChaosGuard Metrics</h1>
        <p className="text-zinc-400 mb-8">
          Precision/recall tracking across benchmark runs on known-vulnerable repositories.
        </p>

        {loading ? (
          <div className="text-center text-zinc-500 py-20">Loading metrics...</div>
        ) : runs.length === 0 ? (
          <div className="border border-zinc-800 rounded-xl p-12 text-center">
            <h2 className="text-lg font-medium text-zinc-300 mb-2">No benchmark data yet</h2>
            <p className="text-zinc-500 text-sm mb-4">
              Run the benchmark suite to generate precision/recall data:
            </p>
            <code className="bg-zinc-900 text-zinc-300 px-4 py-2 rounded-lg text-sm block">
              python scripts/benchmark/run_benchmarks.py --api-url http://localhost:8080
            </code>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Avg Precision</div>
                <div className="text-3xl font-bold text-green-400">
                  {(runs.reduce((s, r) => s + r.precisionScore, 0) / runs.length * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Avg Recall</div>
                <div className="text-3xl font-bold text-blue-400">
                  {(runs.reduce((s, r) => s + r.recallScore, 0) / runs.length * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Avg F1</div>
                <div className="text-3xl font-bold text-purple-400">
                  {(runs.reduce((s, r) => s + r.f1Score, 0) / runs.length * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Results table */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-900/50">
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Repository</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Tier</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Precision</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Recall</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">F1</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {runs.map((run) => (
                    <tr key={run.id} className="hover:bg-zinc-800/50">
                      <td className="px-4 py-3 font-medium text-zinc-200">{run.repoUrl.split('/').pop()}</td>
                      <td className="px-4 py-3 text-zinc-400">{run.tier}</td>
                      <td className="px-4 py-3 text-green-400">{(run.precisionScore * 100).toFixed(1)}%</td>
                      <td className="px-4 py-3 text-blue-400">{(run.recallScore * 100).toFixed(1)}%</td>
                      <td className="px-4 py-3 text-purple-400">{(run.f1Score * 100).toFixed(1)}%</td>
                      <td className="px-4 py-3 text-zinc-400">{run.scanDurationS.toFixed(0)}s</td>
                      <td className="px-4 py-3 text-zinc-500 text-xs">{new Date(run.runAt).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

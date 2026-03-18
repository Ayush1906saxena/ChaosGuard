'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import { SkeletonCard } from '@/components/Skeleton';
import { listScans } from '@/lib/api';
import type { Scan } from '@/lib/types';
import { extractRepoName } from '@/lib/utils';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#22c55e',
  INFO: '#6b7280',
};

export default function MetricsPage() {
  const router = useRouter();
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const response = await listScans(0, 50);
        setScans(response.content);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load scan data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const completedScans = scans.filter(s => s.status === 'COMPLETE' && s.summary);

  // Severity distribution across all scans
  const severityData = completedScans.length > 0
    ? [
        { name: 'Critical', value: completedScans.reduce((s, scan) => s + (scan.summary?.criticalCount ?? 0), 0), color: SEVERITY_COLORS.CRITICAL },
        { name: 'High', value: completedScans.reduce((s, scan) => s + (scan.summary?.highCount ?? 0), 0), color: SEVERITY_COLORS.HIGH },
        { name: 'Medium', value: completedScans.reduce((s, scan) => s + (scan.summary?.mediumCount ?? 0), 0), color: SEVERITY_COLORS.MEDIUM },
        { name: 'Low', value: completedScans.reduce((s, scan) => s + (scan.summary?.lowCount ?? 0), 0), color: SEVERITY_COLORS.LOW },
        { name: 'Info', value: completedScans.reduce((s, scan) => s + (scan.summary?.infoCount ?? 0), 0), color: SEVERITY_COLORS.INFO },
      ].filter(d => d.value > 0)
    : [];

  // Findings per scan (bar chart)
  const findingsPerScan = completedScans.slice(-15).map(scan => ({
    name: extractRepoName(scan.repoUrl).slice(0, 15),
    findings: scan.summary?.totalFindings ?? 0,
    fixes: scan.summary?.fixesGenerated ?? 0,
    chains: scan.summary?.attackChainsFound ?? 0,
  }));

  // Scan timeline (area chart)
  const scanTimeline = completedScans.slice(-15).map(scan => ({
    date: new Date(scan.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    critical: scan.summary?.criticalCount ?? 0,
    high: scan.summary?.highCount ?? 0,
    medium: scan.summary?.mediumCount ?? 0,
    low: scan.summary?.lowCount ?? 0,
  }));

  // Totals
  const totalFindings = completedScans.reduce((s, scan) => s + (scan.summary?.totalFindings ?? 0), 0);
  const totalFixes = completedScans.reduce((s, scan) => s + (scan.summary?.fixesGenerated ?? 0), 0);
  const totalChains = completedScans.reduce((s, scan) => s + (scan.summary?.attackChainsFound ?? 0), 0);
  const totalChaos = completedScans.reduce((s, scan) => s + (scan.summary?.chaosScenarios ?? 0), 0);

  const tooltipStyle = {
    contentStyle: {
      background: 'rgba(24, 24, 27, 0.95)',
      border: '1px solid rgba(255, 255, 255, 0.06)',
      borderRadius: '12px',
      color: '#e4e4e7',
      fontSize: '12px',
      backdropFilter: 'blur(12px)',
    },
    itemStyle: { color: '#a1a1aa' },
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 lg:ml-64">
        <div className="max-w-7xl mx-auto px-6 py-10">
          <div className="mb-10">
            <h1 className="text-3xl font-bold text-zinc-100">Security Metrics</h1>
            <p className="text-sm text-zinc-500 mt-1">
              Aggregated insights across {completedScans.length} completed scan{completedScans.length !== 1 ? 's' : ''}
            </p>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : error ? (
            <div className="glass-card rounded-2xl p-12 text-center">
              <p className="text-red-400 text-sm mb-2">Failed to load metrics</p>
              <p className="text-zinc-600 text-xs mb-4">{error}</p>
              <button onClick={() => window.location.reload()} className="px-4 py-2 text-xs bg-white/[0.04] border border-white/[0.06] text-zinc-400 rounded-lg hover:bg-white/[0.08] transition-colors">
                Retry
              </button>
            </div>
          ) : completedScans.length === 0 ? (
            <div className="glass-card rounded-2xl p-12 text-center">
              <h2 className="text-lg font-medium text-zinc-300 mb-2">No completed scans yet</h2>
              <p className="text-zinc-500 text-sm mb-6">
                Run a security scan to see aggregated metrics here.
              </p>
              <button
                onClick={() => router.push('/')}
                className="px-6 py-2.5 bg-gradient-to-r from-red-600 to-orange-600 text-white rounded-xl text-sm font-semibold hover:from-red-500 hover:to-orange-500 transition-all"
              >
                Launch a Scan
              </button>
            </div>
          ) : (
            <div className="space-y-8">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-card rounded-2xl p-6">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Total Findings</div>
                  <div className="text-3xl font-bold text-zinc-100">{totalFindings.toLocaleString()}</div>
                </div>
                <div className="glass-card glow-green rounded-2xl p-6 border-emerald-500/10">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Fixes Generated</div>
                  <div className="text-3xl font-bold text-emerald-400">{totalFixes.toLocaleString()}</div>
                </div>
                <div className="glass-card rounded-2xl p-6">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Attack Chains</div>
                  <div className="text-3xl font-bold text-orange-400">{totalChains.toLocaleString()}</div>
                </div>
                <div className="glass-card rounded-2xl p-6">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Chaos Scenarios</div>
                  <div className="text-3xl font-bold text-purple-400">{totalChaos.toLocaleString()}</div>
                </div>
              </div>

              {/* Charts Row 1: Severity Pie + Findings Bar */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Severity Distribution */}
                <div className="glass-card rounded-2xl p-6">
                  <h3 className="text-sm font-semibold text-zinc-200 mb-6 flex items-center gap-2">
                    <div className="w-1 h-4 rounded-full bg-gradient-to-b from-red-500 to-yellow-500" />
                    Severity Distribution
                  </h3>
                  {severityData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie
                          data={severityData}
                          cx="50%"
                          cy="50%"
                          innerRadius={70}
                          outerRadius={110}
                          paddingAngle={3}
                          dataKey="value"
                          stroke="none"
                        >
                          {severityData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip {...tooltipStyle} />
                        <Legend
                          verticalAlign="bottom"
                          iconType="circle"
                          iconSize={8}
                          formatter={(value) => <span className="text-xs text-zinc-400">{value}</span>}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-[280px] flex items-center justify-center text-zinc-600 text-sm">No data</div>
                  )}
                </div>

                {/* Findings per Scan */}
                <div className="glass-card rounded-2xl p-6">
                  <h3 className="text-sm font-semibold text-zinc-200 mb-6 flex items-center gap-2">
                    <div className="w-1 h-4 rounded-full bg-gradient-to-b from-blue-500 to-purple-500" />
                    Findings per Scan
                  </h3>
                  {findingsPerScan.length > 0 ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={findingsPerScan}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                        <XAxis dataKey="name" tick={{ fill: '#71717a', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.06)' }} />
                        <YAxis tick={{ fill: '#71717a', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.06)' }} />
                        <Tooltip {...tooltipStyle} />
                        <Bar dataKey="findings" fill="#ef4444" radius={[4, 4, 0, 0]} name="Findings" />
                        <Bar dataKey="fixes" fill="#22c55e" radius={[4, 4, 0, 0]} name="Fixes" />
                        <Bar dataKey="chains" fill="#f97316" radius={[4, 4, 0, 0]} name="Chains" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-[280px] flex items-center justify-center text-zinc-600 text-sm">No data</div>
                  )}
                </div>
              </div>

              {/* Chart Row 2: Severity Timeline */}
              <div className="glass-card rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-zinc-200 mb-6 flex items-center gap-2">
                  <div className="w-1 h-4 rounded-full bg-gradient-to-b from-orange-500 to-red-500" />
                  Severity Trend Across Scans
                </h3>
                {scanTimeline.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={scanTimeline}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.06)' }} />
                      <YAxis tick={{ fill: '#71717a', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.06)' }} />
                      <Tooltip {...tooltipStyle} />
                      <Legend
                        verticalAlign="top"
                        iconType="circle"
                        iconSize={8}
                        formatter={(value) => <span className="text-xs text-zinc-400 capitalize">{value}</span>}
                      />
                      <Area type="monotone" dataKey="critical" stackId="1" stroke={SEVERITY_COLORS.CRITICAL} fill={SEVERITY_COLORS.CRITICAL} fillOpacity={0.3} />
                      <Area type="monotone" dataKey="high" stackId="1" stroke={SEVERITY_COLORS.HIGH} fill={SEVERITY_COLORS.HIGH} fillOpacity={0.3} />
                      <Area type="monotone" dataKey="medium" stackId="1" stroke={SEVERITY_COLORS.MEDIUM} fill={SEVERITY_COLORS.MEDIUM} fillOpacity={0.3} />
                      <Area type="monotone" dataKey="low" stackId="1" stroke={SEVERITY_COLORS.LOW} fill={SEVERITY_COLORS.LOW} fillOpacity={0.3} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[300px] flex items-center justify-center text-zinc-600 text-sm">No data</div>
                )}
              </div>

              {/* Scan History Table */}
              <div className="glass-card rounded-2xl overflow-hidden">
                <div className="px-6 py-4 border-b border-white/[0.04]">
                  <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                    <div className="w-1 h-4 rounded-full bg-gradient-to-b from-emerald-500 to-cyan-500" />
                    Scan History
                  </h3>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.04]">
                      <th className="px-6 py-3 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Repository</th>
                      <th className="px-6 py-3 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Findings</th>
                      <th className="px-6 py-3 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Critical</th>
                      <th className="px-6 py-3 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">High</th>
                      <th className="px-6 py-3 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Fixes</th>
                      <th className="px-6 py-3 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    {completedScans.map(scan => (
                      <tr
                        key={scan.id}
                        onClick={() => router.push(`/scan/${scan.id}`)}
                        className="cursor-pointer table-row-hover"
                      >
                        <td className="px-6 py-3.5 font-medium text-zinc-200">{extractRepoName(scan.repoUrl)}</td>
                        <td className="px-6 py-3.5 text-zinc-400 font-mono">{scan.summary?.totalFindings ?? 0}</td>
                        <td className="px-6 py-3.5">
                          <span className="text-red-400 font-mono">{scan.summary?.criticalCount ?? 0}</span>
                        </td>
                        <td className="px-6 py-3.5">
                          <span className="text-orange-400 font-mono">{scan.summary?.highCount ?? 0}</span>
                        </td>
                        <td className="px-6 py-3.5 text-emerald-400 font-mono">{scan.summary?.fixesGenerated ?? 0}</td>
                        <td className="px-6 py-3.5 text-zinc-600 text-xs">
                          {new Date(scan.createdAt).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

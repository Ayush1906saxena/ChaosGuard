'use client';

import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'next/navigation';
import FindingsTable from '@/components/FindingsTable';
import SeverityBadge from '@/components/SeverityBadge';
import { getScan, getFindings } from '@/lib/api';
import type { Scan, Finding, Severity } from '@/lib/types';

export default function ReportPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [scanData, findingsData] = await Promise.all([
          getScan(scanId),
          getFindings(scanId, { size: 500 }),
        ]);
        setScan(scanData);
        setFindings(findingsData.content);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load report data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  const severityCounts = useMemo(() => {
    const counts: Record<Severity, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 };
    findings.forEach((f) => counts[f.severity]++);
    return counts;
  }, [findings]);

  const maxCount = Math.max(...Object.values(severityCounts), 1);

  const severityBarColors: Record<Severity, string> = {
    CRITICAL: 'bg-red-500',
    HIGH: 'bg-orange-500',
    MEDIUM: 'bg-yellow-500',
    LOW: 'bg-blue-500',
    INFO: 'bg-zinc-500',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-zinc-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading report...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Failed to load report</p>
          <p className="text-zinc-500 text-xs mb-4">{error}</p>
          <button onClick={() => window.location.reload()} className="px-4 py-2 text-xs bg-white/[0.04] border border-white/[0.06] text-zinc-400 rounded-lg hover:bg-white/[0.08] transition-colors">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Security Report</h1>
        <p className="text-sm text-zinc-500 mt-1">Comprehensive vulnerability analysis results</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 stagger-children">
        {([
          { severity: 'CRITICAL' as Severity, label: 'Critical', count: severityCounts.CRITICAL, textColor: 'text-red-400', glowClass: 'glow-red', borderColor: 'border-red-500/10' },
          { severity: 'HIGH' as Severity, label: 'High', count: severityCounts.HIGH, textColor: 'text-orange-400', glowClass: 'glow-orange', borderColor: 'border-orange-500/10' },
          { severity: 'MEDIUM' as Severity, label: 'Medium', count: severityCounts.MEDIUM, textColor: 'text-yellow-400', glowClass: '', borderColor: 'border-yellow-500/10' },
          { severity: 'LOW' as Severity, label: 'Low', count: severityCounts.LOW, textColor: 'text-blue-400', glowClass: '', borderColor: 'border-blue-500/10' },
          { severity: 'INFO' as Severity, label: 'Info', count: severityCounts.INFO, textColor: 'text-zinc-400', glowClass: '', borderColor: 'border-zinc-700/30' },
        ]).map((item) => (
          <div
            key={item.severity}
            className={`glass-card ${item.count > 0 ? item.glowClass : ''} ${item.borderColor} rounded-xl p-5 text-center`}
          >
            <p className={`text-3xl font-bold ${item.textColor} animate-count-up`}>{item.count}</p>
            <p className="text-[10px] text-zinc-600 mt-1.5 uppercase tracking-wider font-medium">{item.label}</p>
          </div>
        ))}
      </div>

      {/* Total Findings */}
      <div className="glass-card rounded-xl p-5 flex items-center justify-between">
        <div>
          <p className="text-sm text-zinc-500">Total Findings</p>
          <p className="text-4xl font-bold text-zinc-100 mt-1">{findings.length}</p>
        </div>
        {scan?.summary && (
          <div className="text-right">
            <p className="text-sm text-zinc-500">Agents Completed</p>
            <p className="text-2xl font-bold text-zinc-300 mt-1 font-mono">
              {scan.summary.agentsCompleted}/{scan.summary.totalAgents}
            </p>
          </div>
        )}
      </div>

      {/* Severity Distribution Chart */}
      <div className="glass-card rounded-2xl p-6">
        <h2 className="text-base font-semibold text-zinc-200 mb-6 flex items-center gap-2">
          <div className="w-1 h-4 rounded-full bg-gradient-to-b from-red-500 to-orange-500" />
          Severity Distribution
        </h2>
        <div className="space-y-3">
          {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as Severity[]).map((severity) => {
            const count = severityCounts[severity];
            const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
            return (
              <div key={severity} className="flex items-center gap-4">
                <div className="w-20">
                  <SeverityBadge severity={severity} size="sm" />
                </div>
                <div className="flex-1">
                  <div className="h-7 bg-white/[0.02] border border-white/[0.04] rounded-lg overflow-hidden relative">
                    <div
                      className={`h-full ${severityBarColors[severity]}/80 rounded-lg transition-all duration-1000 ease-out`}
                      style={{ width: `${percentage}%` }}
                    />
                    <span className="absolute inset-0 flex items-center px-3 text-xs font-mono text-zinc-200">
                      {count}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Category Distribution */}
      {findings.length > 0 && (
        <div className="glass-card rounded-2xl p-6">
          <h2 className="text-base font-semibold text-zinc-200 mb-4 flex items-center gap-2">
            <div className="w-1 h-4 rounded-full bg-gradient-to-b from-blue-500 to-purple-500" />
            Findings by Category
          </h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(
              findings.reduce<Record<string, number>>((acc, f) => {
                acc[f.category] = (acc[f.category] || 0) + 1;
                return acc;
              }, {})
            )
              .sort(([, a], [, b]) => b - a)
              .map(([category, count]) => (
                <div
                  key={category}
                  className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.03] border border-white/[0.06] rounded-lg hover:bg-white/[0.05] transition-colors"
                >
                  <span className="text-xs text-zinc-300">{category.replace(/_/g, ' ')}</span>
                  <span className="text-[10px] text-zinc-500 bg-white/[0.05] px-1.5 py-0.5 rounded-md font-mono">
                    {count}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Findings Table */}
      <div>
        <h2 className="text-base font-semibold text-zinc-200 mb-4 flex items-center gap-2">
          <div className="w-1 h-4 rounded-full bg-gradient-to-b from-purple-500 to-pink-500" />
          All Findings
        </h2>
        <FindingsTable findings={findings} showFilters />
      </div>
    </div>
  );
}

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

  useEffect(() => {
    async function load() {
      try {
        const [scanData, findingsData] = await Promise.all([
          getScan(scanId),
          getFindings(scanId, { size: 500 }),
        ]);
        setScan(scanData);
        setFindings(findingsData.content);
      } catch {
        // handle silently
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  const severityCounts = useMemo(() => {
    const counts: Record<Severity, number> = {
      CRITICAL: 0,
      HIGH: 0,
      MEDIUM: 0,
      LOW: 0,
      INFO: 0,
    };
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Security Report</h1>
        <p className="text-sm text-zinc-500 mt-1">Comprehensive vulnerability analysis results</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {([
          { severity: 'CRITICAL' as Severity, label: 'Critical', count: severityCounts.CRITICAL, textColor: 'text-red-400', borderColor: 'border-red-500/20' },
          { severity: 'HIGH' as Severity, label: 'High', count: severityCounts.HIGH, textColor: 'text-orange-400', borderColor: 'border-orange-500/20' },
          { severity: 'MEDIUM' as Severity, label: 'Medium', count: severityCounts.MEDIUM, textColor: 'text-yellow-400', borderColor: 'border-yellow-500/20' },
          { severity: 'LOW' as Severity, label: 'Low', count: severityCounts.LOW, textColor: 'text-blue-400', borderColor: 'border-blue-500/20' },
          { severity: 'INFO' as Severity, label: 'Info', count: severityCounts.INFO, textColor: 'text-zinc-400', borderColor: 'border-zinc-700' },
        ]).map((item) => (
          <div
            key={item.severity}
            className={`bg-zinc-900/50 border ${item.borderColor} rounded-xl p-5 text-center`}
          >
            <p className={`text-3xl font-bold ${item.textColor}`}>{item.count}</p>
            <p className="text-xs text-zinc-500 mt-1 uppercase tracking-wider">{item.label}</p>
          </div>
        ))}
      </div>

      {/* Total Findings */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 flex items-center justify-between">
        <div>
          <p className="text-sm text-zinc-400">Total Findings</p>
          <p className="text-4xl font-bold text-zinc-100 mt-1">{findings.length}</p>
        </div>
        {scan?.summary && (
          <div className="text-right">
            <p className="text-sm text-zinc-400">Agents Completed</p>
            <p className="text-2xl font-bold text-zinc-300 mt-1">
              {scan.summary.agentsCompleted}/{scan.summary.totalAgents}
            </p>
          </div>
        )}
      </div>

      {/* Severity Distribution Chart */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-zinc-200 mb-6">Severity Distribution</h2>
        <div className="space-y-4">
          {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as Severity[]).map((severity) => {
            const count = severityCounts[severity];
            const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
            return (
              <div key={severity} className="flex items-center gap-4">
                <div className="w-20">
                  <SeverityBadge severity={severity} size="sm" />
                </div>
                <div className="flex-1">
                  <div className="h-6 bg-zinc-800 rounded-lg overflow-hidden relative">
                    <div
                      className={`h-full ${severityBarColors[severity]} rounded-lg transition-all duration-700`}
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
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-zinc-200 mb-4">Findings by Category</h2>
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
                  className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 border border-zinc-700/50 rounded-lg"
                >
                  <span className="text-xs text-zinc-300">{category.replace(/_/g, ' ')}</span>
                  <span className="text-[10px] text-zinc-500 bg-zinc-700 px-1.5 py-0.5 rounded-full">
                    {count}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Findings Table */}
      <div>
        <h2 className="text-lg font-semibold text-zinc-200 mb-4">All Findings</h2>
        <FindingsTable findings={findings} showFilters />
      </div>
    </div>
  );
}

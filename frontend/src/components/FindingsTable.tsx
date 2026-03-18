'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import SeverityBadge from './SeverityBadge';
import TierBadge from './TierBadge';
import type { Finding, Severity, ScanTier } from '@/lib/types';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  FunnelIcon,
  XMarkIcon,
  HandThumbUpIcon,
  HandThumbDownIcon,
  MinusCircleIcon,
} from '@heroicons/react/24/outline';
import { submitFeedback } from '@/lib/api';
import type { FeedbackLabel } from '@/lib/types';

interface FindingsTableProps {
  findings: Finding[];
  onFindingClick?: (finding: Finding) => void;
  showFilters?: boolean;
}

type SortField = 'severity' | 'title' | 'category' | 'filePath' | 'confidence' | 'agentName';
type SortDir = 'asc' | 'desc';

const severityOrder: Record<Severity, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  INFO: 4,
};

export default function FindingsTable({
  findings,
  onFindingClick,
  showFilters = true,
}: FindingsTableProps) {
  const [sortField, setSortField] = useState<SortField>('severity');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [filterOpen, setFilterOpen] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<Severity[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
  const [tierFilter, setTierFilter] = useState<ScanTier[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [feedbackState, setFeedbackState] = useState<Record<string, FeedbackLabel | null>>({});
  const [feedbackLoading, setFeedbackLoading] = useState<Record<string, boolean>>({});
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const handleFeedback = async (findingId: string, label: FeedbackLabel) => {
    if (feedbackState[findingId] === label) {
      setFeedbackState((prev) => ({ ...prev, [findingId]: null }));
      return;
    }
    setFeedbackLoading((prev) => ({ ...prev, [findingId]: true }));
    setFeedbackError(null);
    try {
      await submitFeedback(findingId, label);
      setFeedbackState((prev) => ({ ...prev, [findingId]: label }));
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'Failed to submit feedback');
      setTimeout(() => setFeedbackError(null), 4000);
    } finally {
      setFeedbackLoading((prev) => ({ ...prev, [findingId]: false }));
    }
  };

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const filteredAndSorted = useMemo(() => {
    let result = [...findings];

    if (severityFilter.length > 0) {
      result = result.filter((f) => severityFilter.includes(f.severity));
    }
    if (categoryFilter.length > 0) {
      result = result.filter((f) => categoryFilter.includes(f.category));
    }
    if (tierFilter.length > 0) {
      result = result.filter((f) => tierFilter.includes(f.tier));
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (f) =>
          f.title.toLowerCase().includes(q) ||
          f.filePath.toLowerCase().includes(q) ||
          f.category.toLowerCase().includes(q)
      );
    }

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'severity':
          cmp = severityOrder[a.severity] - severityOrder[b.severity];
          break;
        case 'confidence':
          cmp = a.confidence - b.confidence;
          break;
        default:
          cmp = String(a[sortField]).localeCompare(String(b[sortField]));
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [findings, sortField, sortDir, severityFilter, categoryFilter, tierFilter, searchQuery]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ChevronUpIcon className="w-3 h-3 text-zinc-600" />;
    return sortDir === 'asc' ? (
      <ChevronUpIcon className="w-3 h-3 text-zinc-300" />
    ) : (
      <ChevronDownIcon className="w-3 h-3 text-zinc-300" />
    );
  };

  const allCategories = useMemo(
    () => [...new Set(findings.map((f) => f.category))],
    [findings]
  );

  const activeFilterCount =
    severityFilter.length + categoryFilter.length + tierFilter.length + (searchQuery ? 1 : 0);

  return (
    <div className="space-y-4">
      {showFilters && (
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              placeholder="Search findings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500/30 backdrop-blur-sm transition-all"
            />
          </div>
          <button
            onClick={() => setFilterOpen(!filterOpen)}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-all',
              filterOpen || activeFilterCount > 0
                ? 'border-blue-500/30 bg-blue-500/10 text-blue-400'
                : 'border-white/[0.06] bg-white/[0.03] text-zinc-400 hover:border-white/[0.1]'
            )}
          >
            <FunnelIcon className="w-4 h-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] bg-blue-500 text-white rounded-full">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>
      )}

      {filterOpen && (
        <div className="glass-card rounded-xl p-4 space-y-4 animate-slide-up">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-zinc-300">Filter Findings</h4>
            <button
              onClick={() => {
                setSeverityFilter([]);
                setCategoryFilter([]);
                setTierFilter([]);
                setSearchQuery('');
              }}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear all
            </button>
          </div>

          <div>
            <label className="text-xs font-medium text-zinc-400 mb-2 block">Severity</label>
            <div className="flex flex-wrap gap-2">
              {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as Severity[]).map((s) => (
                <button
                  key={s}
                  onClick={() =>
                    setSeverityFilter((prev) =>
                      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
                    )
                  }
                  className={cn('transition-opacity', severityFilter.includes(s) ? '' : 'opacity-40')}
                >
                  <SeverityBadge severity={s} size="sm" />
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-zinc-400 mb-2 block">Tier</label>
            <div className="flex flex-wrap gap-2">
              {(['RECON', 'HUNTER', 'SIEGE', 'LIVE'] as ScanTier[]).map((t) => (
                <button
                  key={t}
                  onClick={() =>
                    setTierFilter((prev) =>
                      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
                    )
                  }
                  className={cn('transition-opacity', tierFilter.includes(t) ? '' : 'opacity-40')}
                >
                  <TierBadge tier={t} size="sm" />
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-zinc-400 mb-2 block">Category</label>
            <div className="flex flex-wrap gap-1">
              {allCategories.map((c) => (
                <button
                  key={c}
                  onClick={() =>
                    setCategoryFilter((prev) =>
                      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
                    )
                  }
                  className={cn(
                    'px-2 py-0.5 text-[11px] rounded-lg border transition-colors',
                    categoryFilter.includes(c)
                      ? 'border-blue-500/30 bg-blue-500/10 text-blue-400'
                      : 'border-white/[0.06] bg-white/[0.03] text-zinc-500 hover:text-zinc-300'
                  )}
                >
                  {c.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Active filter pills */}
      {activeFilterCount > 0 && !filterOpen && (
        <div className="flex flex-wrap gap-2">
          {severityFilter.map((s) => (
            <button
              key={s}
              onClick={() => setSeverityFilter((prev) => prev.filter((x) => x !== s))}
              className="flex items-center gap-1 px-2 py-0.5 text-xs bg-white/[0.03] border border-white/[0.06] rounded-full text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              {s} <XMarkIcon className="w-3 h-3" />
            </button>
          ))}
          {tierFilter.map((t) => (
            <button
              key={t}
              onClick={() => setTierFilter((prev) => prev.filter((x) => x !== t))}
              className="flex items-center gap-1 px-2 py-0.5 text-xs bg-white/[0.03] border border-white/[0.06] rounded-full text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              {t} <XMarkIcon className="w-3 h-3" />
            </button>
          ))}
        </div>
      )}

      {feedbackError && (
        <div className="glass-card glow-red rounded-xl px-4 py-2.5 text-xs text-red-400 animate-scale-in">
          {feedbackError}
        </div>
      )}

      <div className="overflow-x-auto glass-card rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.04] bg-white/[0.02]">
              {[
                { field: 'severity' as SortField, label: 'Severity', width: 'w-28' },
                { field: 'title' as SortField, label: 'Title', width: '' },
                { field: 'category' as SortField, label: 'Category', width: 'w-40' },
                { field: 'filePath' as SortField, label: 'File', width: 'w-48' },
                { field: 'agentName' as SortField, label: 'Agent', width: 'w-32' },
                { field: 'confidence' as SortField, label: 'Confidence', width: 'w-24' },
                { field: 'confidence' as SortField, label: 'Feedback', width: 'w-28' },
              ].map(({ field, label, width }) => (
                <th
                  key={field}
                  className={cn(
                    'px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider cursor-pointer hover:text-zinc-200 select-none transition-colors',
                    width
                  )}
                  onClick={() => toggleSort(field)}
                >
                  <div className="flex items-center gap-1">
                    {label}
                    <SortIcon field={field} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.03]">
            {filteredAndSorted.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-zinc-500">
                  No findings match the current filters.
                </td>
              </tr>
            ) : (
              filteredAndSorted.map((finding) => (
                <tr
                  key={finding.id}
                  onClick={() => onFindingClick?.(finding)}
                  className={cn(
                    'table-row-hover transition-colors',
                    onFindingClick && 'cursor-pointer'
                  )}
                >
                  <td className="px-4 py-3">
                    <SeverityBadge severity={finding.severity} size="sm" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-zinc-200">{finding.title}</div>
                    <div className="text-xs text-zinc-500 mt-0.5 line-clamp-1">
                      {finding.description}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-zinc-400 bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 rounded-md">
                      {finding.category.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-zinc-400 font-mono truncate block max-w-[200px]">
                      {finding.filePath}
                    </span>
                    {finding.startLine > 0 && (
                      <span className="text-[10px] text-zinc-600">
                        L{finding.startLine}
                        {finding.endLine > finding.startLine && `-${finding.endLine}`}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <TierBadge tier={finding.tier} size="sm" />
                      <span className="text-xs text-zinc-500">{finding.agentName}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', {
                            'bg-green-500': finding.confidence >= 0.8,
                            'bg-yellow-500': finding.confidence >= 0.5 && finding.confidence < 0.8,
                            'bg-red-500': finding.confidence < 0.5,
                          })}
                          style={{ width: `${finding.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-zinc-500">
                        {Math.round(finding.confidence * 100)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleFeedback(finding.id, 'TRUE_POSITIVE')}
                        disabled={feedbackLoading[finding.id]}
                        className={cn(
                          'p-1 rounded-md transition-colors',
                          feedbackState[finding.id] === 'TRUE_POSITIVE'
                            ? 'bg-green-500/20 text-green-400'
                            : 'text-zinc-600 hover:text-green-400 hover:bg-green-500/10'
                        )}
                        title="True Positive"
                      >
                        <HandThumbUpIcon className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleFeedback(finding.id, 'FALSE_POSITIVE')}
                        disabled={feedbackLoading[finding.id]}
                        className={cn(
                          'p-1 rounded-md transition-colors',
                          feedbackState[finding.id] === 'FALSE_POSITIVE'
                            ? 'bg-red-500/20 text-red-400'
                            : 'text-zinc-600 hover:text-red-400 hover:bg-red-500/10'
                        )}
                        title="False Positive"
                      >
                        <HandThumbDownIcon className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleFeedback(finding.id, 'WONT_FIX')}
                        disabled={feedbackLoading[finding.id]}
                        className={cn(
                          'p-1 rounded-md transition-colors',
                          feedbackState[finding.id] === 'WONT_FIX'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'text-zinc-600 hover:text-yellow-400 hover:bg-yellow-500/10'
                        )}
                        title="Won't Fix"
                      >
                        <MinusCircleIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-zinc-500 text-right">
        Showing {filteredAndSorted.length} of {findings.length} findings
      </div>
    </div>
  );
}

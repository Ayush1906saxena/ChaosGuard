'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getFixes, createIssue, createPullRequest, createSinglePullRequest } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import DiffViewer from '@/components/DiffViewer';
import { cn } from '@/lib/utils';
import type { Fix } from '@/lib/types';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  ArrowUpTrayIcon,
  ExclamationTriangleIcon,
  BeakerIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

export default function FixesPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [fixes, setFixes] = useState<Fix[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedFixes, setSelectedFixes] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getFixes(scanId);
        setFixes(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load fixes');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  const handleCreateIssue = async (fixId: string) => {
    setActionLoading(fixId);
    setActionResult(null);
    try {
      const result = await createIssue(scanId, fixId);
      setActionResult({ type: 'success', message: `Issue created: ${result.issueUrl}` });
    } catch (err) {
      setActionResult({ type: 'error', message: err instanceof Error ? err.message : 'Failed to create issue' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreatePR = async () => {
    if (selectedFixes.size === 0) return;
    setActionLoading('pr');
    setActionResult(null);
    try {
      const result = await createPullRequest(scanId, Array.from(selectedFixes));
      setActionResult({ type: 'success', message: `Pull request created: ${result.prUrl}` });
    } catch (err) {
      setActionResult({ type: 'error', message: err instanceof Error ? err.message : 'Failed to create PR' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateSinglePR = async (fixId: string) => {
    setActionLoading(`pr-${fixId}`);
    setActionResult(null);
    try {
      const result = await createSinglePullRequest(scanId, fixId);
      setActionResult({ type: 'success', message: `Pull request created: ${result.prUrl}` });
    } catch (err) {
      setActionResult({ type: 'error', message: err instanceof Error ? err.message : 'Failed to create PR' });
    } finally {
      setActionLoading(null);
    }
  };

  const toggleFixSelection = (fixId: string) => {
    setSelectedFixes((prev) => {
      const next = new Set(prev);
      if (next.has(fixId)) next.delete(fixId);
      else next.add(fixId);
      return next;
    });
  };

  const confidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400 bg-green-500/10 border-green-500/20';
    if (confidence >= 0.5) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20';
    return 'text-red-400 bg-red-500/10 border-red-500/20';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-zinc-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading fixes...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Failed to load fixes</p>
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Fix Review</h1>
          <p className="text-sm text-zinc-500 mt-1">
            AI-generated security fixes with diff preview
          </p>
        </div>
        {selectedFixes.size > 0 && (
          <button
            onClick={handleCreatePR}
            disabled={actionLoading === 'pr'}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white rounded-xl text-sm font-semibold hover:from-emerald-500 hover:to-green-500 transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50"
          >
            {actionLoading === 'pr' ? (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <ArrowUpTrayIcon className="w-4 h-4" />
            )}
            Create PR ({selectedFixes.size} fix{selectedFixes.size > 1 ? 'es' : ''})
          </button>
        )}
      </div>

      {/* Action result */}
      {actionResult && (
        <div
          className={cn(
            'glass-card rounded-xl px-4 py-3 text-sm',
            actionResult.type === 'success'
              ? 'glow-green border-emerald-500/20 text-emerald-400'
              : 'glow-red border-red-500/20 text-red-400'
          )}
        >
          {actionResult.type === 'success' && actionResult.message.includes('http') ? (
            (() => {
              const urlMatch = actionResult.message.match(/https?:\/\/\S+/);
              const url = urlMatch ? urlMatch[0] : '';
              const prefix = actionResult.message.replace(url, '').trim();
              return (
                <>
                  {prefix}{' '}
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-emerald-300 transition-colors"
                  >
                    {url}
                  </a>
                </>
              );
            })()
          ) : (
            actionResult.message
          )}
        </div>
      )}

      {fixes.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No fixes generated for this scan.</p>
        </div>
      ) : (
        <div className="space-y-4 stagger-children">
          {fixes.map((fix) => {
            const isExpanded = expandedId === fix.id;
            return (
              <div
                key={fix.id}
                className="glass-card glass-card-hover rounded-2xl overflow-hidden"
              >
                {/* Fix Header */}
                <div className="flex items-start p-6">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleFixSelection(fix.id)}
                    className={cn(
                      'w-5 h-5 rounded-md border flex-shrink-0 mr-4 mt-0.5 flex items-center justify-center transition-all',
                      selectedFixes.has(fix.id)
                        ? 'bg-emerald-500 border-emerald-500 text-white shadow-lg shadow-emerald-500/30'
                        : 'border-white/[0.1] hover:border-white/[0.2] bg-white/[0.02]'
                    )}
                  >
                    {selectedFixes.has(fix.id) && (
                      <CheckIcon className="w-3 h-3" strokeWidth={3} />
                    )}
                  </button>

                  <button
                    onClick={() => setExpandedId(isExpanded ? null : fix.id)}
                    className="flex-1 text-left"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className={cn(
                        'px-2.5 py-0.5 text-[10px] rounded-lg border font-semibold',
                        confidenceColor(fix.confidence)
                      )}>
                        {Math.round(fix.confidence * 100)}% confidence
                      </span>
                      {fix.breakingChange && (
                        <span className="flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-lg bg-red-500/10 text-red-400 border border-red-500/20">
                          <ExclamationTriangleIcon className="w-3 h-3" />
                          Breaking Change
                        </span>
                      )}
                      {fix.testRequired && (
                        <span className="flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <BeakerIcon className="w-3 h-3" />
                          Test Required
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-semibold text-zinc-100 mb-1">{fix.title}</h3>
                    <p className="text-sm text-zinc-400">{fix.description}</p>
                    <p className="text-xs font-mono text-zinc-600 mt-2">
                      {fix.filePath}:{fix.startLine}-{fix.endLine}
                    </p>
                  </button>

                  <div className="ml-4 flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleCreateIssue(fix.id)}
                      disabled={actionLoading === fix.id}
                      className="px-3 py-1.5 text-xs bg-white/[0.03] border border-white/[0.06] text-zinc-300 rounded-lg hover:bg-white/[0.06] transition-colors disabled:opacity-50"
                    >
                      {actionLoading === fix.id ? 'Creating...' : 'Create Issue'}
                    </button>
                    <button
                      onClick={() => handleCreateSinglePR(fix.id)}
                      disabled={actionLoading === `pr-${fix.id}`}
                      className="px-3 py-1.5 text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === `pr-${fix.id}` ? 'Creating...' : 'Create PR'}
                    </button>
                    {isExpanded ? (
                      <ChevronUpIcon className="w-5 h-5 text-zinc-500" />
                    ) : (
                      <ChevronDownIcon className="w-5 h-5 text-zinc-500" />
                    )}
                  </div>
                </div>

                {/* Expanded */}
                {isExpanded && (
                  <div className="border-t border-white/[0.04] p-6 space-y-6 animate-slide-up">
                    {/* Diff */}
                    <DiffViewer
                      originalCode={fix.originalCode}
                      fixedCode={fix.fixedCode}
                      filePath={fix.filePath}
                      startLine={fix.startLine}
                    />

                    {/* PoC Steps */}
                    {fix.pocSteps.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
                          <div className="w-1 h-4 rounded-full bg-gradient-to-b from-amber-500 to-orange-500" />
                          Proof of Concept Steps
                        </h4>
                        <ol className="space-y-2 list-decimal list-inside">
                          {fix.pocSteps.map((step, idx) => (
                            <li key={idx} className="text-sm text-zinc-400">
                              {step}
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

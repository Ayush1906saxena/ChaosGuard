'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getFixes, createIssue, createPullRequest } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import DiffViewer from '@/components/DiffViewer';
import { cn } from '@/lib/utils';
import type { Fix } from '@/lib/types';

export default function FixesPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [fixes, setFixes] = useState<Fix[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedFixes, setSelectedFixes] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getFixes(scanId);
        setFixes(data);
      } catch {
        // handle silently
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

  const toggleFixSelection = (fixId: string) => {
    setSelectedFixes((prev) => {
      const next = new Set(prev);
      if (next.has(fixId)) next.delete(fixId);
      else next.add(fixId);
      return next;
    });
  };

  const confidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400 bg-green-500/15 border-green-500/30';
    if (confidence >= 0.5) return 'text-yellow-400 bg-yellow-500/15 border-yellow-500/30';
    return 'text-red-400 bg-red-500/15 border-red-500/30';
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

  return (
    <div className="space-y-8">
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
            className="flex items-center gap-2 px-4 py-2 bg-green-500/15 border border-green-500/30 text-green-400 rounded-lg text-sm font-medium hover:bg-green-500/25 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'pr' ? (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            )}
            Create PR ({selectedFixes.size} fix{selectedFixes.size > 1 ? 'es' : ''})
          </button>
        )}
      </div>

      {/* Action result */}
      {actionResult && (
        <div
          className={cn(
            'rounded-xl px-4 py-3 text-sm',
            actionResult.type === 'success'
              ? 'bg-green-500/10 border border-green-500/30 text-green-400'
              : 'bg-red-500/10 border border-red-500/30 text-red-400'
          )}
        >
          {actionResult.message}
        </div>
      )}

      {fixes.length === 0 ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No fixes generated for this scan.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {fixes.map((fix) => {
            const isExpanded = expandedId === fix.id;
            return (
              <div
                key={fix.id}
                className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden"
              >
                {/* Fix Header */}
                <div className="flex items-start p-6">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleFixSelection(fix.id)}
                    className={cn(
                      'w-5 h-5 rounded border flex-shrink-0 mr-4 mt-0.5 flex items-center justify-center transition-colors',
                      selectedFixes.has(fix.id)
                        ? 'bg-green-500 border-green-500 text-white'
                        : 'border-zinc-600 hover:border-zinc-400'
                    )}
                  >
                    {selectedFixes.has(fix.id) && (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>

                  <button
                    onClick={() => setExpandedId(isExpanded ? null : fix.id)}
                    className="flex-1 text-left"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className={cn(
                        'px-2 py-0.5 text-[10px] rounded-full border font-semibold',
                        confidenceColor(fix.confidence)
                      )}>
                        {Math.round(fix.confidence * 100)}% confidence
                      </span>
                      {fix.breakingChange && (
                        <span className="px-2 py-0.5 text-[10px] rounded-full bg-red-500/15 text-red-400 border border-red-500/30">
                          Breaking Change
                        </span>
                      )}
                      {fix.testRequired && (
                        <span className="px-2 py-0.5 text-[10px] rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
                          Test Required
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-semibold text-zinc-100 mb-1">{fix.title}</h3>
                    <p className="text-sm text-zinc-400">{fix.description}</p>
                    <p className="text-xs font-mono text-zinc-500 mt-2">
                      {fix.filePath}:{fix.startLine}-{fix.endLine}
                    </p>
                  </button>

                  <div className="ml-4 flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleCreateIssue(fix.id)}
                      disabled={actionLoading === fix.id}
                      className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === fix.id ? 'Creating...' : 'Create Issue'}
                    </button>
                    <span className="text-zinc-500 text-xl">
                      {isExpanded ? '\u25B2' : '\u25BC'}
                    </span>
                  </div>
                </div>

                {/* Expanded */}
                {isExpanded && (
                  <div className="border-t border-zinc-800 p-6 space-y-6">
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
                        <h4 className="text-sm font-semibold text-zinc-300 mb-3">Proof of Concept Steps</h4>
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

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { getScan, getPlaybooks } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { Scan, PentestPlaybook } from '@/lib/types';
import {
  LockClosedIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback - handle silently
    }
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 px-2 py-1 text-[10px] bg-white/[0.04] border border-white/[0.06] rounded-md text-zinc-300 hover:bg-white/[0.08] transition-colors"
    >
      {copied ? (
        <>
          <CheckIcon className="w-3 h-3 text-green-400" />
          Copied!
        </>
      ) : (
        <>
          <ClipboardDocumentIcon className="w-3 h-3" />
          Copy
        </>
      )}
    </button>
  );
}

export default function PlaybookPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [playbooks, setPlaybooks] = useState<PentestPlaybook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlaybook, setSelectedPlaybook] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const scanData = await getScan(scanId);
        setScan(scanData);
        if (scanData.tier === 'SIEGE') {
          const data = await getPlaybooks(scanId);
          setPlaybooks(data);
          if (data.length > 0) setSelectedPlaybook(data[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load playbooks');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-zinc-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Failed to load playbooks</p>
          <p className="text-zinc-500 text-xs mb-4">{error}</p>
          <button onClick={() => window.location.reload()} className="px-4 py-2 text-xs bg-white/[0.04] border border-white/[0.06] text-zinc-400 rounded-lg hover:bg-white/[0.08] transition-colors">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (scan && scan.tier !== 'SIEGE') {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
            <LockClosedIcon className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="text-xl font-bold text-zinc-200 mb-2">Siege Tier Only</h2>
          <p className="text-sm text-zinc-500">
            Pentest playbooks are available exclusively with the Siege tier.
            Upgrade your scan to access detailed penetration testing guides with
            cURL commands and OWASP/MITRE references.
          </p>
        </div>
      </div>
    );
  }

  const activePlaybook = playbooks.find((p) => p.id === selectedPlaybook);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Pentest Playbook</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Step-by-step penetration testing guide with executable test cases
        </p>
      </div>

      {playbooks.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No playbooks generated for this scan.</p>
        </div>
      ) : (
        <>
          {/* Playbook selector */}
          {playbooks.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-2">
              {playbooks.map((pb) => (
                <button
                  key={pb.id}
                  onClick={() => setSelectedPlaybook(pb.id)}
                  className={cn(
                    'px-4 py-2 text-sm rounded-xl border whitespace-nowrap transition-all',
                    selectedPlaybook === pb.id
                      ? 'bg-white/[0.06] border-white/[0.1] text-zinc-200 shadow-lg'
                      : 'border-white/[0.04] text-zinc-500 hover:text-zinc-300 hover:border-white/[0.08]'
                  )}
                >
                  {pb.title}
                </button>
              ))}
            </div>
          )}

          {activePlaybook && (
            <div className="space-y-6 stagger-children">
              {/* Playbook Metadata */}
              <div className="glass-card rounded-2xl p-6">
                <h2 className="text-lg font-semibold text-zinc-100 mb-2">{activePlaybook.title}</h2>
                <p className="text-sm text-zinc-400 mb-4">{activePlaybook.description}</p>

                <div className="flex flex-wrap gap-4">
                  {/* OWASP References */}
                  {activePlaybook.owaspReferences.length > 0 && (
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">OWASP</p>
                      <div className="flex flex-wrap gap-1">
                        {activePlaybook.owaspReferences.map((ref) => (
                          <span
                            key={ref}
                            className="px-2 py-0.5 text-[10px] bg-orange-500/10 border border-orange-500/20 text-orange-400 rounded-lg"
                          >
                            {ref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* MITRE References */}
                  {activePlaybook.mitreReferences.length > 0 && (
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">MITRE ATT&CK</p>
                      <div className="flex flex-wrap gap-1">
                        {activePlaybook.mitreReferences.map((ref) => (
                          <a
                            key={ref.techniqueId}
                            href={ref.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-2 py-0.5 text-[10px] bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/15 transition-colors"
                          >
                            {ref.techniqueId} - {ref.name}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Test Cases */}
              <div>
                <h3 className="text-sm font-semibold text-zinc-300 mb-4 flex items-center gap-2">
                  <div className="w-1 h-4 rounded-full bg-gradient-to-b from-purple-500 to-pink-500" />
                  Test Cases ({activePlaybook.testCases.length})
                </h3>
                <div className="space-y-4">
                  {activePlaybook.testCases
                    .sort((a, b) => a.order - b.order)
                    .map((tc) => (
                      <div
                        key={tc.order}
                        className={cn(
                          'glass-card rounded-2xl overflow-hidden',
                          tc.passed ? 'border-green-500/15' : 'border-red-500/15'
                        )}
                      >
                        {/* Test case header */}
                        <div className="p-5">
                          <div className="flex items-center gap-3 mb-3">
                            <span className="w-7 h-7 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-xs font-bold text-zinc-300">
                              {tc.order}
                            </span>
                            <SeverityBadge severity={tc.severity} size="sm" />
                            <span className={cn(
                              'flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-lg font-semibold uppercase tracking-wider border',
                              tc.passed
                                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                                : 'bg-red-500/10 text-red-400 border-red-500/20'
                            )}>
                              {tc.passed ? (
                                <><CheckCircleIcon className="w-3 h-3" /> Passed</>
                              ) : (
                                <><XCircleIcon className="w-3 h-3" /> Failed</>
                              )}
                            </span>
                          </div>

                          <h4 className="text-base font-semibold text-zinc-100 mb-2">{tc.title}</h4>
                          <p className="text-sm text-zinc-400">{tc.description}</p>

                          {/* Expected vs Actual */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                            <div className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-3">
                              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Expected Behavior</p>
                              <p className="text-sm text-zinc-300">{tc.expectedBehavior}</p>
                            </div>
                            <div className={cn(
                              'rounded-xl p-3 border',
                              tc.passed ? 'bg-green-500/[0.03] border-green-500/10' : 'bg-red-500/[0.03] border-red-500/10'
                            )}>
                              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Actual Behavior</p>
                              <p className="text-sm text-zinc-300">{tc.actualBehavior}</p>
                            </div>
                          </div>
                        </div>

                        {/* cURL command */}
                        {tc.curlCommand && (
                          <div className="border-t border-white/[0.04] bg-white/[0.01] p-4">
                            <div className="flex items-center justify-between mb-2">
                              <p className="text-[10px] text-zinc-500 uppercase tracking-wider">cURL Command</p>
                              <CopyButton text={tc.curlCommand} />
                            </div>
                            <pre className="text-xs font-mono text-zinc-300 bg-black/30 border border-white/[0.04] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all">
                              {tc.curlCommand}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>

              {/* Summary stats */}
              <div className="glass-card rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-zinc-300 mb-4 flex items-center gap-2">
                  <div className="w-1 h-4 rounded-full bg-gradient-to-b from-blue-500 to-purple-500" />
                  Test Summary
                </h3>
                <div className="grid grid-cols-3 gap-4 stagger-children">
                  <div className="text-center bg-white/[0.02] border border-white/[0.04] rounded-xl p-4">
                    <p className="text-2xl font-bold text-zinc-200 animate-count-up">{activePlaybook.testCases.length}</p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Total Tests</p>
                  </div>
                  <div className="text-center bg-white/[0.02] border border-white/[0.04] rounded-xl p-4">
                    <p className="text-2xl font-bold text-green-400 animate-count-up">
                      {activePlaybook.testCases.filter((t) => t.passed).length}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Passed</p>
                  </div>
                  <div className="text-center bg-white/[0.02] border border-white/[0.04] rounded-xl p-4">
                    <p className="text-2xl font-bold text-red-400 animate-count-up">
                      {activePlaybook.testCases.filter((t) => !t.passed).length}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Failed</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

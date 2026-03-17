'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { getScan, getPlaybooks } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { Scan, PentestPlaybook } from '@/lib/types';

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
      className="px-2 py-1 text-[10px] bg-zinc-700 border border-zinc-600 rounded text-zinc-300 hover:bg-zinc-600 transition-colors"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

export default function PlaybookPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [playbooks, setPlaybooks] = useState<PentestPlaybook[]>([]);
  const [loading, setLoading] = useState(true);
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
      } catch {
        // handle silently
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

  if (scan && scan.tier !== 'SIEGE') {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Pentest Playbook</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Step-by-step penetration testing guide with executable test cases
        </p>
      </div>

      {playbooks.length === 0 ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
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
                    'px-4 py-2 text-sm rounded-lg border whitespace-nowrap transition-colors',
                    selectedPlaybook === pb.id
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-200'
                      : 'border-zinc-700/50 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600'
                  )}
                >
                  {pb.title}
                </button>
              ))}
            </div>
          )}

          {activePlaybook && (
            <div className="space-y-6">
              {/* Playbook Metadata */}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
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
                            className="px-2 py-0.5 text-[10px] bg-orange-500/10 border border-orange-500/20 text-orange-400 rounded"
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
                            className="px-2 py-0.5 text-[10px] bg-red-500/10 border border-red-500/20 text-red-400 rounded hover:bg-red-500/20 transition-colors"
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
                <h3 className="text-sm font-semibold text-zinc-300 mb-4">
                  Test Cases ({activePlaybook.testCases.length})
                </h3>
                <div className="space-y-4">
                  {activePlaybook.testCases
                    .sort((a, b) => a.order - b.order)
                    .map((tc) => (
                      <div
                        key={tc.order}
                        className={cn(
                          'bg-zinc-900/50 border rounded-2xl overflow-hidden',
                          tc.passed ? 'border-green-500/20' : 'border-red-500/20'
                        )}
                      >
                        {/* Test case header */}
                        <div className="p-5">
                          <div className="flex items-center gap-3 mb-3">
                            <span className="w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-bold text-zinc-300">
                              {tc.order}
                            </span>
                            <SeverityBadge severity={tc.severity} size="sm" />
                            <span className={cn(
                              'px-2 py-0.5 text-[10px] rounded-full font-semibold uppercase tracking-wider',
                              tc.passed
                                ? 'bg-green-500/15 text-green-400'
                                : 'bg-red-500/15 text-red-400'
                            )}>
                              {tc.passed ? 'Passed' : 'Failed'}
                            </span>
                          </div>

                          <h4 className="text-base font-semibold text-zinc-100 mb-2">{tc.title}</h4>
                          <p className="text-sm text-zinc-400">{tc.description}</p>

                          {/* Expected vs Actual */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                            <div className="bg-zinc-800/50 rounded-lg p-3">
                              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Expected Behavior</p>
                              <p className="text-sm text-zinc-300">{tc.expectedBehavior}</p>
                            </div>
                            <div className={cn(
                              'rounded-lg p-3',
                              tc.passed ? 'bg-green-500/5' : 'bg-red-500/5'
                            )}>
                              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Actual Behavior</p>
                              <p className="text-sm text-zinc-300">{tc.actualBehavior}</p>
                            </div>
                          </div>
                        </div>

                        {/* cURL command */}
                        {tc.curlCommand && (
                          <div className="border-t border-zinc-800 bg-zinc-800/30 p-4">
                            <div className="flex items-center justify-between mb-2">
                              <p className="text-[10px] text-zinc-500 uppercase tracking-wider">cURL Command</p>
                              <CopyButton text={tc.curlCommand} />
                            </div>
                            <pre className="text-xs font-mono text-zinc-300 bg-zinc-900 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all">
                              {tc.curlCommand}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>

              {/* Summary stats */}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-zinc-300 mb-4">Test Summary</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-zinc-200">{activePlaybook.testCases.length}</p>
                    <p className="text-[10px] text-zinc-500 uppercase">Total Tests</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-400">
                      {activePlaybook.testCases.filter((t) => t.passed).length}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase">Passed</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-red-400">
                      {activePlaybook.testCases.filter((t) => !t.passed).length}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase">Failed</p>
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

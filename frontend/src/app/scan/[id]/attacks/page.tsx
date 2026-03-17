'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getScan, getAttackChains } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { Scan, AttackChain } from '@/lib/types';

export default function AttacksPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [chains, setChains] = useState<AttackChain[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedChains, setExpandedChains] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function load() {
      try {
        const scanData = await getScan(scanId);
        setScan(scanData);
        if (scanData.tier === 'SIEGE') {
          const chainsData = await getAttackChains(scanId);
          setChains(chainsData);
        }
      } catch {
        // handle silently
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  const toggleChain = (id: string) => {
    setExpandedChains((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

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
            Attack chain analysis is available exclusively with the Siege tier.
            Upgrade your scan to access full offensive security assessment with
            multi-step attack chains and MITRE ATT&CK mapping.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Attack Chains</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Multi-step attack paths discovered through offensive analysis
        </p>
      </div>

      {chains.length === 0 ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No attack chains discovered for this scan.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {chains.map((chain) => {
            const isExpanded = expandedChains.has(chain.id);
            return (
              <div
                key={chain.id}
                className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden"
              >
                {/* Chain Header */}
                <button
                  onClick={() => toggleChain(chain.id)}
                  className="w-full flex items-start justify-between p-6 text-left hover:bg-zinc-800/30 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <SeverityBadge severity={chain.overallSeverity} />
                      <span className={cn(
                        'px-2 py-0.5 text-[10px] rounded-full font-medium uppercase tracking-wider',
                        chain.likelihood === 'HIGH' ? 'bg-red-500/15 text-red-400' :
                        chain.likelihood === 'MEDIUM' ? 'bg-yellow-500/15 text-yellow-400' :
                        'bg-blue-500/15 text-blue-400'
                      )}>
                        {chain.likelihood} likelihood
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-100 mb-1">{chain.title}</h3>
                    <p className="text-sm text-zinc-400 line-clamp-2">{chain.description}</p>
                  </div>
                  <div className="ml-4 text-zinc-500 text-xl flex-shrink-0">
                    {isExpanded ? '\u25B2' : '\u25BC'}
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="border-t border-zinc-800 p-6 space-y-6">
                    {/* Impact */}
                    <div className="bg-red-500/5 border border-red-500/10 rounded-xl p-4">
                      <h4 className="text-sm font-semibold text-red-400 mb-1">Impact</h4>
                      <p className="text-sm text-zinc-300">{chain.impactDescription}</p>
                    </div>

                    {/* Steps */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-300 mb-4">Attack Steps</h4>
                      <div className="relative">
                        {/* Vertical line */}
                        <div className="absolute left-5 top-0 bottom-0 w-px bg-zinc-700" />

                        <div className="space-y-4">
                          {chain.steps.map((step) => (
                            <div key={step.order} className="relative flex gap-4 pl-2">
                              {/* Step number circle */}
                              <div className="relative z-10 flex-shrink-0 w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                                <span className="text-xs font-bold text-zinc-300">{step.order}</span>
                              </div>

                              <div className="flex-1 bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
                                <div className="flex items-center gap-2 mb-2">
                                  <SeverityBadge severity={step.severity} size="sm" />
                                  <span className="text-xs text-zinc-500 font-mono bg-zinc-700/50 px-2 py-0.5 rounded">
                                    {step.technique}
                                  </span>
                                </div>
                                <h5 className="text-sm font-semibold text-zinc-200 mb-1">{step.title}</h5>
                                <p className="text-xs text-zinc-400">{step.description}</p>

                                {step.filePath && (
                                  <p className="text-[10px] text-zinc-600 font-mono mt-2">
                                    {step.filePath}
                                  </p>
                                )}

                                {step.codeSnippet && (
                                  <pre className="mt-2 p-2 bg-zinc-900 rounded-lg text-[11px] text-zinc-400 font-mono overflow-x-auto">
                                    {step.codeSnippet}
                                  </pre>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* MITRE References */}
                    {chain.mitreAttackTechniques.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-zinc-300 mb-3">MITRE ATT&CK References</h4>
                        <div className="flex flex-wrap gap-2">
                          {chain.mitreAttackTechniques.map((ref) => (
                            <a
                              key={ref.techniqueId}
                              href={ref.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 border border-zinc-700/50 rounded-lg hover:border-zinc-600 transition-colors"
                            >
                              <span className="text-xs font-mono text-red-400">{ref.techniqueId}</span>
                              <span className="text-xs text-zinc-400">{ref.name}</span>
                              <span className="text-[10px] text-zinc-600">{ref.tacticName}</span>
                            </a>
                          ))}
                        </div>
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

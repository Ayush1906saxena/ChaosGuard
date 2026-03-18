'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getScan, getAttackChains } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { Scan, AttackChain } from '@/lib/types';
import {
  LockClosedIcon,
  ChevronUpIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';

export default function AttacksPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [chains, setChains] = useState<AttackChain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load attack chains');
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

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Failed to load attack chains</p>
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
            Attack chain analysis is available exclusively with the Siege tier.
            Upgrade your scan to access full offensive security assessment with
            multi-step attack chains and MITRE ATT&CK mapping.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Attack Chains</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Multi-step attack paths discovered through offensive analysis
        </p>
      </div>

      {chains.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No attack chains discovered for this scan.</p>
        </div>
      ) : (
        <div className="space-y-4 stagger-children">
          {chains.map((chain) => {
            const isExpanded = expandedChains.has(chain.id);
            return (
              <div
                key={chain.id}
                className="glass-card glass-card-hover rounded-2xl overflow-hidden"
              >
                {/* Chain Header */}
                <button
                  onClick={() => toggleChain(chain.id)}
                  className="w-full flex items-start justify-between p-6 text-left hover:bg-white/[0.01] transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <SeverityBadge severity={chain.overallSeverity} />
                      <span className={cn(
                        'px-2.5 py-0.5 text-[10px] rounded-lg font-medium uppercase tracking-wider border',
                        chain.likelihood === 'HIGH' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                        chain.likelihood === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                        'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      )}>
                        {chain.likelihood} likelihood
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-100 mb-1">{chain.title}</h3>
                    <p className="text-sm text-zinc-400 line-clamp-2">{chain.description}</p>
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    {isExpanded ? (
                      <ChevronUpIcon className="w-5 h-5 text-zinc-500" />
                    ) : (
                      <ChevronDownIcon className="w-5 h-5 text-zinc-500" />
                    )}
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="border-t border-white/[0.04] p-6 space-y-6 animate-slide-up">
                    {/* Impact */}
                    <div className="bg-red-500/[0.03] border border-red-500/10 rounded-xl p-4">
                      <h4 className="text-sm font-semibold text-red-400 mb-1 flex items-center gap-2">
                        <div className="w-1 h-4 rounded-full bg-gradient-to-b from-red-500 to-red-600" />
                        Impact
                      </h4>
                      <p className="text-sm text-zinc-300">{chain.impactDescription}</p>
                    </div>

                    {/* Steps */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-300 mb-4 flex items-center gap-2">
                        <div className="w-1 h-4 rounded-full bg-gradient-to-b from-orange-500 to-red-500" />
                        Attack Steps
                      </h4>
                      <div className="relative">
                        {/* Vertical line */}
                        <div className="absolute left-5 top-0 bottom-0 w-px bg-gradient-to-b from-red-500/30 via-orange-500/20 to-transparent" />

                        <div className="space-y-4">
                          {chain.steps.map((step) => (
                            <div key={step.order} className="relative flex gap-4 pl-2">
                              {/* Step number circle */}
                              <div className="relative z-10 flex-shrink-0 w-8 h-8 rounded-full bg-white/[0.03] border border-white/[0.08] flex items-center justify-center backdrop-blur-sm">
                                <span className="text-xs font-bold text-zinc-300">{step.order}</span>
                              </div>

                              <div className="flex-1 bg-white/[0.02] border border-white/[0.04] rounded-xl p-4 hover:bg-white/[0.03] transition-colors">
                                <div className="flex items-center gap-2 mb-2">
                                  <SeverityBadge severity={step.severity} size="sm" />
                                  <span className="text-xs text-zinc-500 font-mono bg-white/[0.04] px-2 py-0.5 rounded-md">
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
                                  <pre className="mt-2 p-3 bg-black/30 border border-white/[0.04] rounded-lg text-[11px] text-zinc-400 font-mono overflow-x-auto">
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
                        <h4 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
                          <div className="w-1 h-4 rounded-full bg-gradient-to-b from-purple-500 to-pink-500" />
                          MITRE ATT&CK References
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {chain.mitreAttackTechniques.map((ref) => (
                            <a
                              key={ref.techniqueId}
                              href={ref.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.03] border border-white/[0.06] rounded-lg hover:bg-white/[0.06] hover:border-white/[0.1] transition-colors"
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

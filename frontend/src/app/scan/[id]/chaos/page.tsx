'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getChaosScenarios } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { ChaosScenario, Severity } from '@/lib/types';

const impactColors: Record<Severity, string> = {
  CRITICAL: 'bg-red-500',
  HIGH: 'bg-orange-500',
  MEDIUM: 'bg-yellow-500',
  LOW: 'bg-blue-500',
  INFO: 'bg-zinc-500',
};

export default function ChaosPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scenarios, setScenarios] = useState<ChaosScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getChaosScenarios(scanId);
        setScenarios(data);
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
          Loading chaos scenarios...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Chaos Scenarios</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Failure injection scenarios and blast radius analysis
        </p>
      </div>

      {scenarios.length === 0 ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No chaos scenarios generated for this scan.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {scenarios.map((scenario) => {
            const isExpanded = expandedId === scenario.id;
            // Calculate blast radius percentage
            const blastPercentage = scenario.blastRadius.length > 0
              ? Math.min(100, Math.round(
                  (scenario.blastRadius.filter(
                    (n) => n.impact === 'CRITICAL' || n.impact === 'HIGH'
                  ).length / scenario.blastRadius.length) * 100
                ))
              : 0;

            return (
              <div
                key={scenario.id}
                className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden"
              >
                {/* Header */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : scenario.id)}
                  className="w-full flex items-start justify-between p-6 text-left hover:bg-zinc-800/30 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <SeverityBadge severity={scenario.severity} />
                      <span className="px-2 py-0.5 text-[10px] rounded-full bg-zinc-700/50 text-zinc-400 uppercase tracking-wider">
                        {scenario.scenarioType.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-100 mb-1">{scenario.title}</h3>
                    <p className="text-sm text-zinc-400 line-clamp-2">{scenario.description}</p>

                    {/* Quick stats */}
                    <div className="flex items-center gap-4 mt-3">
                      <span className="text-xs text-zinc-500">
                        {scenario.affectedComponents.length} affected services
                      </span>
                      <span className="text-xs text-zinc-500">
                        Recovery: {scenario.estimatedRecoveryTime}
                      </span>
                    </div>
                  </div>
                  <div className="ml-4 text-zinc-500 text-xl flex-shrink-0">
                    {isExpanded ? '\u25B2' : '\u25BC'}
                  </div>
                </button>

                {/* Expanded */}
                {isExpanded && (
                  <div className="border-t border-zinc-800 p-6 space-y-6">
                    {/* Trigger */}
                    <div className="bg-amber-500/5 border border-amber-500/10 rounded-xl p-4">
                      <h4 className="text-sm font-semibold text-amber-400 mb-1">Trigger</h4>
                      <p className="text-sm text-zinc-300">{scenario.trigger}</p>
                    </div>

                    {/* Blast Radius */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-300 mb-3">Blast Radius</h4>
                      <div className="mb-4">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-zinc-500">Impact spread</span>
                          <span className="text-xs font-mono text-zinc-400">{blastPercentage}% critical/high</span>
                        </div>
                        <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded-full transition-all duration-700',
                              blastPercentage >= 70 ? 'bg-red-500' :
                              blastPercentage >= 40 ? 'bg-orange-500' :
                              'bg-yellow-500'
                            )}
                            style={{ width: `${blastPercentage}%` }}
                          />
                        </div>
                      </div>

                      <div className="grid gap-2">
                        {scenario.blastRadius.map((node, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between bg-zinc-800/50 border border-zinc-700/30 rounded-lg px-4 py-2"
                          >
                            <div className="flex items-center gap-3">
                              <div className={cn('w-2.5 h-2.5 rounded-full', impactColors[node.impact])} />
                              <div>
                                <span className="text-sm text-zinc-200">{node.component}</span>
                                <p className="text-[10px] text-zinc-500">{node.failureMode}</p>
                              </div>
                            </div>
                            <SeverityBadge severity={node.impact} size="sm" />
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Affected Services */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-300 mb-3">Affected Services</h4>
                      <div className="flex flex-wrap gap-2">
                        {scenario.affectedComponents.map((component) => (
                          <span
                            key={component}
                            className="px-3 py-1 text-xs bg-zinc-800 border border-zinc-700/50 rounded-lg text-zinc-300"
                          >
                            {component}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Missing Safeguards */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-300 mb-3">Missing Safeguards</h4>
                      <div className="space-y-2">
                        {scenario.missingSafeguards.map((safeguard, idx) => (
                          <div
                            key={idx}
                            className="flex items-start gap-3 p-3 bg-red-500/5 border border-red-500/10 rounded-lg"
                          >
                            <svg className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            <span className="text-sm text-zinc-300">{safeguard}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Recovery Time */}
                    <div className="bg-zinc-800/50 border border-zinc-700/30 rounded-xl p-4 flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-blue-500/15 flex items-center justify-center flex-shrink-0">
                        <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500 uppercase tracking-wider">Estimated Recovery Time</p>
                        <p className="text-lg font-semibold text-zinc-200">{scenario.estimatedRecoveryTime}</p>
                      </div>
                    </div>

                    {/* Timeline */}
                    {scenario.timeline.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-zinc-300 mb-3">Failure Timeline</h4>
                        <div className="space-y-2">
                          {scenario.timeline.map((event, idx) => (
                            <div
                              key={idx}
                              className="flex items-start gap-3 text-sm"
                            >
                              <span className="text-[10px] text-zinc-600 font-mono w-16 flex-shrink-0 pt-0.5">
                                {event.timestamp}
                              </span>
                              <div className={cn('w-2 h-2 rounded-full mt-1.5 flex-shrink-0', impactColors[event.impact])} />
                              <div>
                                <span className="text-zinc-300">{event.event}</span>
                                <span className="text-zinc-600 ml-2 text-xs">{event.component}</span>
                              </div>
                            </div>
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

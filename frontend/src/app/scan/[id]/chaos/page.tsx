'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import {
  getChaosScenarios,
  getChaosAvailability,
  getChaosExperiments,
  startChaosExperiment,
  approveChaosExperiment,
  rejectChaosExperiment,
  abortChaosExperiments,
} from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { ChaosScenario, ChaosExperiment, Severity, ExperimentStatus } from '@/lib/types';

const impactColors: Record<Severity, string> = {
  CRITICAL: 'bg-red-500',
  HIGH: 'bg-orange-500',
  MEDIUM: 'bg-yellow-500',
  LOW: 'bg-blue-500',
  INFO: 'bg-zinc-500',
};

const phaseLabels: Partial<Record<ExperimentStatus, string>> = {
  PLANNING: 'Planning experiment...',
  PROVISIONING: 'Spinning up sandbox containers...',
  BASELINE: 'Collecting baseline metrics...',
  PENDING_APPROVAL: 'Waiting for approval',
  STEADY_STATE: 'Verifying steady state...',
  INJECTING: 'Injecting faults!',
  OBSERVING: 'Observing system under chaos...',
  ROLLING_BACK: 'Rolling back faults...',
  RECOVERING: 'Measuring recovery...',
  COMPLETED: 'Experiment complete',
};

function ResilienceGauge({ score }: { score: number }) {
  const color = score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : score >= 40 ? 'text-orange-400' : 'text-red-400';
  const bgColor = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : score >= 40 ? 'bg-orange-500' : 'bg-red-500';
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-28 h-28">
        <svg className="w-28 h-28 transform -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" stroke="#27272a" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="42" fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeDasharray={`${score * 2.64} ${264 - score * 2.64}`}
            strokeLinecap="round"
            className={color}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn('text-2xl font-bold', color)}>{Math.round(score)}</span>
        </div>
      </div>
      <span className="text-xs text-zinc-500 mt-2">Resilience Score</span>
    </div>
  );
}

function ExperimentCard({ experiment, onApprove, onReject, onAbort, scanId }: {
  experiment: ChaosExperiment;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onAbort: (scanId: string) => void;
  scanId: string;
}) {
  const isActive = ['PLANNING', 'PROVISIONING', 'BASELINE', 'PENDING_APPROVAL', 'STEADY_STATE', 'INJECTING', 'OBSERVING', 'ROLLING_BACK', 'RECOVERING'].includes(experiment.status);
  const isComplete = experiment.status === 'COMPLETED';

  return (
    <div className={cn(
      'bg-zinc-900/70 border rounded-2xl overflow-hidden',
      isActive ? 'border-amber-500/50 shadow-lg shadow-amber-500/5' :
      isComplete ? 'border-zinc-700' : 'border-zinc-800'
    )}>
      {/* Header */}
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {isActive && (
              <div className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500" />
              </div>
            )}
            <span className={cn(
              'px-3 py-1 text-xs font-medium rounded-full uppercase tracking-wider',
              experiment.status === 'COMPLETED' ? 'bg-green-500/15 text-green-400' :
              experiment.status === 'FAILED' || experiment.status === 'ERROR' ? 'bg-red-500/15 text-red-400' :
              experiment.status === 'ABORTED' ? 'bg-zinc-500/15 text-zinc-400' :
              experiment.status === 'PENDING_APPROVAL' ? 'bg-purple-500/15 text-purple-400' :
              'bg-amber-500/15 text-amber-400'
            )}>
              {experiment.status.replace(/_/g, ' ')}
            </span>
          </div>

          {/* Emergency Stop */}
          {isActive && experiment.status !== 'PENDING_APPROVAL' && (
            <button
              onClick={() => onAbort(scanId)}
              className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-bold rounded-lg transition-colors flex items-center gap-2 animate-pulse"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              EMERGENCY STOP
            </button>
          )}
        </div>

        {/* Phase indicator */}
        {isActive && (
          <div className="mb-4 p-3 bg-zinc-800/50 rounded-xl">
            <p className="text-sm text-zinc-300">
              {phaseLabels[experiment.status] || experiment.status}
            </p>
          </div>
        )}

        {/* Approval buttons */}
        {experiment.status === 'PENDING_APPROVAL' && (
          <div className="flex gap-3 mb-4">
            <button
              onClick={() => onApprove(experiment.id)}
              className="flex-1 px-4 py-3 bg-green-600 hover:bg-green-500 text-white font-semibold rounded-xl transition-colors"
            >
              Approve & Execute
            </button>
            <button
              onClick={() => onReject(experiment.id)}
              className="flex-1 px-4 py-3 bg-zinc-700 hover:bg-zinc-600 text-zinc-200 font-semibold rounded-xl transition-colors"
            >
              Reject
            </button>
          </div>
        )}

        {/* Faults injected */}
        {experiment.faultsInjected && experiment.faultsInjected.length > 0 && (
          <div className="mb-4">
            <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Faults Injected</h4>
            <div className="flex flex-wrap gap-2">
              {experiment.faultsInjected.map((fault, idx) => (
                <span key={idx} className={cn(
                  'px-3 py-1.5 text-xs rounded-lg border',
                  fault.success ? 'bg-red-500/10 border-red-500/20 text-red-400' :
                  'bg-zinc-800 border-zinc-700 text-zinc-500'
                )}>
                  {fault.fault_type.replace(/_/g, ' ')} → {fault.target_service}
                  {fault.success ? ' ✓' : ' ✗'}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {isComplete && experiment.resilienceScore !== null && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
            {/* Resilience Score */}
            <div className="flex justify-center">
              <ResilienceGauge score={experiment.resilienceScore} />
            </div>

            {/* Metrics comparison */}
            <div className="space-y-3">
              <h4 className="text-xs text-zinc-500 uppercase tracking-wider">Availability</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Baseline</span>
                  <span className="text-green-400 font-mono">{experiment.baselineMetrics?.success_rate ?? 0}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Under Chaos</span>
                  <span className={cn('font-mono',
                    (experiment.chaosMetrics?.success_rate ?? 0) >= 80 ? 'text-green-400' :
                    (experiment.chaosMetrics?.success_rate ?? 0) >= 50 ? 'text-yellow-400' :
                    'text-red-400'
                  )}>{experiment.chaosMetrics?.success_rate ?? 0}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Recovery</span>
                  <span className="text-blue-400 font-mono">{experiment.recoveryTimeS ?? '?'}s</span>
                </div>
              </div>
            </div>

            {/* Response times */}
            <div className="space-y-3">
              <h4 className="text-xs text-zinc-500 uppercase tracking-wider">Response Time</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Baseline avg</span>
                  <span className="text-zinc-300 font-mono">{experiment.baselineMetrics?.avg_response_ms ?? 0}ms</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Chaos avg</span>
                  <span className="text-zinc-300 font-mono">{experiment.chaosMetrics?.avg_response_ms ?? 0}ms</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Chaos p99</span>
                  <span className="text-zinc-300 font-mono">{experiment.chaosMetrics?.p99_response_ms ?? 0}ms</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Verdict */}
        {experiment.verdict && (
          <div className={cn(
            'mt-4 p-4 rounded-xl border',
            experiment.resilienceScore && experiment.resilienceScore >= 80 ? 'bg-green-500/5 border-green-500/20' :
            experiment.resilienceScore && experiment.resilienceScore >= 60 ? 'bg-yellow-500/5 border-yellow-500/20' :
            'bg-red-500/5 border-red-500/20'
          )}>
            <p className="text-sm text-zinc-300">{experiment.verdict}</p>
          </div>
        )}

        {/* Recommendations */}
        {experiment.recommendations && experiment.recommendations.length > 0 && (
          <div className="mt-4">
            <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Recommendations</h4>
            <div className="space-y-2">
              {experiment.recommendations.map((rec, idx) => (
                <div key={idx} className="flex items-start gap-2 text-sm text-zinc-400">
                  <span className="text-blue-400 mt-0.5">→</span>
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {(experiment.status === 'ERROR' || experiment.status === 'FAILED') && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
            <p className="text-sm text-red-400">Experiment failed</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChaosPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scenarios, setScenarios] = useState<ChaosScenario[]>([]);
  const [experiments, setExperiments] = useState<ChaosExperiment[]>([]);
  const [chaosAvailable, setChaosAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [startingExperiment, setStartingExperiment] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [scenarioData, availData, expData] = await Promise.all([
        getChaosScenarios(scanId).catch(() => []),
        getChaosAvailability(scanId).catch(() => ({ available: false, reason: '' })),
        getChaosExperiments(scanId).catch(() => []),
      ]);
      setScenarios(scenarioData);
      setChaosAvailable(availData.available);
      setExperiments(Array.isArray(expData) ? expData : []);
    } catch {
      // handle silently
    } finally {
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll for experiment updates when any experiment is active
  useEffect(() => {
    const hasActive = experiments.some(e =>
      ['PLANNING', 'PROVISIONING', 'BASELINE', 'PENDING_APPROVAL', 'STEADY_STATE', 'INJECTING', 'OBSERVING', 'ROLLING_BACK', 'RECOVERING', 'RUNNING'].includes(e.status)
    );
    if (!hasActive) return;

    const interval = setInterval(async () => {
      try {
        const expData = await getChaosExperiments(scanId);
        setExperiments(Array.isArray(expData) ? expData : []);
      } catch {
        // ignore
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [experiments, scanId]);

  const handleStartExperiment = async (scenarioId: string) => {
    setStartingExperiment(scenarioId);
    try {
      await startChaosExperiment(scanId, scenarioId, false);
      // Reload experiments after a brief delay
      setTimeout(loadData, 2000);
    } catch (err) {
      console.error('Failed to start experiment:', err);
    } finally {
      setStartingExperiment(null);
    }
  };

  const handleApprove = async (experimentId: string) => {
    try {
      await approveChaosExperiment(experimentId);
      setTimeout(loadData, 1000);
    } catch (err) {
      console.error('Failed to approve:', err);
    }
  };

  const handleReject = async (experimentId: string) => {
    try {
      await rejectChaosExperiment(experimentId);
      setTimeout(loadData, 1000);
    } catch (err) {
      console.error('Failed to reject:', err);
    }
  };

  const handleAbort = async () => {
    try {
      await abortChaosExperiments(scanId);
      setTimeout(loadData, 2000);
    } catch (err) {
      console.error('Failed to abort:', err);
    }
  };

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
        <h1 className="text-2xl font-bold text-zinc-100">Chaos Engineering</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Failure injection scenarios, blast radius analysis, and live resilience testing
        </p>
      </div>

      {/* Active / Past Experiments */}
      {experiments.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-zinc-200 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            Chaos Experiments
          </h2>
          {experiments.map((exp) => (
            <ExperimentCard
              key={exp.id}
              experiment={exp}
              onApprove={handleApprove}
              onReject={handleReject}
              onAbort={handleAbort}
              scanId={scanId}
            />
          ))}
        </div>
      )}

      {/* Scenarios */}
      {scenarios.length === 0 ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No chaos scenarios generated for this scan.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-zinc-200">Detected Scenarios</h2>
          {scenarios.map((scenario) => {
            const isExpanded = expandedId === scenario.id;
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
                <div className="flex items-start justify-between p-6">
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : scenario.id)}
                    className="flex-1 text-left"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <SeverityBadge severity={scenario.severity} />
                      <span className="px-2 py-0.5 text-[10px] rounded-full bg-zinc-700/50 text-zinc-400 uppercase tracking-wider">
                        {scenario.scenarioType.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-100 mb-1">{scenario.title}</h3>
                    <p className="text-sm text-zinc-400 line-clamp-2">{scenario.description}</p>
                    <div className="flex items-center gap-4 mt-3">
                      <span className="text-xs text-zinc-500">
                        {scenario.affectedComponents.length} affected services
                      </span>
                      <span className="text-xs text-zinc-500">
                        Recovery: {scenario.estimatedRecoveryTime}
                      </span>
                    </div>
                  </button>

                  <div className="flex items-center gap-2 ml-4">
                    {/* Execute button */}
                    {chaosAvailable && (
                      <button
                        onClick={() => handleStartExperiment(scenario.id)}
                        disabled={startingExperiment === scenario.id}
                        className={cn(
                          'px-4 py-2 text-sm font-semibold rounded-lg transition-all',
                          startingExperiment === scenario.id
                            ? 'bg-zinc-700 text-zinc-400 cursor-wait'
                            : 'bg-amber-600 hover:bg-amber-500 text-white hover:shadow-lg hover:shadow-amber-500/20'
                        )}
                      >
                        {startingExperiment === scenario.id ? (
                          <span className="flex items-center gap-2">
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            Starting...
                          </span>
                        ) : (
                          'Execute Chaos'
                        )}
                      </button>
                    )}
                    <span className="text-zinc-500 text-xl">
                      {isExpanded ? '\u25B2' : '\u25BC'}
                    </span>
                  </div>
                </div>

                {/* Expanded details — same as before */}
                {isExpanded && (
                  <div className="border-t border-zinc-800 p-6 space-y-6">
                    {scenario.trigger && (
                      <div className="bg-amber-500/5 border border-amber-500/10 rounded-xl p-4">
                        <h4 className="text-sm font-semibold text-amber-400 mb-1">Trigger</h4>
                        <p className="text-sm text-zinc-300">{scenario.trigger}</p>
                      </div>
                    )}

                    {scenario.blastRadius && scenario.blastRadius.length > 0 && (
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
                    )}

                    {scenario.affectedComponents && scenario.affectedComponents.length > 0 && (
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
                    )}

                    {scenario.missingSafeguards && scenario.missingSafeguards.length > 0 && (
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
                    )}

                    {scenario.timeline && scenario.timeline.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-zinc-300 mb-3">Failure Timeline</h4>
                        <div className="space-y-2">
                          {scenario.timeline.map((event, idx) => (
                            <div key={idx} className="flex items-start gap-3 text-sm">
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

      {/* Info banner when chaos execution is not available */}
      {chaosAvailable === false && scenarios.length > 0 && (
        <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-4 flex items-start gap-3">
          <svg className="w-5 h-5 text-zinc-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm text-zinc-300 font-medium">Live chaos execution unavailable</p>
            <p className="text-xs text-zinc-500 mt-1">
              This repository does not contain a docker-compose.yml. Chaos scenarios above are analysis-only.
              To enable live fault injection, the scanned repo must include a Docker Compose configuration.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

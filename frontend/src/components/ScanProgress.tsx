'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import { getScan, getFindings } from '@/lib/api';
import type { ScanStatus, Finding } from '@/lib/types';
import SeverityBadge from './SeverityBadge';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';

interface ScanProgressProps {
  scanId: string;
  initialStatus?: ScanStatus;
  onComplete?: () => void;
}

// Maps scan status to a progress step and estimated percentage
const statusProgress: Record<ScanStatus, { step: number; label: string; description: string }> = {
  QUEUED: { step: 0, label: 'Queued', description: 'Waiting to start...' },
  CLONING: { step: 1, label: 'Cloning Repository', description: 'Downloading source code from remote...' },
  CLONING_COMPLETE: { step: 2, label: 'Clone Complete', description: 'Repository cloned successfully' },
  INDEXING: { step: 3, label: 'Indexing Codebase', description: 'Building code index and generating embeddings...' },
  INDEXING_COMPLETE: { step: 4, label: 'Indexing Complete', description: 'Code index built successfully' },
  ANALYZING: { step: 5, label: 'Analyzing Security', description: 'AI agents scanning for vulnerabilities...' },
  GENERATING_FIXES: { step: 6, label: 'Generating Fixes', description: 'Creating verified fix suggestions...' },
  COMPLETE: { step: 7, label: 'Scan Complete', description: 'All analysis finished' },
  FAILED: { step: -1, label: 'Scan Failed', description: 'An error occurred during scanning' },
};

const totalSteps = 7;

export default function ScanProgress({ scanId, initialStatus, onComplete }: ScanProgressProps) {
  const [status, setStatus] = useState<ScanStatus>(initialStatus || 'QUEUED');
  const [findings, setFindings] = useState<Finding[]>([]);
  const [statusHistory, setStatusHistory] = useState<{ status: ScanStatus; time: Date }[]>([
    { status: initialStatus || 'QUEUED', time: new Date() },
  ]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const prevStatus = useRef<ScanStatus>(initialStatus || 'QUEUED');
  const completeCalled = useRef(false);

  // Poll scan status via REST every 3s
  const pollScan = useCallback(async () => {
    try {
      const scan = await getScan(scanId);
      const newStatus = scan.status;
      setStatus(newStatus);

      if (scan.errorMessage) {
        setErrorMessage(scan.errorMessage);
      }

      // Track status changes for the timeline
      if (newStatus !== prevStatus.current) {
        prevStatus.current = newStatus;
        setStatusHistory((prev) => [...prev, { status: newStatus, time: new Date() }]);
      }

      if ((newStatus === 'COMPLETE' || newStatus === 'FAILED') && !completeCalled.current) {
        completeCalled.current = true;
        onComplete?.();
      }
    } catch {
      // Network error - will retry on next poll
    }
  }, [scanId, onComplete]);

  // Poll findings periodically when analyzing
  const pollFindings = useCallback(async () => {
    try {
      const data = await getFindings(scanId, { size: 10, page: 0 });
      if (data.content.length > 0) {
        setFindings(data.content);
      }
    } catch {
      // Findings may not be ready yet
    }
  }, [scanId]);

  useEffect(() => {
    pollScan();
    const scanInterval = setInterval(pollScan, 3000);

    return () => clearInterval(scanInterval);
  }, [pollScan]);

  // Poll findings less frequently, only during analysis
  useEffect(() => {
    if (status !== 'ANALYZING' && status !== 'GENERATING_FIXES') return;
    pollFindings();
    const findingInterval = setInterval(pollFindings, 10000);
    return () => clearInterval(findingInterval);
  }, [status, pollFindings]);

  const progressInfo = statusProgress[status];
  const progressPercent = status === 'FAILED' ? 100 : Math.round((progressInfo.step / totalSteps) * 100);

  const steps = [
    { key: 'QUEUED', label: 'Queued', icon: ClockIcon },
    { key: 'CLONING', label: 'Cloning', icon: ArrowPathIcon },
    { key: 'INDEXING', label: 'Indexing', icon: ArrowPathIcon },
    { key: 'ANALYZING', label: 'Analyzing', icon: ArrowPathIcon },
    { key: 'GENERATING_FIXES', label: 'Fixes', icon: ArrowPathIcon },
    { key: 'COMPLETE', label: 'Done', icon: CheckCircleIcon },
  ];

  const currentStepIndex = steps.findIndex((s) => s.key === status);
  const isTerminal = status === 'COMPLETE' || status === 'FAILED';

  return (
    <div className="space-y-6">
      {/* Overall Progress Header */}
      <div className="glass-card rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-zinc-100">{progressInfo.label}</h3>
            <p className="text-sm text-zinc-500 mt-0.5">{progressInfo.description}</p>
          </div>
          <div className="flex items-center gap-3">
            {!isTerminal && (
              <div className="flex items-center gap-2">
                <div className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-400" />
                </div>
                <span className="text-xs text-zinc-500">Polling</span>
              </div>
            )}
            <span className="text-2xl font-bold text-zinc-100 font-mono">{progressPercent}%</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-2 bg-white/[0.04] border border-white/[0.04] rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-700',
              status === 'FAILED' ? 'bg-red-500' : status === 'COMPLETE' ? 'bg-green-500' : 'bg-blue-500'
            )}
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-between mt-6">
          {steps.map((step, idx) => {
            const isActive = step.key === status || (step.key === 'CLONING' && (status === 'CLONING' || status === 'CLONING_COMPLETE'))
              || (step.key === 'INDEXING' && (status === 'INDEXING' || status === 'INDEXING_COMPLETE'));
            const isPast = idx < currentStepIndex || (status === 'COMPLETE');
            const isFailed = status === 'FAILED';
            const StepIcon = isPast ? CheckCircleIcon : step.icon;

            return (
              <div key={step.key} className="flex flex-col items-center gap-1.5 flex-1">
                <div
                  className={cn(
                    'w-8 h-8 rounded-full flex items-center justify-center border transition-all',
                    isPast
                      ? 'bg-green-500/20 border-green-500/30'
                      : isActive && !isFailed
                      ? 'bg-blue-500/20 border-blue-500/30'
                      : isFailed && isActive
                      ? 'bg-red-500/20 border-red-500/30'
                      : 'bg-white/[0.02] border-white/[0.06]'
                  )}
                >
                  {isPast ? (
                    <CheckCircleIcon className="w-4 h-4 text-green-400" />
                  ) : isActive && !isFailed ? (
                    <ArrowPathIcon className="w-4 h-4 text-blue-400 animate-spin" />
                  ) : isFailed && isActive ? (
                    <ExclamationCircleIcon className="w-4 h-4 text-red-400" />
                  ) : (
                    <StepIcon className="w-4 h-4 text-zinc-600" />
                  )}
                </div>
                <span
                  className={cn(
                    'text-[10px] font-medium uppercase tracking-wider',
                    isPast ? 'text-green-400' : isActive ? (isFailed ? 'text-red-400' : 'text-blue-400') : 'text-zinc-600'
                  )}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error message */}
      {status === 'FAILED' && errorMessage && (
        <div className="glass-card glow-red rounded-xl p-4 flex items-start gap-3 animate-scale-in">
          <ExclamationCircleIcon className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm text-red-400 font-medium">Scan Failed</p>
            <p className="text-xs text-zinc-400 mt-1">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Status Timeline */}
      {statusHistory.length > 1 && (
        <div className="glass-card rounded-xl p-4">
          <h4 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
            <div className="w-1 h-3 rounded-full bg-gradient-to-b from-blue-500 to-purple-500" />
            Status Timeline
          </h4>
          <div className="space-y-2">
            {statusHistory.map((entry, i) => (
              <div key={i} className="flex items-center gap-3 text-xs animate-fade-in">
                <span className="text-zinc-600 font-mono w-20 flex-shrink-0">
                  {entry.time.toLocaleTimeString()}
                </span>
                <div
                  className={cn(
                    'w-2 h-2 rounded-full flex-shrink-0',
                    entry.status === 'COMPLETE' ? 'bg-green-400' :
                    entry.status === 'FAILED' ? 'bg-red-400' :
                    'bg-blue-400'
                  )}
                />
                <span className="text-zinc-400">{statusProgress[entry.status]?.label || entry.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Findings (only when analyzing) */}
      {findings.length > 0 && (
        <div className="glass-card rounded-xl p-4">
          <h4 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
            <div className="w-1 h-3 rounded-full bg-gradient-to-b from-red-500 to-orange-500" />
            Recent Findings ({findings.length})
          </h4>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {findings.map((finding, i) => (
              <div
                key={`${finding.id}-${i}`}
                className="flex items-start gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] animate-fade-in"
              >
                <SeverityBadge severity={finding.severity} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-zinc-300 truncate">{finding.title}</p>
                  <p className="text-[10px] text-zinc-600 font-mono truncate">
                    {finding.filePath}:{finding.startLine}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

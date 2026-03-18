'use client';

import { useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { ScanWebSocket } from '@/lib/websocket';
import type { AgentProgress, ScanProgressUpdate, Finding, ScanStatus } from '@/lib/types';
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

const statusLabels: Record<ScanStatus, string> = {
  QUEUED: 'Queued',
  CLONING: 'Cloning Repository',
  CLONING_COMPLETE: 'Clone Complete',
  INDEXING: 'Indexing Codebase',
  INDEXING_COMPLETE: 'Indexing Complete',
  ANALYZING: 'Analyzing Security',
  GENERATING_FIXES: 'Generating Fixes',
  COMPLETE: 'Scan Complete',
  FAILED: 'Scan Failed',
};

export default function ScanProgress({ scanId, initialStatus, onComplete }: ScanProgressProps) {
  const [agents, setAgents] = useState<AgentProgress[]>([]);
  const [status, setStatus] = useState<ScanStatus>(initialStatus || 'QUEUED');
  const [connected, setConnected] = useState(false);
  const [recentFindings, setRecentFindings] = useState<Finding[]>([]);
  const [logMessages, setLogMessages] = useState<string[]>([]);
  const [connectionLost, setConnectionLost] = useState(false);

  const handleMessage = useCallback(
    (update: ScanProgressUpdate) => {
      setStatus(update.status);
      setAgents(update.agents);

      if (update.latestFinding) {
        setRecentFindings((prev) => [update.latestFinding!, ...prev].slice(0, 20));
      }

      if (update.logMessage) {
        setLogMessages((prev) => [update.logMessage!, ...prev].slice(0, 50));
      }

      if (update.status === 'COMPLETE' || update.status === 'FAILED') {
        onComplete?.();
      }
    },
    [onComplete]
  );

  useEffect(() => {
    const ws = new ScanWebSocket(scanId, handleMessage, setConnected, () => {
      setConnectionLost(true);
    });
    ws.connect();
    return () => ws.disconnect();
  }, [scanId, handleMessage]);

  const overallProgress =
    agents.length > 0
      ? Math.round(agents.reduce((sum, a) => sum + a.progress, 0) / agents.length)
      : 0;

  const StatusIcon = ({ agentStatus }: { agentStatus: AgentProgress['status'] }) => {
    switch (agentStatus) {
      case 'COMPLETE':
        return <CheckCircleIcon className="w-5 h-5 text-green-400" />;
      case 'FAILED':
        return <ExclamationCircleIcon className="w-5 h-5 text-red-400" />;
      case 'RUNNING':
        return <ArrowPathIcon className="w-5 h-5 text-blue-400 animate-spin" />;
      default:
        return <ClockIcon className="w-5 h-5 text-zinc-600" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Overall Progress Header */}
      <div className="glass-card rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-zinc-100">{statusLabels[status]}</h3>
            <p className="text-sm text-zinc-500 mt-0.5">
              {agents.filter((a) => a.status === 'COMPLETE').length} of {agents.length} agents
              complete
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div
                className={cn('w-2 h-2 rounded-full', connected ? 'bg-green-400' : connectionLost ? 'bg-zinc-500' : 'bg-red-400 animate-pulse')}
              />
              <span className="text-xs text-zinc-500">
                {connected ? 'Live' : connectionLost ? 'Disconnected' : 'Reconnecting...'}
              </span>
            </div>
            <span className="text-2xl font-bold text-zinc-100 font-mono">{overallProgress}%</span>
          </div>
        </div>

        <div className="w-full h-2 bg-white/[0.04] border border-white/[0.04] rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              status === 'FAILED' ? 'bg-red-500' : status === 'COMPLETE' ? 'bg-green-500' : 'bg-blue-500'
            )}
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* Connection Lost Banner */}
      {connectionLost && (
        <div className="glass-card glow-red rounded-xl p-4 flex items-center justify-between animate-scale-in">
          <div className="flex items-center gap-3">
            <ExclamationCircleIcon className="w-5 h-5 text-red-400" />
            <div>
              <p className="text-sm text-zinc-200 font-medium">Connection lost</p>
              <p className="text-xs text-zinc-500">Live updates are no longer available.</p>
            </div>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-xs font-medium bg-white/[0.06] border border-white/[0.08] text-zinc-300 rounded-lg hover:bg-white/[0.1] transition-colors"
          >
            Refresh
          </button>
        </div>
      )}

      {/* Agent Progress Bars */}
      <div className="grid gap-3 stagger-children">
        {agents.map((agent) => (
          <div
            key={agent.agentName}
            className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-4 hover:bg-white/[0.03] transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <StatusIcon agentStatus={agent.status} />
                <div>
                  <span className="text-sm font-medium text-zinc-200">{agent.agentName}</span>
                  {agent.currentTask && (
                    <p className="text-xs text-zinc-500 mt-0.5">{agent.currentTask}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {agent.findingsCount > 0 && (
                  <span className="text-xs text-zinc-400 bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 rounded-md">
                    {agent.findingsCount} findings
                  </span>
                )}
                <span className="text-xs text-zinc-500 font-mono w-10 text-right">
                  {agent.progress}%
                </span>
              </div>
            </div>
            <div className="w-full h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-500', {
                  'bg-green-500': agent.status === 'COMPLETE',
                  'bg-red-500': agent.status === 'FAILED',
                  'bg-blue-500': agent.status === 'RUNNING',
                  'bg-zinc-600': agent.status === 'PENDING',
                })}
                style={{ width: `${agent.progress}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Live Findings Feed */}
        <div className="glass-card rounded-xl p-4">
          <h4 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
            <div className="w-1 h-3 rounded-full bg-gradient-to-b from-red-500 to-orange-500" />
            Live Findings
          </h4>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {recentFindings.length === 0 ? (
              <p className="text-xs text-zinc-600 py-4 text-center">
                Waiting for findings...
              </p>
            ) : (
              recentFindings.map((finding, i) => (
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
              ))
            )}
          </div>
        </div>

        {/* Activity Log */}
        <div className="glass-card rounded-xl p-4">
          <h4 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
            <div className="w-1 h-3 rounded-full bg-gradient-to-b from-blue-500 to-purple-500" />
            Activity Log
          </h4>
          <div className="space-y-1 max-h-64 overflow-y-auto font-mono text-[11px]">
            {logMessages.length === 0 ? (
              <p className="text-xs text-zinc-600 py-4 text-center font-sans">
                Waiting for activity...
              </p>
            ) : (
              logMessages.map((msg, i) => (
                <div key={i} className="text-zinc-500 animate-fade-in py-0.5">
                  <span className="text-zinc-600 mr-2">
                    {new Date().toLocaleTimeString()}
                  </span>
                  {msg}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

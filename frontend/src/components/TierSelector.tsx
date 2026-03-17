'use client';

import { cn } from '@/lib/utils';
import type { ScanTier } from '@/lib/types';
import {
  ShieldCheckIcon,
  MagnifyingGlassIcon,
  BoltIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';

interface TierSelectorProps {
  selectedTier: ScanTier;
  onSelect: (tier: ScanTier) => void;
}

const tiers: {
  value: ScanTier;
  name: string;
  description: string;
  agents: string[];
  time: string;
  icon: typeof ShieldCheckIcon;
  color: string;
  borderColor: string;
  bgColor: string;
  glowColor: string;
}[] = [
  {
    value: 'RECON',
    name: 'Recon',
    description: 'Fast surface-level security scan. Identifies common vulnerabilities, misconfigurations, and dependency issues.',
    agents: ['Static Analyzer'],
    time: '~2 min',
    icon: MagnifyingGlassIcon,
    color: 'text-blue-400',
    borderColor: 'border-blue-500/50',
    bgColor: 'bg-blue-500/10',
    glowColor: 'shadow-blue-500/20',
  },
  {
    value: 'HUNTER',
    name: 'Hunter',
    description: 'Deep multi-agent analysis with data flow tracing, dependency auditing, chaos engineering, and auto-fix generation.',
    agents: ['Static Analyzer', 'Data Flow Tracer', 'Dependency Auditor', 'Chaos Engineer'],
    time: '~8 min',
    icon: ShieldCheckIcon,
    color: 'text-purple-400',
    borderColor: 'border-purple-500/50',
    bgColor: 'bg-purple-500/10',
    glowColor: 'shadow-purple-500/20',
  },
  {
    value: 'SIEGE',
    name: 'Siege',
    description: 'Full offensive security assessment. All agents plus attack chain analysis, pentest playbooks, and PoC generation.',
    agents: [
      'Static Analyzer',
      'Data Flow Tracer',
      'Dependency Auditor',
      'Chaos Engineer',
      'Attack Chain Analyzer',
      'Exploit Validator',
      'Pentest Planner',
      'Report Synthesizer',
    ],
    time: '~20 min',
    icon: BoltIcon,
    color: 'text-red-400',
    borderColor: 'border-red-500/50',
    bgColor: 'bg-red-500/10',
    glowColor: 'shadow-red-500/20',
  },
  {
    value: 'LIVE',
    name: 'Live',
    description: 'Dynamic application security testing. All static analysis plus targeted DAST probes against a running instance. Requires target_url.',
    agents: [
      'Static Analyzer',
      'Data Flow Tracer',
      'Dependency Auditor',
      'Chaos Engineer',
      'Attack Chain Analyzer',
      'IDOR Probe',
      'Auth Bypass Probe',
      'SQLi Probe',
      'Race Condition Probe',
    ],
    time: '~35 min',
    icon: GlobeAltIcon,
    color: 'text-orange-400',
    borderColor: 'border-orange-500/50',
    bgColor: 'bg-orange-500/10',
    glowColor: 'shadow-orange-500/20',
  },
];

export default function TierSelector({ selectedTier, onSelect }: TierSelectorProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {tiers.map((tier) => {
        const isSelected = selectedTier === tier.value;
        const Icon = tier.icon;

        return (
          <button
            key={tier.value}
            onClick={() => onSelect(tier.value)}
            className={cn(
              'relative flex flex-col items-start p-6 rounded-xl border-2 transition-all duration-300 text-left',
              'hover:scale-[1.02] hover:shadow-lg',
              isSelected
                ? cn(tier.borderColor, tier.bgColor, `shadow-lg ${tier.glowColor}`)
                : 'border-zinc-700/50 bg-zinc-800/50 hover:border-zinc-600'
            )}
          >
            {isSelected && (
              <div className="absolute top-3 right-3">
                <div className={cn('w-3 h-3 rounded-full', {
                  'bg-blue-400': tier.value === 'RECON',
                  'bg-purple-400': tier.value === 'HUNTER',
                  'bg-red-400': tier.value === 'SIEGE',
                  'bg-orange-400': tier.value === 'LIVE',
                })} />
              </div>
            )}

            <div className={cn('p-2 rounded-lg mb-4', tier.bgColor)}>
              <Icon className={cn('w-6 h-6', tier.color)} />
            </div>

            <h3 className={cn('text-lg font-bold mb-1', tier.color)}>
              {tier.name}
            </h3>
            <p className="text-sm text-zinc-400 mb-4 leading-relaxed">
              {tier.description}
            </p>

            <div className="mt-auto w-full">
              <div className="flex items-center justify-between text-xs text-zinc-500 mb-2">
                <span>{tier.agents.length} agent{tier.agents.length > 1 ? 's' : ''}</span>
                <span>{tier.time}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {tier.agents.map((agent) => (
                  <span
                    key={agent}
                    className="px-1.5 py-0.5 text-[10px] rounded bg-zinc-700/50 text-zinc-400"
                  >
                    {agent}
                  </span>
                ))}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

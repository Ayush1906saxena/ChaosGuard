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
  glowClass: string;
  dotColor: string;
}[] = [
  {
    value: 'RECON',
    name: 'Recon',
    description: 'Fast surface-level security scan. Identifies common vulnerabilities, misconfigurations, and dependency issues.',
    agents: ['Static Analyzer'],
    time: '~2 min',
    icon: MagnifyingGlassIcon,
    color: 'text-blue-400',
    borderColor: 'border-blue-500/30',
    bgColor: 'bg-blue-500/[0.07]',
    glowClass: 'glow-blue',
    dotColor: 'bg-blue-400',
  },
  {
    value: 'HUNTER',
    name: 'Hunter',
    description: 'Deep multi-agent analysis with data flow tracing, dependency auditing, chaos engineering, and auto-fix generation.',
    agents: ['Static Analyzer', 'Data Flow Tracer', 'Dependency Auditor', 'Chaos Engineer'],
    time: '~8 min',
    icon: ShieldCheckIcon,
    color: 'text-purple-400',
    borderColor: 'border-purple-500/30',
    bgColor: 'bg-purple-500/[0.07]',
    glowClass: 'glow-purple',
    dotColor: 'bg-purple-400',
  },
  {
    value: 'SIEGE',
    name: 'Siege',
    description: 'Full offensive security assessment. All agents plus attack chain analysis, pentest playbooks, and PoC generation.',
    agents: [
      'Static Analyzer', 'Data Flow Tracer', 'Dependency Auditor', 'Chaos Engineer',
      'Attack Chain Analyzer', 'Exploit Validator', 'Pentest Planner', 'Report Synthesizer',
    ],
    time: '~20 min',
    icon: BoltIcon,
    color: 'text-red-400',
    borderColor: 'border-red-500/30',
    bgColor: 'bg-red-500/[0.07]',
    glowClass: 'glow-red',
    dotColor: 'bg-red-400',
  },
  {
    value: 'LIVE',
    name: 'Live',
    description: 'Dynamic application security testing. All static analysis plus targeted DAST probes against a running instance.',
    agents: [
      'Static Analyzer', 'Data Flow Tracer', 'Dependency Auditor', 'Chaos Engineer',
      'Attack Chain Analyzer', 'IDOR Probe', 'Auth Bypass Probe', 'SQLi Probe', 'Race Condition Probe',
    ],
    time: '~35 min',
    icon: GlobeAltIcon,
    color: 'text-orange-400',
    borderColor: 'border-orange-500/30',
    bgColor: 'bg-orange-500/[0.07]',
    glowClass: 'glow-orange',
    dotColor: 'bg-orange-400',
  },
];

export default function TierSelector({ selectedTier, onSelect }: TierSelectorProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
      {tiers.map((tier) => {
        const isSelected = selectedTier === tier.value;
        const Icon = tier.icon;

        return (
          <button
            key={tier.value}
            onClick={() => onSelect(tier.value)}
            className={cn(
              'relative flex flex-col items-start p-5 rounded-2xl border transition-all duration-300 text-left',
              'hover:scale-[1.01]',
              isSelected
                ? cn(tier.borderColor, tier.bgColor, tier.glowClass, 'shadow-inner-light')
                : 'border-white/[0.04] bg-white/[0.02] hover:bg-white/[0.03] hover:border-white/[0.08]'
            )}
          >
            {isSelected && (
              <div className="absolute top-4 right-4">
                <div className={cn('w-2.5 h-2.5 rounded-full', tier.dotColor, 'shadow-lg')}
                  style={{ boxShadow: `0 0 8px currentColor` }}
                />
              </div>
            )}

            <div className={cn('p-2.5 rounded-xl mb-4', isSelected ? tier.bgColor : 'bg-white/[0.03]')}>
              <Icon className={cn('w-5 h-5', isSelected ? tier.color : 'text-zinc-500')} />
            </div>

            <h3 className={cn('text-base font-bold mb-1', isSelected ? tier.color : 'text-zinc-300')}>
              {tier.name}
            </h3>
            <p className="text-[13px] text-zinc-500 mb-4 leading-relaxed line-clamp-3">
              {tier.description}
            </p>

            <div className="mt-auto w-full">
              <div className="flex items-center justify-between text-[11px] text-zinc-600 mb-2.5">
                <span>{tier.agents.length} agent{tier.agents.length > 1 ? 's' : ''}</span>
                <span className="font-mono">{tier.time}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {tier.agents.slice(0, 4).map((agent) => (
                  <span
                    key={agent}
                    className="px-1.5 py-0.5 text-[9px] rounded-md bg-white/[0.04] text-zinc-500 border border-white/[0.04]"
                  >
                    {agent}
                  </span>
                ))}
                {tier.agents.length > 4 && (
                  <span className="px-1.5 py-0.5 text-[9px] rounded-md bg-white/[0.04] text-zinc-600">
                    +{tier.agents.length - 4}
                  </span>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getDependencyGraph } from '@/lib/api';
import DependencyGraph from '@/components/DependencyGraph';
import type { DependencyNode, DependencyEdge } from '@/lib/types';

export default function GraphPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [nodes, setNodes] = useState<DependencyNode[]>([]);
  const [edges, setEdges] = useState<DependencyEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const graph = await getDependencyGraph(scanId);
        setNodes(graph.nodes);
        setEdges(graph.edges);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dependency graph');
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
          Loading dependency graph...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-6 py-4 text-sm text-red-400">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Dependency Graph</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Interactive visualization of code dependencies and risk propagation
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-zinc-500">
          <span>{nodes.length} nodes</span>
          <span>{edges.length} edges</span>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
          <p className="text-zinc-500">No dependency data available for this scan.</p>
        </div>
      ) : (
        <div className="h-[calc(100vh-220px)]">
          <DependencyGraph nodes={nodes} edges={edges} />
        </div>
      )}
    </div>
  );
}

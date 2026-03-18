'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import type { DependencyNode, DependencyEdge, Severity } from '@/lib/types';
import { cn } from '@/lib/utils';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface DependencyGraphProps {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  onNodeClick?: (node: DependencyNode) => void;
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  type: DependencyNode['type'];
  riskLevel: DependencyNode['riskLevel'];
  findingCount: number;
  metadata: Record<string, string>;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  type: DependencyEdge['type'];
  label?: string;
}

const riskColors: Record<Severity | 'NONE', string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#3b82f6',
  INFO: '#6b7280',
  NONE: '#22c55e',
};

const nodeTypeShapes: Record<DependencyNode['type'], number> = {
  file: 6,
  package: 8,
  service: 10,
  database: 12,
  external: 7,
};

export default function DependencyGraph({ nodes, edges, onNodeClick }: DependencyGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: DependencyNode } | null>(null);
  const [selectedNode, setSelectedNode] = useState<DependencyNode | null>(null);

  const handleNodeClick = useCallback((node: DependencyNode) => {
    setSelectedNode(node);
    onNodeClick?.(node);
  }, [onNodeClick]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const rect = containerRef.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    svg.attr('width', width).attr('height', height);

    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Prepare data
    const simNodes: SimNode[] = nodes.map((n) => ({
      id: n.id,
      name: n.name,
      type: n.type,
      riskLevel: n.riskLevel,
      findingCount: n.findingCount,
      metadata: n.metadata,
    }));

    const simLinks: SimLink[] = edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
      label: e.label,
    }));

    // Force simulation
    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(25));

    // Arrow markers
    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'rgba(255,255,255,0.1)');

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', 'rgba(255,255,255,0.08)')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', (d) => d.type === 'data_flow' ? '4,2' : 'none')
      .attr('marker-end', 'url(#arrowhead)');

    // Nodes
    const node = g.append('g')
      .selectAll<SVGCircleElement, SimNode>('circle')
      .data(simNodes)
      .join('circle')
      .attr('r', (d) => nodeTypeShapes[d.type] || 6)
      .attr('fill', (d) => riskColors[d.riskLevel])
      .attr('stroke', 'rgba(0,0,0,0.3)')
      .attr('stroke-width', 2)
      .attr('cursor', 'pointer')
      .on('mouseover', function (_event, d) {
        d3.select(this).attr('stroke', '#fafafa').attr('stroke-width', 3);
        const svgRect = svgRef.current!.getBoundingClientRect();
        setTooltip({
          x: (_event as MouseEvent).clientX - svgRect.left,
          y: (_event as MouseEvent).clientY - svgRect.top - 10,
          node: {
            id: d.id,
            name: d.name,
            type: d.type,
            riskLevel: d.riskLevel,
            findingCount: d.findingCount,
            metadata: d.metadata,
          },
        });
      })
      .on('mouseout', function () {
        d3.select(this).attr('stroke', 'rgba(0,0,0,0.3)').attr('stroke-width', 2);
        setTooltip(null);
      })
      .on('click', (_event, d) => {
        handleNodeClick({
          id: d.id,
          name: d.name,
          type: d.type,
          riskLevel: d.riskLevel,
          findingCount: d.findingCount,
          metadata: d.metadata,
        });
      });

    // Labels
    const label = g.append('g')
      .selectAll('text')
      .data(simNodes)
      .join('text')
      .text((d) => d.name.length > 20 ? d.name.slice(0, 20) + '...' : d.name)
      .attr('font-size', '9px')
      .attr('fill', '#52525b')
      .attr('text-anchor', 'middle')
      .attr('dy', 20)
      .attr('pointer-events', 'none');

    // Drag behavior
    const drag = d3.drag<SVGCircleElement, SimNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    node.call(drag);

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x!)
        .attr('y1', (d) => (d.source as SimNode).y!)
        .attr('x2', (d) => (d.target as SimNode).x!)
        .attr('y2', (d) => (d.target as SimNode).y!);

      node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
      label.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, handleNodeClick]);

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[500px] glass-card rounded-xl">
      <svg ref={svgRef} className="w-full h-full" />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-10 pointer-events-none glass-card rounded-lg p-3 shadow-xl"
          style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
        >
          <p className="text-xs font-semibold text-zinc-200">{tooltip.node.name}</p>
          <p className="text-[10px] text-zinc-500 mt-0.5">
            Type: {tooltip.node.type} | Risk: {tooltip.node.riskLevel}
          </p>
          {tooltip.node.findingCount > 0 && (
            <p className="text-[10px] text-red-400 mt-0.5">
              {tooltip.node.findingCount} finding{tooltip.node.findingCount > 1 ? 's' : ''}
            </p>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 glass-card rounded-lg p-3">
        <p className="text-[10px] font-semibold text-zinc-400 mb-2 uppercase tracking-wider">Risk Level</p>
        <div className="space-y-1">
          {Object.entries(riskColors).map(([level, color]) => (
            <div key={level} className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[10px] text-zinc-500">{level}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Selected node details */}
      {selectedNode && (
        <div className="absolute top-4 right-4 w-64 glass-card rounded-xl p-4 shadow-xl animate-scale-in">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-zinc-200 truncate">{selectedNode.name}</h4>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-500">Type</span>
              <span className="text-zinc-300 capitalize">{selectedNode.type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Risk</span>
              <span style={{ color: riskColors[selectedNode.riskLevel] }}>{selectedNode.riskLevel}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Findings</span>
              <span className="text-zinc-300">{selectedNode.findingCount}</span>
            </div>
            {Object.entries(selectedNode.metadata).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <span className="text-zinc-500 capitalize">{key}</span>
                <span className="text-zinc-300 truncate ml-2">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Zoom controls */}
      <div className="absolute top-4 left-4 flex flex-col gap-1">
        <button
          onClick={() => {
            if (!svgRef.current) return;
            const svg = d3.select(svgRef.current);
            svg.transition().duration(300).call(
              d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.1, 4]).on('zoom', () => {}).scaleBy,
              1.3
            );
          }}
          className="w-7 h-7 glass-card rounded-lg text-zinc-400 hover:text-zinc-200 text-sm flex items-center justify-center transition-colors"
        >
          +
        </button>
        <button
          onClick={() => {
            if (!svgRef.current) return;
            const svg = d3.select(svgRef.current);
            svg.transition().duration(300).call(
              d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.1, 4]).on('zoom', () => {}).scaleBy,
              0.7
            );
          }}
          className="w-7 h-7 glass-card rounded-lg text-zinc-400 hover:text-zinc-200 text-sm flex items-center justify-center transition-colors"
        >
          -
        </button>
      </div>
    </div>
  );
}

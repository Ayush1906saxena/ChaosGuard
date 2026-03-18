'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { getFileTree, getFileContent, getFindings } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { FileTreeNode, FileContent, Finding, Severity } from '@/lib/types';
import {
  FolderIcon,
  DocumentIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

const severityIndicator: Record<Severity, string> = {
  CRITICAL: 'bg-red-500',
  HIGH: 'bg-orange-500',
  MEDIUM: 'bg-yellow-500',
  LOW: 'bg-blue-500',
  INFO: 'bg-zinc-500',
};

function TreeItem({
  node,
  depth,
  onSelect,
  selectedPath,
}: {
  node: FileTreeNode;
  depth: number;
  onSelect: (path: string) => void;
  selectedPath: string | null;
}) {
  const [expanded, setExpanded] = useState(depth === 0);
  const isDir = node.type === 'directory';
  const isSelected = selectedPath === node.path;

  return (
    <div>
      <button
        onClick={() => {
          if (isDir) setExpanded(!expanded);
          else onSelect(node.path);
        }}
        className={cn(
          'w-full flex items-center gap-2 px-2 py-1.5 text-left text-xs rounded-lg transition-colors',
          isSelected ? 'bg-white/[0.06] text-zinc-100 border border-white/[0.08]' : 'text-zinc-400 hover:bg-white/[0.03] hover:text-zinc-200'
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          expanded ? (
            <ChevronDownIcon className="w-3 h-3 text-zinc-500 flex-shrink-0" />
          ) : (
            <ChevronRightIcon className="w-3 h-3 text-zinc-500 flex-shrink-0" />
          )
        ) : (
          <span className="w-3 flex-shrink-0" />
        )}

        {isDir ? (
          <FolderIcon className="w-4 h-4 text-blue-400/70 flex-shrink-0" />
        ) : (
          <DocumentIcon className="w-4 h-4 text-zinc-500 flex-shrink-0" />
        )}

        <span className="truncate flex-1">{node.name}</span>

        {node.findingCount && node.findingCount > 0 && (
          <div className="flex items-center gap-1">
            {node.maxSeverity && (
              <div className={cn('w-2 h-2 rounded-full', severityIndicator[node.maxSeverity])} />
            )}
            <span className="text-[10px] text-zinc-500">{node.findingCount}</span>
          </div>
        )}
      </button>

      {isDir && expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              selectedPath={selectedPath}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function CodePage() {
  const params = useParams();
  const scanId = params.id as string;
  const [tree, setTree] = useState<FileTreeNode[]>([]);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const treeData = await getFileTree(scanId);
        setTree(treeData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file tree');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  const handleSelectFile = useCallback(async (path: string) => {
    setSelectedPath(path);
    setLoadingFile(true);
    setSelectedFinding(null);
    setFileError(null);
    try {
      const content = await getFileContent(scanId, path);
      setFileContent(content);
    } catch (err) {
      setFileContent(null);
      setFileError(err instanceof Error ? err.message : 'Failed to load file');
    } finally {
      setLoadingFile(false);
    }
  }, [scanId]);

  const handleFindingClick = useCallback((finding: Finding) => {
    setSelectedFinding(finding);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-zinc-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading file tree...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Failed to load file tree</p>
          <p className="text-zinc-500 text-xs mb-4">{error}</p>
          <button onClick={() => window.location.reload()} className="px-4 py-2 text-xs bg-white/[0.04] border border-white/[0.06] text-zinc-400 rounded-lg hover:bg-white/[0.08] transition-colors">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Code Explorer</h1>
        <p className="text-sm text-zinc-500 mt-1">Browse source code and view vulnerability markers</p>
      </div>

      <div className="flex gap-4 h-[calc(100vh-220px)]">
        {/* File Tree Sidebar */}
        <div className="w-72 flex-shrink-0 glass-card rounded-xl overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-white/[0.04]">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Files</h3>
          </div>
          <div className="flex-1 overflow-y-auto py-2">
            {tree.map((node) => (
              <TreeItem
                key={node.path}
                node={node}
                depth={0}
                onSelect={handleSelectFile}
                selectedPath={selectedPath}
              />
            ))}
          </div>
        </div>

        {/* Code Viewer */}
        <div className="flex-1 glass-card rounded-xl overflow-hidden flex flex-col">
          {!selectedPath ? (
            <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
              Select a file to view its contents
            </div>
          ) : loadingFile ? (
            <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
              Loading file...
            </div>
          ) : fileContent ? (
            <>
              {/* File header */}
              <div className="px-4 py-2 border-b border-white/[0.04] flex items-center justify-between bg-white/[0.02]">
                <span className="text-xs font-mono text-zinc-400">{fileContent.path}</span>
                <span className="text-[10px] text-zinc-600 uppercase bg-white/[0.04] px-2 py-0.5 rounded-md">{fileContent.language}</span>
              </div>

              {/* Findings bar */}
              {fileContent.findings.length > 0 && (
                <div className="px-4 py-2 border-b border-white/[0.04] bg-white/[0.01]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider mr-2">Findings:</span>
                    {fileContent.findings.map((f) => (
                      <button
                        key={f.id}
                        onClick={() => handleFindingClick(f)}
                        className={cn(
                          'flex items-center gap-1.5 px-2 py-0.5 rounded-lg text-[10px] border transition-colors',
                          selectedFinding?.id === f.id
                            ? 'bg-white/[0.06] border-white/[0.1] text-zinc-200'
                            : 'bg-white/[0.02] border-white/[0.04] text-zinc-400 hover:border-white/[0.08]'
                        )}
                      >
                        <SeverityBadge severity={f.severity} size="sm" />
                        <span className="truncate max-w-[120px]">{f.title}</span>
                        <span className="text-zinc-600">L{f.startLine}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Code content */}
              <div className="flex-1 overflow-auto">
                <pre className="text-xs font-mono">
                  {fileContent.content.split('\n').map((line, idx) => {
                    const lineNum = idx + 1;
                    const isVuln = fileContent.findings.some(
                      (f) => lineNum >= f.startLine && lineNum <= f.endLine
                    );
                    const isSelectedVuln = selectedFinding &&
                      lineNum >= selectedFinding.startLine &&
                      lineNum <= selectedFinding.endLine;

                    return (
                      <div
                        key={idx}
                        className={cn(
                          'flex',
                          isSelectedVuln ? 'bg-red-500/10 border-l-2 border-red-500/50' :
                          isVuln ? 'bg-orange-500/[0.05] border-l-2 border-orange-500/30' : 'border-l-2 border-transparent'
                        )}
                      >
                        <span className="w-12 text-right pr-4 text-zinc-600 select-none flex-shrink-0 py-0.5">
                          {lineNum}
                        </span>
                        <span className={cn(
                          'flex-1 py-0.5 pr-4',
                          isVuln ? 'text-zinc-200' : 'text-zinc-400'
                        )}>
                          {line || ' '}
                        </span>
                      </div>
                    );
                  })}
                </pre>
              </div>

              {/* Selected finding detail */}
              {selectedFinding && (
                <div className="border-t border-white/[0.04] p-4 bg-white/[0.02] animate-slide-up">
                  <div className="flex items-start gap-3">
                    <SeverityBadge severity={selectedFinding.severity} size="sm" />
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-zinc-200">{selectedFinding.title}</h4>
                      <p className="text-xs text-zinc-400 mt-1">{selectedFinding.description}</p>
                      <p className="text-xs text-zinc-500 mt-2">
                        <span className="font-semibold text-zinc-400">Recommendation:</span>{' '}
                        {selectedFinding.recommendation}
                      </p>
                    </div>
                    <button
                      onClick={() => setSelectedFinding(null)}
                      className="text-zinc-500 hover:text-zinc-300 flex-shrink-0"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm">
              <div className="text-center">
                <p className="text-red-400 mb-1">Unable to load file</p>
                {fileError && <p className="text-zinc-600 text-xs">{fileError}</p>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { getFileTree, getFileContent, getFindings } from '@/lib/api';
import SeverityBadge from '@/components/SeverityBadge';
import { cn } from '@/lib/utils';
import type { FileTreeNode, FileContent, Finding, Severity } from '@/lib/types';

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
          'w-full flex items-center gap-2 px-2 py-1 text-left text-xs rounded transition-colors',
          isSelected ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          <span className="text-zinc-500 w-4 text-center flex-shrink-0">
            {expanded ? '\u25BE' : '\u25B8'}
          </span>
        ) : (
          <span className="w-4 flex-shrink-0" />
        )}

        <span className="truncate flex-1">
          {isDir ? '\uD83D\uDCC1' : '\uD83D\uDCC4'} {node.name}
        </span>

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
  const [loadingFile, setLoadingFile] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const treeData = await getFileTree(scanId);
        setTree(treeData);
      } catch {
        // handle silently
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
    try {
      const content = await getFileContent(scanId, path);
      setFileContent(content);
    } catch {
      setFileContent(null);
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

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Code Explorer</h1>
        <p className="text-sm text-zinc-500 mt-1">Browse source code and view vulnerability markers</p>
      </div>

      <div className="flex gap-4 h-[calc(100vh-220px)]">
        {/* File Tree Sidebar */}
        <div className="w-72 flex-shrink-0 bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-zinc-800">
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
        <div className="flex-1 bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden flex flex-col">
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
              <div className="px-4 py-2 border-b border-zinc-800 flex items-center justify-between bg-zinc-800/50">
                <span className="text-xs font-mono text-zinc-400">{fileContent.path}</span>
                <span className="text-[10px] text-zinc-600 uppercase">{fileContent.language}</span>
              </div>

              {/* Findings bar */}
              {fileContent.findings.length > 0 && (
                <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-800/30">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider mr-2">Findings:</span>
                    {fileContent.findings.map((f) => (
                      <button
                        key={f.id}
                        onClick={() => handleFindingClick(f)}
                        className={cn(
                          'flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] border transition-colors',
                          selectedFinding?.id === f.id
                            ? 'bg-zinc-700 border-zinc-600 text-zinc-200'
                            : 'bg-zinc-800 border-zinc-700/50 text-zinc-400 hover:border-zinc-600'
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
                          isSelectedVuln ? 'code-line-vuln bg-red-500/15' :
                          isVuln ? 'code-line-warn' : ''
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
                <div className="border-t border-zinc-800 p-4 bg-zinc-800/50">
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
                      className="text-zinc-500 hover:text-zinc-300 text-sm flex-shrink-0"
                    >
                      {'\u2715'}
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
              Unable to load file content
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

'use client';

import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface DiffViewerProps {
  originalCode: string;
  fixedCode: string;
  filePath?: string;
  startLine?: number;
}

interface DiffLine {
  type: 'add' | 'remove' | 'context';
  content: string;
  oldLineNum: number | null;
  newLineNum: number | null;
}

function computeDiff(original: string, fixed: string, startLine: number): DiffLine[] {
  const oldLines = original.split('\n');
  const newLines = fixed.split('\n');
  const result: DiffLine[] = [];

  // Simple LCS-based diff
  const m = oldLines.length;
  const n = newLines.length;

  // Build LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to produce diff
  const diffLines: DiffLine[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      diffLines.unshift({
        type: 'context',
        content: oldLines[i - 1],
        oldLineNum: startLine + i - 1,
        newLineNum: startLine + j - 1,
      });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      diffLines.unshift({
        type: 'add',
        content: newLines[j - 1],
        oldLineNum: null,
        newLineNum: startLine + j - 1,
      });
      j--;
    } else if (i > 0) {
      diffLines.unshift({
        type: 'remove',
        content: oldLines[i - 1],
        oldLineNum: startLine + i - 1,
        newLineNum: null,
      });
      i--;
    }
  }

  return diffLines;
}

export default function DiffViewer({ originalCode, fixedCode, filePath, startLine = 1 }: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<'unified' | 'split'>('unified');
  const diffLines = useMemo(() => computeDiff(originalCode, fixedCode, startLine), [originalCode, fixedCode, startLine]);

  const additions = diffLines.filter((l) => l.type === 'add').length;
  const deletions = diffLines.filter((l) => l.type === 'remove').length;

  return (
    <div className="rounded-xl border border-zinc-700/50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-800/80 border-b border-zinc-700/50">
        <div className="flex items-center gap-3">
          {filePath && (
            <span className="text-xs font-mono text-zinc-400">{filePath}</span>
          )}
          <span className="text-xs text-green-400">+{additions}</span>
          <span className="text-xs text-red-400">-{deletions}</span>
        </div>
        <div className="flex items-center gap-1 bg-zinc-900 rounded-lg p-0.5">
          <button
            onClick={() => setViewMode('unified')}
            className={cn(
              'px-2 py-1 text-[10px] rounded-md transition-colors',
              viewMode === 'unified' ? 'bg-zinc-700 text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'
            )}
          >
            Unified
          </button>
          <button
            onClick={() => setViewMode('split')}
            className={cn(
              'px-2 py-1 text-[10px] rounded-md transition-colors',
              viewMode === 'split' ? 'bg-zinc-700 text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'
            )}
          >
            Split
          </button>
        </div>
      </div>

      {/* Diff content */}
      {viewMode === 'unified' ? (
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <tbody>
              {diffLines.map((line, idx) => (
                <tr
                  key={idx}
                  className={cn({
                    'bg-red-500/10': line.type === 'remove',
                    'bg-green-500/10': line.type === 'add',
                  })}
                >
                  <td className="px-2 py-0.5 text-right text-zinc-600 select-none w-12 border-r border-zinc-800">
                    {line.oldLineNum ?? ''}
                  </td>
                  <td className="px-2 py-0.5 text-right text-zinc-600 select-none w-12 border-r border-zinc-800">
                    {line.newLineNum ?? ''}
                  </td>
                  <td className="px-1 py-0.5 select-none w-6 text-center">
                    {line.type === 'add' && <span className="text-green-400">+</span>}
                    {line.type === 'remove' && <span className="text-red-400">-</span>}
                  </td>
                  <td className="px-2 py-0.5 whitespace-pre">
                    <span className={cn({
                      'text-green-300': line.type === 'add',
                      'text-red-300': line.type === 'remove',
                      'text-zinc-400': line.type === 'context',
                    })}>
                      {line.content}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-2 divide-x divide-zinc-700/50 overflow-x-auto">
          {/* Original */}
          <div>
            <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-600 bg-zinc-800/50 border-b border-zinc-700/50">
              Original
            </div>
            <table className="w-full text-xs font-mono">
              <tbody>
                {diffLines
                  .filter((l) => l.type !== 'add')
                  .map((line, idx) => (
                    <tr
                      key={idx}
                      className={cn({ 'bg-red-500/10': line.type === 'remove' })}
                    >
                      <td className="px-2 py-0.5 text-right text-zinc-600 select-none w-10 border-r border-zinc-800">
                        {line.oldLineNum ?? ''}
                      </td>
                      <td className="px-2 py-0.5 whitespace-pre">
                        <span className={cn(line.type === 'remove' ? 'text-red-300' : 'text-zinc-400')}>
                          {line.content}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {/* Fixed */}
          <div>
            <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-600 bg-zinc-800/50 border-b border-zinc-700/50">
              Fixed
            </div>
            <table className="w-full text-xs font-mono">
              <tbody>
                {diffLines
                  .filter((l) => l.type !== 'remove')
                  .map((line, idx) => (
                    <tr
                      key={idx}
                      className={cn({ 'bg-green-500/10': line.type === 'add' })}
                    >
                      <td className="px-2 py-0.5 text-right text-zinc-600 select-none w-10 border-r border-zinc-800">
                        {line.newLineNum ?? ''}
                      </td>
                      <td className="px-2 py-0.5 whitespace-pre">
                        <span className={cn(line.type === 'add' ? 'text-green-300' : 'text-zinc-400')}>
                          {line.content}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

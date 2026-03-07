'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LatexDiffViewerProps {
  original: string;
  modified: string;
}

type DiffLine =
  | { kind: 'equal'; text: string }
  | { kind: 'remove'; text: string }
  | { kind: 'add'; text: string }
  | { kind: 'separator' };

const CONTEXT = 3; // lines of context around each change

/** Very small Myers-inspired line diff (no external dependency). */
function diffLines(a: string[], b: string[]): DiffLine[] {
  // Build LCS table
  const m = a.length, n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j]
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);

  const raw: DiffLine[] = [];
  let i = 0, j = 0;
  while (i < m || j < n) {
    if (i < m && j < n && a[i] === b[j]) {
      raw.push({ kind: 'equal', text: a[i++] });
      j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      raw.push({ kind: 'add', text: b[j++] });
    } else {
      raw.push({ kind: 'remove', text: a[i++] });
    }
  }
  return raw;
}

/** Collapse unchanged regions to ±CONTEXT lines around each hunk. */
function buildHunks(lines: DiffLine[]): DiffLine[] {
  const changed = new Set<number>();
  lines.forEach((l, i) => { if (l.kind !== 'equal') changed.add(i); });

  if (changed.size === 0) return [];

  const visible = new Set<number>();
  changed.forEach((ci) => {
    for (let k = ci - CONTEXT; k <= ci + CONTEXT; k++)
      if (k >= 0 && k < lines.length) visible.add(k);
  });

  const result: DiffLine[] = [];
  let prevVisible = false;
  lines.forEach((l, i) => {
    if (visible.has(i)) {
      if (!prevVisible && result.length > 0) result.push({ kind: 'separator' });
      result.push(l);
      prevVisible = true;
    } else {
      prevVisible = false;
    }
  });
  return result;
}

export function LatexDiffViewer({ original, modified }: LatexDiffViewerProps) {
  const [expanded, setExpanded] = useState(true);

  const hunks = useMemo(() => {
    const aLines = original.split('\n');
    const bLines = modified.split('\n');
    const all = diffLines(aLines, bLines);
    return buildHunks(all);
  }, [original, modified]);

  const changeCount = hunks.filter((l) => l.kind === 'remove' || l.kind === 'add').length;

  if (changeCount === 0) return (
    <p className="mt-2 text-xs text-muted-foreground italic">No changes detected.</p>
  );

  return (
    <div className="mt-2 rounded-lg overflow-hidden border border-border/40 text-xs">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-1.5 bg-[#252526] text-muted-foreground hover:bg-[#2d2d2d] transition-colors"
      >
        <span className="font-mono text-[11px]">
          Proposed diff — {changeCount} changed line{changeCount !== 1 ? 's' : ''}
        </span>
        {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {expanded && (
        <div className="overflow-auto max-h-64 bg-[#1e1e1e] font-mono text-[11px] leading-5">
          {hunks.map((line, idx) => {
            if (line.kind === 'separator') {
              return (
                <div key={idx} className="px-3 py-0.5 bg-[#252526] text-[#555] select-none">
                  ···
                </div>
              );
            }
            return (
              <div
                key={idx}
                className={cn(
                  'px-3 whitespace-pre-wrap break-all',
                  line.kind === 'remove' && 'bg-red-950/40 text-red-300',
                  line.kind === 'add'    && 'bg-emerald-950/40 text-emerald-300',
                  line.kind === 'equal'  && 'text-[#888]',
                )}
              >
                <span className="select-none mr-2 opacity-50">
                  {line.kind === 'remove' ? '−' : line.kind === 'add' ? '+' : ' '}
                </span>
                {line.text}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

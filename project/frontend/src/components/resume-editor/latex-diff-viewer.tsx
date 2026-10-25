'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { buildHunks, diffLines } from './latex-diff';

interface LatexDiffViewerProps {
  original: string;
  modified: string;
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

  if (changeCount === 0)
    return <p className="mt-2 text-xs text-muted-foreground italic">No changes detected.</p>;

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
                  line.kind === 'add' && 'bg-emerald-950/40 text-emerald-300',
                  line.kind === 'equal' && 'text-[#888]'
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

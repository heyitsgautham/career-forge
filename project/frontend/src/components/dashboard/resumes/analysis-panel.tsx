import { useState } from 'react';
import { FileText } from 'lucide-react';

export function AnalysisPanel({ analysis }: { analysis: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border bg-muted/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 text-sm font-medium hover:bg-muted/50 transition-colors rounded-lg"
      >
        <span className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          Step 0 Analysis
        </span>
        <span className="text-xs text-muted-foreground">{expanded ? 'Collapse' : 'Expand'}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          <pre className="text-xs font-mono whitespace-pre-wrap bg-background rounded-md p-3 border max-h-[300px] overflow-y-auto">
            {analysis}
          </pre>
        </div>
      )}
    </div>
  );
}

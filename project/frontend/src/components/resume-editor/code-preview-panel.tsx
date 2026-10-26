import { useState, type ReactNode } from 'react';
import { Code2, Eye, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * The editor's main panel: the LaTeX source, or the compiled PDF once there is
 * one. The editor stays mounted while the preview shows, so no edits are lost.
 */
export function CodePreviewPanel({
  editor,
  fileName,
  pdfUrl,
  onPreviewWithoutPdf,
}: {
  editor: ReactNode;
  fileName: string;
  pdfUrl: string | null;
  onPreviewWithoutPdf: () => void;
}) {
  const [activeTab, setActiveTab] = useState<'code' | 'preview'>('code');

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar: Code / Preview toggle */}
      <div className="flex items-center gap-0 px-2 py-1.5 border-b bg-card shrink-0">
        <button
          onClick={() => setActiveTab('code')}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors',
            activeTab === 'code'
              ? 'bg-violet-600 text-white'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          <Code2 className="h-3.5 w-3.5" />
          Code
        </button>
        <button
          onClick={() => {
            if (!pdfUrl) {
              onPreviewWithoutPdf();
              return;
            }
            setActiveTab('preview');
          }}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors',
            activeTab === 'preview'
              ? 'bg-violet-600 text-white'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          <Eye className="h-3.5 w-3.5" />
          Preview
        </button>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground pr-1">
          <FileText className="h-3.5 w-3.5" />
          {fileName}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {/* Monaco editor — always mounted so state is preserved, hidden when previewing */}
        <div className={cn('h-full', activeTab !== 'code' && 'hidden')}>{editor}</div>

        {/* Inline PDF preview */}
        {activeTab === 'preview' && (
          <div className="h-full bg-[#525659]">
            {pdfUrl ? (
              <iframe src={pdfUrl} title="Resume PDF preview" className="w-full h-full border-0" />
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-sm text-muted-foreground">No PDF yet — compile first</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

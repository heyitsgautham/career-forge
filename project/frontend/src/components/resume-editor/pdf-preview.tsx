'use client';

import { useState } from 'react';
import { Loader2, FileText, AlertCircle, RefreshCw, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type CompileStatus = 'idle' | 'compiling' | 'success' | 'error';

interface PdfPreviewProps {
  pdfUrl: string | null;
  compileStatus: CompileStatus;
  errorMessage?: string | null;
  onRecompile?: () => void;
  className?: string;
}

/**
 * PDF preview panel.
 * Shows the compiled PDF in an iframe, or appropriate state messages.
 */
export function PdfPreview({
  pdfUrl,
  compileStatus,
  errorMessage,
  onRecompile,
  className,
}: PdfPreviewProps) {
  const [zoom, setZoom] = useState(100);

  const canZoom = !!pdfUrl && compileStatus === 'success';

  return (
    <div className={cn('flex flex-col h-full bg-muted/30', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b bg-muted/50 shrink-0">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {compileStatus === 'compiling' && (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-500" />
              <span>Compiling…</span>
            </>
          )}
          {compileStatus === 'success' && (
            <>
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span>PDF ready</span>
            </>
          )}
          {compileStatus === 'error' && (
            <>
              <span className="h-2 w-2 rounded-full bg-red-500" />
              <span>Compile error</span>
            </>
          )}
          {compileStatus === 'idle' && (
            <>
              <span className="h-2 w-2 rounded-full bg-gray-400" />
              <span>Not compiled</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-1">
          {canZoom && (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setZoom((z) => Math.max(50, z - 10))}
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
              <span className="text-xs text-muted-foreground w-8 text-center">{zoom}%</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setZoom((z) => Math.min(200, z + 10))}
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          {onRecompile && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 text-xs px-2"
              onClick={onRecompile}
              disabled={compileStatus === 'compiling'}
            >
              <RefreshCw className={cn('h-3 w-3', compileStatus === 'compiling' && 'animate-spin')} />
              Recompile
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden relative">
        {/* Compiling overlay */}
        {compileStatus === 'compiling' && (
          <div className="absolute inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center z-10">
            <div className="flex flex-col items-center gap-3">
              <div className="relative h-12 w-12">
                <div className="absolute inset-0 rounded-full border-4 border-violet-200 dark:border-violet-900" />
                <div className="absolute inset-0 rounded-full border-4 border-violet-500 border-t-transparent animate-spin" />
              </div>
              <span className="text-sm text-muted-foreground">Compiling LaTeX…</span>
            </div>
          </div>
        )}

        {/* PDF iframe */}
        {pdfUrl && (
          <div
            className="h-full w-full overflow-auto"
            style={{ padding: zoom !== 100 ? '8px' : 0 }}
          >
            <iframe
              src={pdfUrl}
              title="PDF Preview"
              className="border-0 transition-all"
              style={{
                width: zoom !== 100 ? `${zoom}%` : '100%',
                height: zoom !== 100 ? `${zoom}%` : '100%',
                minHeight: '100%',
              }}
            />
          </div>
        )}

        {/* Error state */}
        {!pdfUrl && compileStatus === 'error' && (
          <div className="flex flex-col items-center justify-center h-full p-6 text-center gap-4">
            <div className="h-12 w-12 rounded-full bg-red-100 dark:bg-red-950/30 flex items-center justify-center">
              <AlertCircle className="h-6 w-6 text-red-500" />
            </div>
            <div>
              <p className="font-medium text-sm">Compilation failed</p>
              {errorMessage && (
                <pre className="mt-2 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/20 rounded-md p-3 max-h-32 overflow-y-auto text-left whitespace-pre-wrap">
                  {errorMessage}
                </pre>
              )}
            </div>
            {onRecompile && (
              <Button size="sm" variant="outline" onClick={onRecompile} className="gap-1.5">
                <RefreshCw className="h-3.5 w-3.5" />
                Try again
              </Button>
            )}
          </div>
        )}

        {/* Idle (not compiled yet) */}
        {!pdfUrl && compileStatus === 'idle' && (
          <div className="flex flex-col items-center justify-center h-full p-6 text-center gap-4 text-muted-foreground">
            <FileText className="h-16 w-16 opacity-20" />
            <div>
              <p className="font-medium text-sm">No PDF yet</p>
              <p className="text-xs mt-1 opacity-70">
                Press <kbd className="px-1.5 py-0.5 rounded border text-xs font-mono">Ctrl+Enter</kbd> or click{' '}
                <strong>Compile</strong> to generate the preview.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import { resumesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Download, Loader2, X, AlertTriangle } from 'lucide-react';
import { useState, useEffect } from 'react';
import type { Resume } from './types';

// ─── PDF Preview Modal ──────────────────────────────────────────────────────

export function PdfPreviewModal({
  resume,
  onClose,
  onDownload,
}: {
  resume: Resume;
  onClose: () => void;
  onDownload: () => void;
}) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoadError(false);
    setPdfUrl(null);

    resumesApi
      .getPdfUrl(resume.id)
      .then((res) => setPdfUrl(res.data.url))
      .catch(() => setLoadError(true));
  }, [resume.id]);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-background rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h3 className="font-semibold">{resume.name}</h3>
            <p className="text-xs text-muted-foreground">PDF Preview</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" className="gap-1.5" onClick={onDownload}>
              <Download className="h-3.5 w-3.5" />
              Download
            </Button>
            <Button size="icon" variant="ghost" onClick={onClose} className="h-8 w-8">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* PDF iframe */}
        <div className="flex-1 min-h-0 flex items-center justify-center">
          {!pdfUrl && !loadError && (
            <div className="flex flex-col items-center gap-3 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin" />
              <span className="text-sm">Loading preview…</span>
            </div>
          )}
          {loadError && (
            <div className="flex flex-col items-center gap-3 text-muted-foreground p-8 text-center">
              <AlertTriangle className="h-8 w-8 text-[hsl(var(--accent))]" />
              <p className="text-sm font-medium">Preview unavailable</p>
              <p className="text-xs text-muted-foreground/70">
                Use the Download button to open the PDF.
              </p>
            </div>
          )}
          {pdfUrl && (
            <iframe
              src={pdfUrl}
              title="Generated resume preview"
              aria-label={`Preview of ${resume.name}`}
              className="w-full h-full min-h-[60vh]"
              style={{ border: 'none' }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

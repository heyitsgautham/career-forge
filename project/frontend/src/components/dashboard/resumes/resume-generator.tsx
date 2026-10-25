'use client';

import { useMutation } from '@tanstack/react-query';
import { resumesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  FileText,
  Download,
  Edit,
  CheckCircle,
  XCircle,
  Loader2,
  X,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import type { Resume, Job } from './types';
import { apiErrorDetail } from '@/lib/api-error';

// ─── Resume Generator (M2 Flow) ────────────────────────────────────────────

export function ResumeGenerator({
  onClose,
  onGenerated,
}: {
  onClose: () => void;
  onGenerated: () => void;
}) {
  const [jdText, setJdText] = useState('');
  const [result, setResult] = useState<{
    resume_id: string;
    pdf_url: string | null;
    tex_url: string | null;
    analysis: string;
    status: string;
    compilation_error?: string | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const downloadTex = async (resumeId: string, filename?: string) => {
    try {
      const response = await resumesApi.downloadTex(resumeId);
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/plain' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename ?? `resume-${resumeId.slice(0, 8)}.tex`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast({ title: '.tex download failed', variant: 'destructive' });
    }
  };

  const generateMutation = useMutation({
    mutationFn: () => resumesApi.generateFromSummaries(jdText || undefined),
    onSuccess: (res) => {
      setResult(res.data);
      setError(null);
      toast({ title: 'Resume generated successfully!' });
    },
    onError: (err: unknown) => {
      const detail = apiErrorDetail(err, 'Generation failed');
      setError(detail);
      setResult(null);
    },
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-background rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Generate Resume</h2>
              <p className="text-xs text-muted-foreground">AI-powered from your GitHub projects</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* JD input */}
          <div className="space-y-2">
            <Label htmlFor="jd-input" className="text-sm font-medium">
              Job Description
              <span className="text-muted-foreground font-normal ml-1">(optional)</span>
            </Label>
            <Textarea
              id="jd-input"
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste a job description here to tailor your resume. Leave empty for a strong base resume ranked by project complexity."
              className="min-h-[120px] resize-y text-sm"
              disabled={generateMutation.isPending}
            />
            <p className="text-xs text-muted-foreground">
              Your resume will be generated from your ingested GitHub project summaries.
            </p>
          </div>

          {/* Generation in progress */}
          {generateMutation.isPending && (
            <div className="flex flex-col items-center py-8 space-y-4">
              <div className="relative">
                <div className="h-16 w-16 rounded-full border-4 border-primary/20" />
                <div className="absolute inset-0 h-16 w-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
              </div>
              <div className="text-center space-y-1">
                <p className="font-medium text-sm">Generating your resume…</p>
                <p className="text-xs text-muted-foreground">
                  Analyzing projects, ranking by relevance, crafting LaTeX…
                </p>
              </div>
            </div>
          )}

          {/* Error state */}
          {error && !generateMutation.isPending && (
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 space-y-2">
              <div className="flex items-start gap-2">
                <XCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium text-sm text-destructive">Generation failed</p>
                  <p className="text-xs text-destructive/80 mt-1">{error}</p>
                </div>
              </div>
              <p className="text-xs text-destructive/70 pl-7">
                Try re-importing your repos first, or check that GitHub ingestion completed.
              </p>
            </div>
          )}

          {/* Success: result */}
          {result && !generateMutation.isPending && (
            <div className="space-y-4">
              <div className="rounded-lg border border-[hsl(var(--success))]/20 bg-[hsl(var(--success))]/5 p-4">
                <div className="flex items-start gap-2">
                  <CheckCircle className="h-5 w-5 text-[hsl(var(--success))] mt-0.5 shrink-0" />
                  <div className="space-y-2 flex-1">
                    <p className="font-medium text-sm text-[hsl(var(--success))]">
                      Resume {result.pdf_url ? 'generated & compiled' : 'generated (LaTeX saved)'}!
                    </p>

                    <div className="flex gap-2 flex-wrap">
                      {result.pdf_url && (
                        <a
                          href={result.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          download={`resume-${new Date().toISOString().split('T')[0]}.pdf`}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[hsl(var(--success))] text-white text-xs font-medium hover:opacity-90 transition-colors"
                        >
                          <Download className="h-3.5 w-3.5" />
                          Download PDF
                        </a>
                      )}
                      {result.tex_url && (
                        <button
                          onClick={() =>
                            downloadTex(
                              result.resume_id,
                              `resume-${new Date().toISOString().split('T')[0]}.tex`
                            )
                          }
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white dark:bg-gray-800 border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          Download .tex Source
                        </button>
                      )}
                      {/* Open in Editor shortcut — shown when status is compiled */}
                      <Link
                        href={`/dashboard/resumes/${result.resume_id}/edit`}
                        onClick={onClose}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-medium transition-colors"
                      >
                        <Edit className="h-3.5 w-3.5" />
                        Open in Editor
                      </Link>
                    </div>
                  </div>
                </div>
              </div>

              {/* Compilation warning — shown when LaTeX was generated but PDF failed */}
              {!result.pdf_url && result.compilation_error && (
                <div className="rounded-lg border border-[hsl(var(--accent))]/20 bg-[hsl(var(--accent))]/5 p-3 space-y-1">
                  <div className="flex items-start gap-2">
                    <XCircle className="h-4 w-4 text-[hsl(var(--accent))] mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs font-medium text-[hsl(var(--accent))]">
                        PDF compilation failed
                      </p>
                      <p className="text-xs text-[hsl(var(--accent))]/80 mt-0.5 font-mono break-all">
                        {result.compilation_error}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-amber-500/80 dark:text-amber-400/50 pl-6">
                    Download the .tex source above to compile manually or regenerate.
                  </p>
                </div>
              )}

              {/* Analysis collapse */}
              {result.analysis && <AnalysisPanel analysis={result.analysis} />}

              {/* PDF preview */}
              {result.pdf_url && (
                <div className="rounded-lg overflow-hidden border">
                  <iframe
                    src={result.pdf_url}
                    title="Generated resume preview"
                    aria-label="Preview of generated resume"
                    className="w-full h-[500px]"
                    style={{ border: 'none' }}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t bg-muted/30">
          <Button variant="ghost" onClick={onClose} className="text-sm">
            {result ? 'Close' : 'Cancel'}
          </Button>
          <div className="flex gap-2">
            {result && (
              <Button
                variant="outline"
                onClick={() => {
                  onGenerated();
                }}
                className="text-sm"
              >
                Done
              </Button>
            )}
            <Button
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="gap-2 text-sm bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : result ? (
                <>
                  <RefreshCw className="h-4 w-4" />
                  Regenerate
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Generate Resume
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Analysis Panel ─────────────────────────────────────────────────────────

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

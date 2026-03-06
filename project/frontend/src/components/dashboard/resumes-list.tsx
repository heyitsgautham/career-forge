'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { resumesApi, jobsApi, templatesApi, api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  FileText, Download, Edit, Trash2, Clock, CheckCircle, XCircle,
  Loader2, Plus, X, Sparkles, Eye, RefreshCw, AlertTriangle, ExternalLink,
} from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/hooks/use-toast';

interface Resume {
  id: string;
  name: string;
  template_id?: string;
  job_description_id?: string;
  status: 'draft' | 'generating' | 'generated' | 'compiling' | 'compiled' | 'error';
  pdf_path?: string;
  latex_content?: string;
  error_message?: string;
  analysis?: string;
  tex_s3_key?: string;
  created_at: string;
  updated_at: string;
}

interface Job {
  id: string;
  title: string;
  company: string;
}

interface Template {
  id: string;
  name: string;
}

const statusConfig = {
  draft: { icon: Clock, color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300', text: 'Draft' },
  generating: { icon: Loader2, color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300', text: 'Generating…', animate: true },
  generated: { icon: CheckCircle, color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300', text: 'Generated' },
  compiling: { icon: Loader2, color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300', text: 'Compiling…', animate: true },
  compiled: { icon: CheckCircle, color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300', text: 'Ready' },
  error: { icon: XCircle, color: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300', text: 'Error' },
};

// ─── Main Component ────────────────────────────────────────────────────────────

export function ResumesList() {
  const [showGenerator, setShowGenerator] = useState(false);
  const [previewResume, setPreviewResume] = useState<Resume | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: resumes, isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: async () => {
      const res = await resumesApi.list();
      return res.data as Resume[];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => resumesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'Resume deleted' });
    },
  });

  const downloadPdf = async (resume: Resume) => {
    if (!resume.pdf_path) {
      toast({ title: 'PDF not available', variant: 'destructive' });
      return;
    }
    try {
      const response = await api.get(`/api/resumes/${resume.id}/pdf`, {
        responseType: 'blob',
        maxRedirects: 0,
        validateStatus: (s) => s < 400,
      });

      // Handle redirect (presigned URL)
      if (response.status >= 300 && response.status < 400) {
        const redirectUrl = response.headers['location'];
        if (redirectUrl) {
          window.open(redirectUrl, '_blank');
          return;
        }
      }

      // Download blob
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const date = new Date(resume.created_at).toISOString().split('T')[0];
      link.setAttribute('download', `resume-${date}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      // For redirects, the browser may have already downloaded
      // Try opening the PDF endpoint directly
      window.open(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/resumes/${resume.id}/pdf`,
        '_blank'
      );
    }
  };

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

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-10 bg-muted/40 rounded-lg w-48 animate-pulse" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-5 bg-muted rounded w-3/4" />
                <div className="h-4 bg-muted rounded w-1/2 mt-2" />
              </CardHeader>
              <CardContent>
                <div className="h-8 bg-muted rounded w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with generate button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Resumes</h2>
          <p className="text-sm text-muted-foreground">
            {resumes?.length || 0} resume{resumes?.length !== 1 ? 's' : ''} generated
          </p>
        </div>
        <Button
          onClick={() => setShowGenerator(true)}
          className="gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white shadow-md hover:shadow-lg transition-all"
        >
          <Sparkles className="h-4 w-4" />
          Generate Resume
        </Button>
      </div>

      {/* Generator modal */}
      {showGenerator && (
        <ResumeGenerator
          onClose={() => setShowGenerator(false)}
          onGenerated={() => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] });
            setShowGenerator(false);
          }}
        />
      )}

      {/* PDF Preview modal */}
      {previewResume && (
        <PdfPreviewModal
          resume={previewResume}
          onClose={() => setPreviewResume(null)}
          onDownload={() => downloadPdf(previewResume)}
        />
      )}

      {/* Result area with aria-live for screen readers */}
      <div aria-live="polite" role="status">
        {/* Empty state */}
        {(!resumes || resumes.length === 0) && (
          <Card className="text-center py-16 border-dashed border-2">
            <CardContent className="space-y-4">
              <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">No resumes yet</h3>
                <p className="text-muted-foreground mt-1 max-w-sm mx-auto">
                  Generate your first resume from your GitHub projects. Import your repos first, then click Generate.
                </p>
              </div>
              <Button
                onClick={() => setShowGenerator(true)}
                className="gap-2"
              >
                <Sparkles className="h-4 w-4" />
                Generate Your First Resume
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Resume grid */}
        {resumes && resumes.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {resumes.map((resume) => {
              const status = statusConfig[resume.status] || statusConfig.draft;
              const StatusIcon = status.icon;
              const isProcessing = resume.status === 'generating' || resume.status === 'compiling';

              return (
                <Card
                  key={resume.id}
                  className="group hover:shadow-md transition-all duration-200 border-l-4 border-l-violet-500/60"
                >
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start gap-2">
                      <CardTitle className="text-base font-medium line-clamp-1">
                        {resume.name}
                      </CardTitle>
                      <Badge
                        variant="secondary"
                        className={`shrink-0 text-xs font-medium gap-1 ${status.color}`}
                      >
                        <StatusIcon className={`h-3 w-3 ${isProcessing ? 'animate-spin' : ''}`} />
                        {status.text}
                      </Badge>
                    </div>
                    <CardDescription className="text-xs">
                      {new Date(resume.updated_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    {resume.error_message && (
                      <div className="flex items-start gap-2 p-2 mb-3 rounded-md bg-red-50 dark:bg-red-950/30 text-sm">
                        <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-red-700 dark:text-red-400 line-clamp-2 text-xs">
                            {resume.error_message}
                          </p>
                          <p className="text-red-500/70 dark:text-red-400/50 text-xs mt-1">
                            Try re-importing your repos first
                          </p>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between">
                      <div className="flex gap-1.5">
                        {(resume.status === 'compiled' || resume.status === 'generated') && resume.pdf_path && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              className="gap-1 h-8 text-xs"
                              onClick={() => setPreviewResume(resume)}
                            >
                              <Eye className="h-3 w-3" />
                              Preview
                            </Button>
                            <Button
                              size="sm"
                              className="gap-1 h-8 text-xs"
                              onClick={() => downloadPdf(resume)}
                            >
                              <Download className="h-3 w-3" />
                              PDF
                            </Button>
                            {resume.tex_s3_key && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-1 h-8 text-xs"
                                onClick={() => downloadTex(resume.id, `resume-${new Date(resume.created_at).toISOString().split('T')[0]}.tex`)}
                              >
                                <FileText className="h-3 w-3" />
                                .tex
                              </Button>
                            )}
                          </>
                        )}
                        {resume.status === 'generated' && !resume.pdf_path && (
                          <CompileButton resumeId={resume.id} />
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => {
                          if (confirm('Delete this resume?')) {
                            deleteMutation.mutate(resume.id);
                          }
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Compile Button ─────────────────────────────────────────────────────────

function CompileButton({ resumeId }: { resumeId: string }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const compileMutation = useMutation({
    mutationFn: () => resumesApi.compile(resumeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'PDF compiled successfully!' });
    },
    onError: (error: any) => {
      toast({
        title: 'Compilation failed',
        description: error.response?.data?.detail || 'Check LaTeX syntax',
        variant: 'destructive',
      });
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
  });

  return (
    <Button
      size="sm"
      variant="outline"
      className="gap-1 h-8 text-xs"
      onClick={() => compileMutation.mutate()}
      disabled={compileMutation.isPending}
    >
      {compileMutation.isPending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <RefreshCw className="h-3 w-3" />
      )}
      Compile PDF
    </Button>
  );
}

// ─── PDF Preview Modal ──────────────────────────────────────────────────────

function PdfPreviewModal({
  resume,
  onClose,
  onDownload,
}: {
  resume: Resume;
  onClose: () => void;
  onDownload: () => void;
}) {
  const pdfUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/resumes/${resume.id}/pdf`;

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
        <div className="flex-1 min-h-0">
          <iframe
            src={pdfUrl}
            title="Generated resume preview"
            aria-label={`Preview of ${resume.name}`}
            className="w-full h-full min-h-[60vh]"
            style={{ border: 'none' }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Resume Generator (M2 Flow) ────────────────────────────────────────────

function ResumeGenerator({
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
    onError: (err: any) => {
      const detail = err.response?.data?.detail || 'Generation failed';
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
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Generate Resume</h2>
              <p className="text-xs text-muted-foreground">
                AI-powered from your GitHub projects
              </p>
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
                <div className="h-16 w-16 rounded-full border-4 border-violet-200 dark:border-violet-900" />
                <div className="absolute inset-0 h-16 w-16 rounded-full border-4 border-violet-600 border-t-transparent animate-spin" />
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
            <div className="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/20 p-4 space-y-2">
              <div className="flex items-start gap-2">
                <XCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium text-sm text-red-700 dark:text-red-400">
                    Generation failed
                  </p>
                  <p className="text-xs text-red-600/80 dark:text-red-400/70 mt-1">
                    {error}
                  </p>
                </div>
              </div>
              <p className="text-xs text-red-500/70 dark:text-red-400/50 pl-7">
                Try re-importing your repos first, or check that GitHub ingestion completed.
              </p>
            </div>
          )}

          {/* Success: result */}
          {result && !generateMutation.isPending && (
            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50 dark:bg-emerald-950/20 p-4">
                <div className="flex items-start gap-2">
                  <CheckCircle className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
                  <div className="space-y-2 flex-1">
                    <p className="font-medium text-sm text-emerald-700 dark:text-emerald-400">
                      Resume {result.pdf_url ? 'generated & compiled' : 'generated (LaTeX saved)'}!
                    </p>

                    <div className="flex gap-2 flex-wrap">
                      {result.pdf_url && (
                        <a
                          href={result.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          download={`resume-${new Date().toISOString().split('T')[0]}.pdf`}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 transition-colors"
                        >
                          <Download className="h-3.5 w-3.5" />
                          Download PDF
                        </a>
                      )}
                      {result.tex_url && (
                        <button
                          onClick={() => downloadTex(result.resume_id, `resume-${new Date().toISOString().split('T')[0]}.tex`)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white dark:bg-gray-800 border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          Download .tex Source
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Compilation warning — shown when LaTeX was generated but PDF failed */}
              {!result.pdf_url && result.compilation_error && (
                <div className="rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/20 p-3 space-y-1">
                  <div className="flex items-start gap-2">
                    <XCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs font-medium text-amber-700 dark:text-amber-400">PDF compilation failed</p>
                      <p className="text-xs text-amber-600/80 dark:text-amber-400/70 mt-0.5 font-mono break-all">{result.compilation_error}</p>
                    </div>
                  </div>
                  <p className="text-xs text-amber-500/80 dark:text-amber-400/50 pl-6">
                    Download the .tex source above to compile manually or regenerate.
                  </p>
                </div>
              )}

              {/* Analysis collapse */}
              {result.analysis && (
                <AnalysisPanel analysis={result.analysis} />
              )}

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
              className="gap-2 text-sm bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white"
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

function AnalysisPanel({ analysis }: { analysis: string }) {
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
        <span className="text-xs text-muted-foreground">
          {expanded ? 'Collapse' : 'Expand'}
        </span>
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

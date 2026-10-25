'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { resumesApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { FileText, Download, Edit, Trash2, Loader2, Sparkles, Eye } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import { statusConfig } from './resumes/status-config';
import { CompileButton } from './resumes/compile-button';
import { ResumeGenerator } from './resumes/resume-generator';
import type { Resume } from './resumes/types';

// ─── Main Component ────────────────────────────────────────────────────────────

export function ResumesList() {
  const [showGenerator, setShowGenerator] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: resumes, isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: async () => {
      const res = await resumesApi.list();
      return res.data as Resume[];
    },
    staleTime: 2 * 60 * 1000, // 2 min
    gcTime: 15 * 60 * 1000, // 15 min
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => resumesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'Resume deleted' });
    },
  });

  const [isDeletingAll, setIsDeletingAll] = useState(false);

  const deleteAll = async () => {
    if (!resumes || resumes.length === 0) return;
    if (
      !confirm(
        `Delete all ${resumes.length} resume${resumes.length !== 1 ? 's' : ''}? This cannot be undone.`
      )
    )
      return;
    setIsDeletingAll(true);
    try {
      await Promise.all(resumes.map((r) => resumesApi.delete(r.id)));
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: `Deleted ${resumes.length} resume${resumes.length !== 1 ? 's' : ''}` });
    } catch {
      toast({ title: 'Some resumes could not be deleted', variant: 'destructive' });
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    } finally {
      setIsDeletingAll(false);
    }
  };

  const previewPdf = async (resume: Resume) => {
    if (!resume.pdf_path) {
      toast({ title: 'PDF not available', variant: 'destructive' });
      return;
    }
    try {
      const { data } = await resumesApi.getPdfUrl(resume.id);
      window.open(data.url, '_blank', 'noopener,noreferrer');
    } catch {
      toast({ title: 'Failed to open PDF', variant: 'destructive' });
    }
  };

  const downloadPdf = async (resume: Resume) => {
    if (!resume.pdf_path) {
      toast({ title: 'PDF not available', variant: 'destructive' });
      return;
    }
    try {
      // Use the /pdf endpoint which returns a redirect to a presigned URL
      // with Content-Disposition: attachment so the browser saves the file.
      const { data } = await resumesApi.getPdfDownloadUrl(resume.id);
      const link = document.createElement('a');
      link.href = data.url;
      link.setAttribute(
        'download',
        `resume-${new Date(resume.created_at).toISOString().split('T')[0]}.pdf`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      toast({ title: 'Failed to download PDF', variant: 'destructive' });
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
      <div className="space-y-4">
        <div className="h-10 bg-muted/40 rounded-lg w-48 animate-pulse" />
        <div className="rounded-lg border divide-y">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-3 animate-pulse">
              <div className="h-8 w-8 bg-muted rounded-full shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-muted rounded w-1/3" />
                <div className="h-3 bg-muted rounded w-1/4" />
              </div>
              <div className="h-6 bg-muted rounded w-16" />
              <div className="h-8 bg-muted rounded w-24" />
            </div>
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
        <div className="flex items-center gap-2">
          {resumes && resumes.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
              onClick={deleteAll}
              disabled={isDeletingAll}
            >
              {isDeletingAll ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Delete All
            </Button>
          )}
          <Button
            onClick={() => setShowGenerator(true)}
            className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground shadow-md hover:shadow-lg transition-all"
          >
            <Sparkles className="h-4 w-4" />
            Generate Resume
          </Button>
        </div>
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
                  Generate your first resume from your GitHub projects. Import your repos first,
                  then click Generate.
                </p>
              </div>
              <Button onClick={() => setShowGenerator(true)} className="gap-2">
                <Sparkles className="h-4 w-4" />
                Generate Your First Resume
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Resume list */}
        {resumes && resumes.length > 0 && (
          <div className="rounded-lg border divide-y overflow-hidden">
            {resumes.map((resume) => {
              const status = statusConfig[resume.status] || statusConfig.draft;
              const StatusIcon = status.icon;
              const isProcessing = resume.status === 'generating' || resume.status === 'compiling';

              return (
                <div
                  key={resume.id}
                  className="group flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors"
                >
                  {/* Icon */}
                  <div className="shrink-0 h-8 w-8 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
                    <FileText className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                  </div>

                  {/* Name + date */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{resume.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(resume.updated_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                    {resume.error_message && (
                      <p className="text-xs text-red-500 truncate mt-0.5">{resume.error_message}</p>
                    )}
                  </div>

                  {/* Status badge */}
                  <Badge
                    variant="secondary"
                    className={`shrink-0 text-xs font-medium gap-1 ${status.color}`}
                  >
                    <StatusIcon className={`h-3 w-3 ${isProcessing ? 'animate-spin' : ''}`} />
                    {status.text}
                  </Badge>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {(resume.status === 'compiled' || resume.status === 'generated') &&
                      resume.pdf_path && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1 h-7 text-xs"
                            onClick={() => previewPdf(resume)}
                          >
                            <Eye className="h-3 w-3" />
                            Preview
                          </Button>
                          <Button
                            size="sm"
                            className="gap-1 h-7 text-xs"
                            onClick={() => downloadPdf(resume)}
                          >
                            <Download className="h-3 w-3" />
                            PDF
                          </Button>
                          {resume.tex_s3_key && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="gap-1 h-7 text-xs"
                              onClick={() =>
                                downloadTex(
                                  resume.id,
                                  `resume-${new Date(resume.created_at).toISOString().split('T')[0]}.tex`
                                )
                              }
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
                    {(resume.latex_content ||
                      ['generated', 'compiled', 'error'].includes(resume.status)) && (
                      <Link href={`/dashboard/resumes/${resume.id}/edit`}>
                        <Button
                          size="sm"
                          variant={resume.status === 'compiled' ? 'default' : 'outline'}
                          className={`gap-1 h-7 text-xs ${resume.status === 'compiled' ? 'bg-primary hover:bg-primary/90 text-primary-foreground' : ''}`}
                        >
                          <Edit className="h-3 w-3" />
                          {resume.status === 'compiled' ? 'Open in Editor' : 'Edit'}
                        </Button>
                      </Link>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => {
                        if (confirm('Delete this resume?')) {
                          deleteMutation.mutate(resume.id);
                        }
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

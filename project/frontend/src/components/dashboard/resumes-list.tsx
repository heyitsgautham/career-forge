'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { resumesApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FileText, Trash2, Loader2, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { ResumeGenerator } from './resumes/resume-generator';
import { ResumeRow } from './resumes/resume-row';
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
    onError: (error: unknown) => {
      toast({
        title: 'Failed to delete resume',
        description: apiErrorDetail(error, 'Please try again.'),
        variant: 'destructive',
      });
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
            {resumes.map((resume) => (
              <ResumeRow
                key={resume.id}
                resume={resume}
                onDelete={() => deleteMutation.mutate(resume.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

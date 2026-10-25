'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi, githubApi } from '@/lib/api';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Github, Plus } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { ProjectDetailsModal } from './projects/project-details-modal';
import { AddProjectModal } from './projects/add-project-modal';
import { GithubImportModal } from './projects/github-import-modal';
import { ImportSkeletonCard, ImportProgressBanner } from './projects/import-progress';
import type { Project, SyncSummary } from './projects/types';
import { SyncBanner } from './projects/sync-banner';
import { ProjectCard } from './projects/project-card';
import { apiErrorDetail } from '@/lib/api-error';

export function ProjectsList() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [mounted, setMounted] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  useEffect(() => setMounted(true), []);

  // ── GitHub bulk-ingestion state ─────────────────────────────────────────
  const [syncing, setSyncing] = useState(false); // "Sync All Repos"
  const busy = syncing;
  const [syncStatus, setSyncStatus] = useState<string>('none');
  const [syncSummary, setSyncSummary] = useState<SyncSummary | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const res = await githubApi.getIngestStatus();
      const s = res.data.status as string;
      const summary = res.data.summary;
      setSyncStatus(s);
      setSyncSummary(summary);
      if (s === 'done' || s === 'completed') {
        stopPoll();
        setSyncing(false);
        queryClient.invalidateQueries({ queryKey: ['projects'] });
        const count = summary?.processed ?? 0;
        toast({
          title: 'Sync complete',
          description: `${count} existing project${count !== 1 ? 's' : ''} refreshed.`,
        });
      } else if (s === 'failed') {
        stopPoll();
        setSyncing(false);
        toast({
          title: 'Sync failed',
          description: 'Check your GitHub connection and try again.',
          variant: 'destructive',
        });
      }
    } catch {
      stopPoll();
      setSyncing(false);
    }
  }, [stopPoll, queryClient, toast]);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await githubApi.sync(false);
    } catch {
      /* server already processing */
    }
    pollRef.current = setInterval(pollStatus, 3000);
    pollStatus();
  };

  // ───────────────────────────────────────────────────────────────────────

  const {
    data: projects,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await projectsApi.list();
      return res.data as Project[];
    },
    staleTime: 5 * 60 * 1000, // 5 min
    gcTime: 30 * 60 * 1000, // 30 min
  });

  // Fetch GitHub repos count for the badge
  const { data: githubReposCount } = useQuery({
    queryKey: ['github-repos-count'],
    queryFn: async () => {
      try {
        const res = await projectsApi.listGithubUserRepos();
        return (res.data as any[]).length;
      } catch {
        return 0;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 min
    gcTime: 30 * 60 * 1000, // 30 min
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onMutate: async (id: string) => {
      // Cancel any in-flight refetches so they don't overwrite the optimistic update
      await queryClient.cancelQueries({ queryKey: ['projects'] });
      // Snapshot so we can roll back on error
      const previous = queryClient.getQueryData(['projects']);
      // Optimistically remove from cache immediately
      queryClient.setQueryData(['projects'], (old: unknown) => {
        if (!Array.isArray(old)) return old;
        return old.filter((p: { id: string }) => p.id !== id);
      });
      return { previous };
    },
    onError: (_err, _id, context) => {
      // Roll back to snapshot
      if (context?.previous !== undefined) {
        queryClient.setQueryData(['projects'], context.previous);
      }
      toast({ title: 'Failed to delete project', variant: 'destructive' });
    },
    onSettled: () => {
      // Sync with server once the mutation resolves either way
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const deleteAllMutation = useMutation({
    mutationFn: () => projectsApi.deleteAll(),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['projects'] });
      const previous = queryClient.getQueryData(['projects']);
      queryClient.setQueryData(['projects'], []);
      return { previous };
    },
    onSuccess: (response) => {
      toast({
        title: 'All projects cleared',
        description: response.data?.message || 'Projects deleted.',
      });
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(['projects'], context.previous);
      }
      toast({ title: 'Failed to clear projects', variant: 'destructive' });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [importProgress, setImportProgress] = useState<
    Array<{ name: string; fullName: string; status: 'queued' | 'processing' | 'done' | 'failed' }>
  >([]);
  // Holds the visual simulation interval so it can be cancelled when real results arrive
  const simulationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Import mutation (lifted to parent so loading overlay survives modal close) ──
  const importMutation = useMutation({
    mutationFn: (fullNames: string[]) => projectsApi.importGithub(fullNames),
    onMutate: () => {
      // importProgress already set before calling mutate
    },
    onSuccess: (response) => {
      // Stop simulation — real results drive the state from here
      if (simulationIntervalRef.current) {
        clearInterval(simulationIntervalRef.current);
        simulationIntervalRef.current = null;
      }

      queryClient.invalidateQueries({ queryKey: ['projects'] });
      const results: Array<{ full_name?: string; status?: string; error?: string }> =
        response.data?.results ?? [];

      // Reveal done/failed one by one — 650ms stagger so cards appear sequentially
      results.forEach((result, idx) => {
        setTimeout(() => {
          setImportProgress((prev) =>
            prev.map((repo) => {
              if (
                repo.fullName === result.full_name ||
                (!result.full_name &&
                  idx ===
                    prev.indexOf(prev.find((r) => r.status !== 'done' && r.status !== 'failed')!))
              ) {
                return { ...repo, status: result.status === 'success' ? 'done' : 'failed' };
              }
              return repo;
            })
          );
        }, idx * 650);
      });

      const allDoneDelay = results.length * 650;

      // Toast after the last card flips
      setTimeout(() => {
        const failed = results.filter((r) => r.status === 'error');
        const succeeded = results.filter((r) => r.status === 'success');
        if (succeeded.length > 0 && failed.length === 0) {
          toast({
            title: `${succeeded.length} project${succeeded.length !== 1 ? 's' : ''} imported successfully`,
          });
        } else if (succeeded.length > 0 && failed.length > 0) {
          toast({
            title: `${succeeded.length} imported, ${failed.length} failed`,
            description: `Failed: ${failed.map((f) => f.full_name).join(', ')}`,
          });
        } else if (failed.length > 0) {
          toast({
            title: `Import failed for ${failed.length} project${failed.length !== 1 ? 's' : ''}`,
            description: failed[0].error ?? 'Unknown error',
            variant: 'destructive',
          });
        } else {
          toast({ title: 'Import completed' });
        }
      }, allDoneDelay);

      // Clear skeleton cards after real cards have had time to load via polling
      setTimeout(() => setImportProgress([]), allDoneDelay + 3500);

      // A5: Poll for 30s to catch delayed DB writes
      const pollId = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ['projects'] });
      }, 5000);
      setTimeout(() => clearInterval(pollId), 30_000);
    },
    onError: (error: unknown) => {
      if (simulationIntervalRef.current) {
        clearInterval(simulationIntervalRef.current);
        simulationIntervalRef.current = null;
      }
      // Mark all as failed, then clear after a short delay
      setImportProgress((prev) => prev.map((repo) => ({ ...repo, status: 'failed' })));
      toast({
        title: 'Failed to import repositories',
        description: apiErrorDetail(
          error,
          error instanceof Error && error.message ? error.message : 'Unknown error'
        ),
        variant: 'destructive',
      });
      setTimeout(() => setImportProgress([]), 4000);
    },
    onSettled: () => {
      // cleanup handled per-path in onSuccess / onError
    },
  });

  const handleStartImport = (fullNames: string[]) => {
    // Initialize — first repo immediately processing, rest queued
    const progressItems = fullNames.map((fn, idx) => ({
      name: fn.split('/').pop() || fn,
      fullName: fn,
      status: (idx === 0 ? 'processing' : 'queued') as 'queued' | 'processing' | 'done' | 'failed',
    }));
    setImportProgress(progressItems);
    setShowGithubModal(false);
    importMutation.mutate(fullNames);

    // Advance the "processing" indicator along the queue while waiting for the API
    if (fullNames.length > 1) {
      let currentIdx = 1;
      simulationIntervalRef.current = setInterval(() => {
        if (currentIdx < fullNames.length) {
          setImportProgress((prev) =>
            prev.map((item, i) => {
              if (i < currentIdx)
                return item.status === 'queued' ? { ...item, status: 'processing' as const } : item;
              if (i === currentIdx) return { ...item, status: 'processing' as const };
              return item;
            })
          );
          currentIdx++;
        } else {
          if (simulationIntervalRef.current) {
            clearInterval(simulationIntervalRef.current);
            simulationIntervalRef.current = null;
          }
        }
      }, 3000);
    }
  };

  // ── GitHub sync banner (always visible at top) ────────────────────────
  const syncBanner = (
    <SyncBanner
      syncing={syncing}
      syncStatus={syncStatus}
      syncSummary={syncSummary}
      onSyncAll={handleSyncAll}
      showClearAll={Boolean(mounted && projects && projects.length > 0)}
      clearing={deleteAllMutation.isPending}
      onClearAll={() => setShowClearConfirm(true)}
    />
  );

  // ── Non-blocking import progress banner ─────────────────────────────────
  const importBanner =
    importProgress.length > 0 ? <ImportProgressBanner importProgress={importProgress} /> : null;
  // ───────────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <>
        {syncBanner}
        {importBanner}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-6 bg-muted rounded w-3/4"></div>
                <div className="h-4 bg-muted rounded w-full mt-2"></div>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <div className="h-5 bg-muted rounded w-16"></div>
                  <div className="h-5 bg-muted rounded w-16"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </>
    );
  }

  // If an import is actively running, skip the empty state and fall through to the grid
  // so skeleton cards are visible even before the first real project lands.
  if ((!projects || projects.length === 0) && importProgress.length === 0) {
    return (
      <>
        {syncBanner}
        {importBanner}
        <Card className="text-center py-12">
          <CardContent>
            <Github className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
            <p className="text-muted-foreground mb-4">
              Sync your GitHub repos above, or import/add projects below.
            </p>
            <div className="flex gap-2 justify-center">
              <Button variant="outline" className="gap-2" onClick={() => setShowGithubModal(true)}>
                <Github className="h-4 w-4" />
                Import from GitHub
                {githubReposCount !== undefined && githubReposCount > 0 && (
                  <Badge variant="secondary" className="ml-1 bg-primary/10 text-primary">
                    {githubReposCount}
                  </Badge>
                )}
              </Button>
              <Button onClick={() => setShowAddModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Manually
              </Button>
            </div>
          </CardContent>
        </Card>

        {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} />}
        {showGithubModal && (
          <GithubImportModal
            onClose={() => setShowGithubModal(false)}
            onStartImport={handleStartImport}
            importedRepoNames={new Set((projects ?? []).map((p) => p.title))}
            projectsLoading={isLoading}
          />
        )}
      </>
    );
  }

  return (
    <>
      {syncBanner}
      {importBanner}
      <div className="flex justify-end gap-2 mb-4">
        <Button
          variant="outline"
          className="gap-2 border-primary/30 hover:bg-primary/5"
          onClick={() => setShowGithubModal(true)}
        >
          <Github className="h-4 w-4" />
          Import from GitHub
          {githubReposCount !== undefined && githubReposCount > 0 && (
            <Badge variant="secondary" className="ml-1 bg-primary/10 text-primary">
              {githubReposCount}
            </Badge>
          )}
        </Button>
        <Button
          onClick={() => setShowAddModal(true)}
          className="shadow-md shadow-primary/20 hover:shadow-lg"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Project
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Skeleton placeholder cards for in-flight imports */}
        {importProgress.map((item) => (
          <ImportSkeletonCard key={`skeleton-${item.fullName}`} item={item} />
        ))}
        {/* Real project cards */}
        {(projects ?? []).map((project) => (
          <ProjectCard
            key={project.id}
            project={project}
            onShowDetails={() => setSelectedProject(project)}
            onDelete={() => deleteMutation.mutate(project.id)}
          />
        ))}
      </div>

      {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} />}
      {showGithubModal && (
        <GithubImportModal
          onClose={() => setShowGithubModal(false)}
          onStartImport={handleStartImport}
          importedRepoNames={new Set((projects ?? []).map((p) => p.title))}
          projectsLoading={isLoading}
        />
      )}
      {selectedProject && (
        <ProjectDetailsModal project={selectedProject} onClose={() => setSelectedProject(null)} />
      )}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-sm">
            <h2 className="text-lg font-bold mb-2">Clear All Projects?</h2>
            <p className="text-sm text-muted-foreground mb-4">
              This will permanently delete all {projects?.length ?? 0} projects. You can re-import
              specific ones afterwards using &quot;Import from GitHub&quot;.
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowClearConfirm(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  deleteAllMutation.mutate();
                  setShowClearConfirm(false);
                }}
              >
                Yes, Clear All
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi, githubApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Github, ExternalLink, RefreshCw, Trash2, Calendar, Plus, X, Code2, Sparkles, GitBranch, FileCode, Lock, Globe } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface Project {
  id: string;
  title: string;
  description: string;
  technologies: string[];
  url?: string;
  highlights: string[];
  is_private?: boolean;
  source_type?: string;
  start_date?: string;
  end_date?: string;
  created_at: string;
}

export function ProjectsList() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // ── GitHub bulk-ingestion state ─────────────────────────────────────────
  const [syncing, setSyncing] = useState(false);      // "Sync All Repos"
  const busy = syncing;
  const [syncStatus, setSyncStatus] = useState<string>('none');
  const [syncSummary, setSyncSummary] = useState<{ processed: number; failed: number; mode?: string; lastRunAt?: string } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const res = await githubApi.getIngestStatus();
      const s = res.data.status as string;
      const summary = res.data.summary;
      setSyncStatus(s);
      setSyncSummary(summary);
      if (s === 'done' || s === 'completed') {
        stopPoll(); setSyncing(false);
        queryClient.invalidateQueries({ queryKey: ['projects'] });
        const count = summary?.processed ?? 0;
        toast({
          title: 'Sync complete',
          description: `${count} existing project${count !== 1 ? 's' : ''} refreshed.`,
        });
      } else if (s === 'failed') {
        stopPoll(); setSyncing(false);
        toast({ title: 'Sync failed', description: 'Check your GitHub connection and try again.', variant: 'destructive' });
      }
    } catch { stopPoll(); setSyncing(false); }
  }, [stopPoll, queryClient, toast]);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await githubApi.sync(false);
    } catch { /* server already processing */ }
    pollRef.current = setInterval(pollStatus, 3000);
    pollStatus();
  };

  // ───────────────────────────────────────────────────────────────────────

  const { data: projects, isLoading, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await projectsApi.list();
      return res.data as Project[];
    },
    staleTime: 5 * 60 * 1000,   // 5 min
    gcTime: 30 * 60 * 1000,     // 30 min
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
    staleTime: 5 * 60 * 1000,   // 5 min
    gcTime: 30 * 60 * 1000,     // 30 min
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
      toast({ title: 'All projects cleared', description: response.data?.message || 'Projects deleted.' });
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
  const [importProgress, setImportProgress] = useState<Array<{ name: string; fullName: string; status: 'queued' | 'processing' | 'done' | 'failed' }>>([]);
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
      const results: Array<{ full_name?: string; status?: string; error?: string }> = response.data?.results ?? [];

      // Reveal done/failed one by one — 650ms stagger so cards appear sequentially
      results.forEach((result, idx) => {
        setTimeout(() => {
          setImportProgress(prev => prev.map(repo => {
            if (repo.fullName === result.full_name || (!result.full_name && idx === prev.indexOf(prev.find(r => r.status !== 'done' && r.status !== 'failed')!))) {
              return { ...repo, status: result.status === 'success' ? 'done' : 'failed' };
            }
            return repo;
          }));
        }, idx * 650);
      });

      const allDoneDelay = results.length * 650;

      // Toast after the last card flips
      setTimeout(() => {
        const failed = results.filter(r => r.status === 'error');
        const succeeded = results.filter(r => r.status === 'success');
        if (succeeded.length > 0 && failed.length === 0) {
          toast({ title: `${succeeded.length} project${succeeded.length !== 1 ? 's' : ''} imported successfully` });
        } else if (succeeded.length > 0 && failed.length > 0) {
          toast({ title: `${succeeded.length} imported, ${failed.length} failed`, description: `Failed: ${failed.map(f => f.full_name).join(', ')}` });
        } else if (failed.length > 0) {
          toast({ title: `Import failed for ${failed.length} project${failed.length !== 1 ? 's' : ''}`, description: failed[0].error ?? 'Unknown error', variant: 'destructive' });
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
    onError: (error: any) => {
      if (simulationIntervalRef.current) {
        clearInterval(simulationIntervalRef.current);
        simulationIntervalRef.current = null;
      }
      // Mark all as failed, then clear after a short delay
      setImportProgress(prev => prev.map(repo => ({ ...repo, status: 'failed' })));
      toast({ title: 'Failed to import repositories', description: error.response?.data?.detail || error.message || 'Unknown error', variant: 'destructive' });
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
          setImportProgress(prev => prev.map((item, i) => {
            if (i < currentIdx) return item.status === 'queued' ? { ...item, status: 'processing' as const } : item;
            if (i === currentIdx) return { ...item, status: 'processing' as const };
            return item;
          }));
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
    <Card className="mb-4 border-l-4 border-l-primary bg-card">
      <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <Github className="h-5 w-5 text-primary" />
            <span className="text-base font-semibold leading-none tracking-tight">GitHub Sync</span>
            {syncStatus === 'done' || syncStatus === 'completed' ? (
              <Badge className="bg-[hsl(var(--success))]/10 text-[hsl(var(--success))] border-0">
                {syncSummary ? `${syncSummary.processed} imported` : 'Synced'}
              </Badge>
            ) : syncStatus === 'in_progress' || syncStatus === 'pending' ? (
              <Badge className="bg-primary/10 text-primary border-0 animate-pulse">
                {syncStatus === 'pending' ? 'Pending…' : 'Importing…'}
              </Badge>
            ) : syncStatus === 'failed' ? (
              <Badge variant="destructive">Failed</Badge>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleSyncAll}
              disabled={busy}
              variant="outline"
              className="gap-2 border-primary/40 text-primary hover:bg-primary/5"
            >
              {syncing ? (
                <><RefreshCw className="h-4 w-4 animate-spin" />Syncing…</>
              ) : (
                <><RefreshCw className="h-4 w-4" />Sync Existing</>
              )}
            </Button>
            {projects && projects.length > 0 && (
              <Button
                size="sm"
                variant="outline"
                className="gap-2 border-destructive/40 text-destructive hover:bg-destructive/5"
                onClick={() => setShowClearConfirm(true)}
                disabled={deleteAllMutation.isPending}
              >
                <Trash2 className="h-4 w-4" />
                {deleteAllMutation.isPending ? 'Clearing…' : 'Clear All'}
              </Button>
            )}
          </div>
        </div>
      {(syncStatus === 'in_progress' || syncStatus === 'pending') && (
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground animate-pulse">
            Refreshing existing projects via Bedrock — this takes ~1–2 min for large accounts.
          </p>
        </CardContent>
      )}
      {syncStatus === 'done' && syncSummary?.lastRunAt && (
        <CardContent className="pt-0">
          <p className="text-xs text-muted-foreground">
            Last synced {new Date(syncSummary.lastRunAt).toLocaleString()}
            {syncSummary.failed > 0 && ` · ${syncSummary.failed} failed`}
          </p>
        </CardContent>
      )}
    </Card>
  );

  // ── Non-blocking import progress banner ─────────────────────────────────
  const importBanner = importProgress.length > 0 ? (
    <ImportProgressBanner importProgress={importProgress} />
  ) : null;
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
        {showGithubModal && <GithubImportModal onClose={() => setShowGithubModal(false)} onStartImport={handleStartImport} importedRepoNames={new Set((projects ?? []).map(p => p.title))} projectsLoading={isLoading} />}
      </>
    );
  }

  return (
    <>
      {syncBanner}
      {importBanner}
      <div className="flex justify-end gap-2 mb-4">
        <Button variant="outline" className="gap-2 border-primary/30 hover:bg-primary/5" onClick={() => setShowGithubModal(true)}>
          <Github className="h-4 w-4" />
          Import from GitHub
          {githubReposCount !== undefined && githubReposCount > 0 && (
            <Badge variant="secondary" className="ml-1 bg-primary/10 text-primary">
              {githubReposCount}
            </Badge>
          )}
        </Button>
        <Button onClick={() => setShowAddModal(true)} className="shadow-md shadow-primary/20 hover:shadow-lg">
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
          <Card key={project.id} className="hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-4 border-l-[hsl(var(--success))]">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 min-w-0">
                  <CardTitle className="text-lg truncate">{project.title}</CardTitle>
                  {project.source_type === 'github' && (
                    project.is_private ? (
                      <span title="Private repository" className="flex-shrink-0">
                        <Lock className="h-3.5 w-3.5 text-amber-500" />
                      </span>
                    ) : (
                      <span title="Public repository" className="flex-shrink-0">
                        <Globe className="h-3.5 w-3.5 text-green-500" />
                      </span>
                    )
                  )}
                </div>
                <div className="flex gap-1">
                  {project.url && (
                    <Button variant="ghost" size="icon" asChild>
                      <a href={project.url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
              <CardDescription className="line-clamp-2">
                {project.description}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1 mb-4">
                {project.technologies?.slice(0, 5).map((tech, idx) => (
                  <Badge key={tech} variant="secondary" className={`text-xs ${idx % 3 === 0 ? 'bg-primary/10 text-primary' :
                    idx % 3 === 1 ? 'bg-[hsl(var(--accent))]/10 text-[hsl(var(--accent))]' :
                      'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]'
                    }`}>
                    {tech}
                  </Badge>
                ))}
                {project.technologies?.length > 5 && (
                  <Badge variant="outline" className="text-xs">
                    +{project.technologies.length - 5}
                  </Badge>
                )}
              </div>
              {project.start_date && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  {project.start_date} - {project.end_date || 'Present'}
                </div>
              )}
              <div className="flex justify-between gap-2 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedProject(project)}
                >
                  Show Details
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive"
                  onClick={() => deleteMutation.mutate(project.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} />}
      {showGithubModal && <GithubImportModal onClose={() => setShowGithubModal(false)} onStartImport={handleStartImport} importedRepoNames={new Set((projects ?? []).map(p => p.title))} projectsLoading={isLoading} />}
      {selectedProject && <ProjectDetailsModal project={selectedProject} onClose={() => setSelectedProject(null)} />}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-sm">
            <h2 className="text-lg font-bold mb-2">Clear All Projects?</h2>
            <p className="text-sm text-muted-foreground mb-4">
              This will permanently delete all {projects?.length ?? 0} projects. You can re-import specific ones afterwards using "Import from GitHub".
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowClearConfirm(false)}>Cancel</Button>
              <Button
                variant="destructive"
                onClick={() => { deleteAllMutation.mutate(); setShowClearConfirm(false); }}
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

function ProjectDetailsModal({ project, onClose }: { project: Project; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-fade-in-up">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{project.title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          {/* Description */}
          <div>
            <h3 className="font-semibold text-sm text-muted-foreground mb-1">Description</h3>
            <p className="text-sm">{project.description}</p>
          </div>

          {/* Technologies */}
          {project.technologies && project.technologies.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Technologies</h3>
              <div className="flex flex-wrap gap-2">
                {project.technologies.map((tech) => (
                  <Badge key={tech} variant="secondary">
                    {tech}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Highlights */}
          {project.highlights && project.highlights.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Key Highlights</h3>
              <ul className="list-disc list-inside space-y-1">
                {project.highlights.map((highlight, idx) => (
                  <li key={idx} className="text-sm">{highlight}</li>
                ))}
              </ul>
            </div>
          )}

          {/* URL */}
          {project.url && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-1">Project URL</h3>
              <a
                href={project.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                {project.url}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}

          {/* Dates */}
          {project.start_date && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-1">Timeline</h3>
              <p className="text-sm">
                {project.start_date} - {project.end_date || 'Present'}
              </p>
            </div>
          )}

          <div className="flex justify-end pt-4">
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AddProjectModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [technologies, setTechnologies] = useState('');
  const [highlights, setHighlights] = useState('');
  const [url, setUrl] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () => projectsApi.create({
      title,
      description,
      technologies: technologies.split(',').map(t => t.trim()).filter(Boolean),
      highlights: highlights.split('\n').map(h => h.trim()).filter(Boolean),
      url: url || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast({ title: 'Project created successfully' });
      onClose();
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to create project',
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive'
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-md max-h-[90vh] overflow-y-auto animate-fade-in-up">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Add Project</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="title">Project Title *</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My Awesome Project"
            />
          </div>

          <div>
            <Label htmlFor="description">Description *</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this project do?"
              rows={3}
            />
          </div>

          <div>
            <Label htmlFor="technologies">Technologies (comma-separated)</Label>
            <Input
              id="technologies"
              value={technologies}
              onChange={(e) => setTechnologies(e.target.value)}
              placeholder="Python, FastAPI, React"
            />
          </div>

          <div>
            <Label htmlFor="highlights">Key Highlights (optional - auto-generated if empty)</Label>
            <Textarea
              id="highlights"
              value={highlights}
              onChange={(e) => setHighlights(e.target.value)}
              placeholder="Leave empty to auto-generate 3 technical highlights using AI"
              rows={3}
            />
            <p className="text-xs text-muted-foreground mt-1">
              💡 Leave empty and we'll generate 3 technical bullet points automatically
            </p>
          </div>

          <div>
            <Label htmlFor="url">Project URL (optional)</Label>
            <Input
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/..."
            />
          </div>

          <div className="flex gap-2 justify-end pt-4">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!title || !description || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating…' : 'Create Project'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function GithubImportModal({ 
  onClose, 
  onStartImport, 
  importedRepoNames,
  projectsLoading = false,
}: { 
  onClose: () => void; 
  onStartImport: (fullNames: string[]) => void; 
  importedRepoNames: Set<string>;
  projectsLoading?: boolean;
}) {
  const [repoUrl, setRepoUrl] = useState('');
  const [selectedRepos, setSelectedRepos] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [importMode, setImportMode] = useState<'select' | 'url'>('select');
  const [visibilityFilter, setVisibilityFilter] = useState<'all' | 'public' | 'private'>('all');

  // Fetch user's GitHub repositories
  const { data: userRepos, isLoading: loadingRepos, error: reposError } = useQuery({
    queryKey: ['github-user-repos'],
    queryFn: async () => {
      const res = await projectsApi.listGithubUserRepos();
      return res.data as Array<{
        full_name: string;
        name: string;
        description?: string;
        html_url: string;
        stars: number;
        forks: number;
        language?: string;
        is_private: boolean;
        is_fork: boolean;
      }>;
    },
    retry: false,
    staleTime: 5 * 60 * 1000,   // 5 min
    gcTime: 30 * 60 * 1000,     // 30 min
  });

  // Filter repos based on search query and visibility
  const filteredRepos = userRepos?.filter(repo => {
    // Apply visibility filter first
    if (visibilityFilter === 'public' && repo.is_private) return false;
    if (visibilityFilter === 'private' && !repo.is_private) return false;
    
    // Then apply search query
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      repo.full_name.toLowerCase().includes(query) ||
      repo.name.toLowerCase().includes(query) ||
      repo.description?.toLowerCase().includes(query) ||
      repo.language?.toLowerCase().includes(query)
    );
  });

  // Compute visibility counts from full userRepos list
  const publicCount = userRepos?.filter(r => !r.is_private).length ?? 0;
  const privateCount = userRepos?.filter(r => r.is_private).length ?? 0;

  const isAlreadyImported = (repo: { name: string }) => importedRepoNames.has(repo.name);

  const toggleRepo = (fullName: string) => {
    setSelectedRepos(prev => {
      const next = new Set(prev);
      if (next.has(fullName)) {
        next.delete(fullName);
      } else {
        next.add(fullName);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (!filteredRepos) return;
    const selectableRepos = filteredRepos.filter(r => !isAlreadyImported(r));
    const allFilteredSelected = selectableRepos.every(r => selectedRepos.has(r.full_name));
    if (allFilteredSelected) {
      setSelectedRepos(prev => {
        const next = new Set(prev);
        selectableRepos.forEach(r => next.delete(r.full_name));
        return next;
      });
    } else {
      setSelectedRepos(prev => {
        const next = new Set(prev);
        selectableRepos.forEach(r => next.add(r.full_name));
        return next;
      });
    }
  };

  const handleImport = () => {
    if (importMode === 'select') {
      if (selectedRepos.size === 0) return;
      onStartImport(Array.from(selectedRepos));
    } else {
      const match = repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
      if (!match) return;
      const fullName = `${match[1]}/${match[2].replace('.git', '')}`;
      onStartImport([fullName]);
    }
  };

  const selectableFilteredRepos = filteredRepos?.filter(r => !isAlreadyImported(r));
  const allFilteredSelected = selectableFilteredRepos && selectableFilteredRepos.length > 0 && selectableFilteredRepos.every(r => selectedRepos.has(r.full_name));

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-fade-in-up">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Import from GitHub</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          {/* Import Mode Tabs */}
          <div className="flex gap-2 mb-4">
            <Button
              variant={importMode === 'select' ? 'default' : 'outline'}
              onClick={() => setImportMode('select')}
              className="flex-1"
            >
              Select from Your Repos
            </Button>
            <Button
              variant={importMode === 'url' ? 'default' : 'outline'}
              onClick={() => setImportMode('url')}
              className="flex-1"
            >
              Import by URL
            </Button>
          </div>

          {importMode === 'select' ? (
            <>
              {loadingRepos ? (
                <div className="text-center py-8">
                  <RefreshCw className="h-8 w-8 mx-auto animate-spin text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">Loading your repositories...</p>
                </div>
              ) : reposError ? (
                <div className="text-center py-8">
                  <Github className="h-12 w-12 mx-auto text-red-500 mb-2" />
                  <p className="text-sm font-semibold text-red-600 dark:text-red-400 mb-1">
                    Failed to load repositories
                  </p>
                  <p className="text-xs text-muted-foreground mb-3">
                    {(reposError as any)?.response?.data?.detail || 'No GitHub account connected or connection expired'}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setImportMode('url')}
                  >
                    Switch to URL Import
                  </Button>
                </div>
              ) : userRepos && userRepos.length > 0 ? (
                <>
                  <div>
                    <Label htmlFor="repoSearch">Search Repositories</Label>
                    <Input
                      id="repoSearch"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search by name, description, or language..."
                      className="mt-1"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {filteredRepos?.length} of {userRepos.length} repositories
                      {selectedRepos.size > 0 && (
                        <span className="ml-2 font-medium text-violet-600 dark:text-violet-400">
                          · {selectedRepos.size} selected
                        </span>
                      )}
                    </p>
                  </div>

                  {/* Visibility Filter Toggle */}
                  <div className="flex gap-1">
                    <Button
                      variant={visibilityFilter === 'all' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setVisibilityFilter('all')}
                      className="text-xs h-8"
                    >
                      All ({userRepos.length})
                    </Button>
                    <Button
                      variant={visibilityFilter === 'public' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setVisibilityFilter('public')}
                      className="text-xs h-8 gap-1"
                    >
                      <Globe className="h-3 w-3" />
                      Public ({publicCount})
                    </Button>
                    <Button
                      variant={visibilityFilter === 'private' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setVisibilityFilter('private')}
                      className="text-xs h-8 gap-1"
                    >
                      <Lock className="h-3 w-3" />
                      Private ({privateCount})
                    </Button>
                  </div>

                  {/* Projects loading warning banner (A2) */}
                  {projectsLoading && (
                    <div className="flex items-center gap-2 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                      <RefreshCw className="h-3 w-3 animate-spin" />
                      Loading your imported projects…
                    </div>
                  )}

                  {/* Select All / Deselect All */}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={toggleAll}
                      className="text-xs"
                    >
                      {allFilteredSelected ? 'Deselect All' : 'Select All'}
                    </Button>
                    {selectedRepos.size > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedRepos(new Set())}
                        className="text-xs text-muted-foreground"
                      >
                        Clear Selection
                      </Button>
                    )}
                  </div>

                  {/* Repo List with Checkboxes */}
                  <div className="border rounded-lg max-h-72 overflow-y-auto divide-y">
                    {filteredRepos?.map((repo) => {
                      const imported = isAlreadyImported(repo);
                      const isSelected = !imported && selectedRepos.has(repo.full_name);
                      return (
                        <label
                          key={repo.full_name}
                          className={`flex items-start gap-3 px-3 py-2.5 transition-colors ${
                            imported
                              ? 'opacity-50 cursor-not-allowed bg-muted/30'
                              : isSelected
                                ? 'bg-primary/5 cursor-pointer hover:bg-muted/50'
                                : 'cursor-pointer hover:bg-muted/50'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => !imported && toggleRepo(repo.full_name)}
                            disabled={imported}
                            className="mt-1 h-4 w-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500 disabled:opacity-50"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm truncate">{repo.full_name}</span>
                              {imported && <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]">Imported</Badge>}
                              {repo.is_private && <Badge variant="outline" className="text-[10px] px-1 py-0">Private</Badge>}
                              {repo.is_fork && <Badge variant="outline" className="text-[10px] px-1 py-0">Fork</Badge>}
                            </div>
                            {repo.description && (
                              <p className="text-xs text-muted-foreground mt-0.5 truncate">{repo.description}</p>
                            )}
                            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                              {repo.language && <span>{repo.language}</span>}
                              <span>⭐ {repo.stars}</span>
                              <span>🍴 {repo.forks}</span>
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>

                  <p className="text-sm text-muted-foreground">
                    💡 Select one or more repositories to import. We'll analyze each to extract project details via AI.
                  </p>
                </>
              ) : (
                <div className="text-center py-8">
                  <Github className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No repositories found. Make sure your GitHub account is connected.
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              <div>
                <Label htmlFor="repoUrl">GitHub Repository URL</Label>
                <Input
                  id="repoUrl"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/username/repository"
                />
              </div>

              <p className="text-sm text-muted-foreground">
                Enter any GitHub repository URL to import it as a project.
              </p>
            </>
          )}

          <div className="flex gap-2 justify-end pt-4">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              onClick={handleImport}
              disabled={
                (importMode === 'url' && !repoUrl) ||
                (importMode === 'select' && selectedRepos.size === 0)
              }
            >
              {importMode === 'select' && selectedRepos.size > 1
                ? `Import ${selectedRepos.size} Repositories`
                : 'Import Repository'
              }
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Compact non-blocking import progress banner (A4) ─────────────────────
type ImportProgressItem = { name: string; fullName: string; status: 'queued' | 'processing' | 'done' | 'failed' };

// ── Skeleton card shown in the grid while a repo is being imported ────────
function ImportSkeletonCard({ item }: { item: ImportProgressItem }) {
  const isProcessing = item.status === 'processing';
  const isDone = item.status === 'done';
  const isFailed = item.status === 'failed';

  return (
    <Card
      className={`border-l-4 transition-all duration-500 ${
        isDone    ? 'border-l-[hsl(var(--success))]' :
        isFailed  ? 'border-l-destructive' :
        isProcessing ? 'border-l-destructive' :
                    'border-l-muted'
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Github className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <span className="font-medium text-sm truncate">{item.name}</span>
          </div>
          {isProcessing && <RefreshCw className="h-6 w-6 text-destructive animate-spin flex-shrink-0" />}
          {isDone && (
            <div className="h-3.5 w-3.5 rounded-full bg-[hsl(var(--success))] flex-shrink-0" />
          )}
          {isFailed && <X className="h-3.5 w-3.5 text-destructive flex-shrink-0" />}
          {item.status === 'queued' && (
            <div className="h-3.5 w-3.5 rounded-full border-2 border-muted-foreground/30 flex-shrink-0" />
          )}
        </div>
        {/* fake description lines */}
        <div className={`h-3 bg-muted rounded mt-2 ${isProcessing ? 'animate-pulse' : 'opacity-50'}`} style={{ width: '78%' }} />
        <div className={`h-3 bg-muted rounded mt-1 ${isProcessing ? 'animate-pulse' : 'opacity-50'}`} style={{ width: '52%' }} />
      </CardHeader>
      <CardContent className="pb-4">
        {/* fake tech badges */}
        <div className="flex gap-2 mb-3">
          {[64, 48, 56].map((w, i) => (
            <div
              key={i}
              className={`h-5 rounded bg-muted ${isProcessing ? 'animate-pulse' : 'opacity-50'}`}
              style={{ width: w }}
            />
          ))}
        </div>
        <p className={`text-xs font-medium ${
          isDone       ? 'text-[hsl(var(--success))]' :
          isFailed     ? 'text-destructive' :
          isProcessing ? 'text-destructive' :
                         'text-muted-foreground'
        }`}>
          {item.status === 'queued'     ? 'Waiting in queue…'    :
           item.status === 'processing' ? 'Analyzing with AI…'   :
           item.status === 'done'       ? 'Import complete ✓'    :
                                          'Import failed'}
        </p>
      </CardContent>
    </Card>
  );
}

function ImportProgressBanner({ importProgress }: { importProgress: ImportProgressItem[] }) {
  const doneCount = importProgress.filter(r => r.status === 'done').length;
  const failedCount = importProgress.filter(r => r.status === 'failed').length;
  const processingCount = importProgress.filter(r => r.status === 'processing').length;
  const queuedCount = importProgress.filter(r => r.status === 'queued').length;
  
  const allDone = doneCount + failedCount === importProgress.length;
  const currentRepo = importProgress.find(r => r.status === 'processing');

  return (
    <Card className={`mb-4 border-l-4 ${allDone ? (failedCount > 0 ? 'border-l-destructive' : 'border-l-[hsl(var(--success))]') : 'border-l-destructive'} bg-card`}>
      <CardContent className="py-3 px-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {allDone ? (
              failedCount > 0 ? (
                <div className="h-8 w-8 rounded-lg bg-destructive/10 flex items-center justify-center">
                  <X className="h-4 w-4 text-destructive" />
                </div>
              ) : (
                <div className="h-8 w-8 rounded-lg bg-[hsl(var(--success))]/10 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-[hsl(var(--success))]" />
                </div>
              )
            ) : (
              <div className="h-8 w-8 rounded-lg bg-destructive/10 flex items-center justify-center">
                <RefreshCw className="h-5 w-5 text-destructive animate-spin" />
              </div>
            )}
            <div>
              <p className="text-sm font-medium">
                {allDone 
                  ? (failedCount > 0 
                    ? `Import completed with ${failedCount} failure${failedCount !== 1 ? 's' : ''}`
                    : `Successfully imported ${doneCount} project${doneCount !== 1 ? 's' : ''}`)
                  : `Importing ${importProgress.length} repositor${importProgress.length !== 1 ? 'ies' : 'y'}…`
                }
              </p>
              <p className="text-xs text-muted-foreground">
                {allDone 
                  ? `${doneCount} succeeded${failedCount > 0 ? `, ${failedCount} failed` : ''}`
                  : currentRepo 
                    ? `Analyzing ${currentRepo.name}…`
                    : `${processingCount} processing, ${queuedCount} queued`
                }
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Progress indicators */}
            <div className="flex gap-1">
              {importProgress.map((item) => (
                <div
                  key={item.fullName}
                  className={`h-2 w-2 rounded-full transition-colors ${
                    item.status === 'done' ? 'bg-[hsl(var(--success))]' :
                    item.status === 'failed' ? 'bg-destructive' :
                    item.status === 'processing' ? 'bg-destructive animate-pulse' :
                    'bg-muted'
                  }`}
                  title={`${item.name}: ${item.status}`}
                />
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Creative import loading overlay with per-repo progress ─────────────
const LOADING_PHRASES = [
  'Cloning repository data...',
  'Scanning source files...',
  'Analyzing code architecture...',
  'Extracting tech stack...',
  'Generating AI summaries...',
  'Building project highlights...',
  'Crafting project cards...',
  'Almost there...',
];

function ImportLoadingOverlay({ importProgress }: { importProgress: ImportProgressItem[] }) {
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [visibleRepos, setVisibleRepos] = useState(0);

  useEffect(() => {
    const phraseTimer = setInterval(() => {
      setPhraseIdx(prev => (prev + 1) % LOADING_PHRASES.length);
    }, 3000);
    return () => clearInterval(phraseTimer);
  }, []);

  useEffect(() => {
    if (visibleRepos < importProgress.length) {
      const timer = setTimeout(() => setVisibleRepos(prev => prev + 1), 400);
      return () => clearTimeout(timer);
    }
  }, [visibleRepos, importProgress.length]);

  const doneCount = importProgress.filter(r => r.status === 'done').length;
  const failedCount = importProgress.filter(r => r.status === 'failed').length;
  const processingCount = importProgress.filter(r => r.status === 'processing').length;

  const getStatusInfo = (status: ImportProgressItem['status']) => {
    switch (status) {
      case 'done':
        return { text: 'Done!', color: 'text-[hsl(var(--success))]', bgColor: 'bg-[hsl(var(--success))]/10' };
      case 'failed':
        return { text: 'Failed', color: 'text-destructive', bgColor: 'bg-destructive/10' };
      case 'processing':
        return { text: 'Analyzing...', color: 'text-primary animate-pulse', bgColor: 'bg-primary/10' };
      case 'queued':
      default:
        return { text: 'Queued', color: 'text-muted-foreground', bgColor: 'bg-muted' };
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      {/* Animated orbital spinner */}
      <div className="relative w-32 h-32 mb-8">
        {/* Outer ring */}
        <div className="absolute inset-0 rounded-full border-2 border-violet-200 dark:border-violet-900" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-500 animate-spin" style={{ animationDuration: '2s' }} />
        {/* Middle ring */}
        <div className="absolute inset-3 rounded-full border-2 border-transparent border-b-purple-500 animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
        {/* Inner ring */}
        <div className="absolute inset-6 rounded-full border-2 border-transparent border-t-blue-500 animate-spin" style={{ animationDuration: '1s' }} />
        {/* Center icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 bg-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/30 animate-pulse">
            <Code2 className="h-6 w-6 text-white" />
          </div>
        </div>
      </div>

      {/* Title */}
      <h3 className="text-xl font-bold text-violet-600 mb-2">
        Importing {importProgress.length} {importProgress.length === 1 ? 'Repository' : 'Repositories'}
      </h3>

      {/* Progress summary */}
      <div className="flex gap-3 mb-4 text-xs">
        {processingCount > 0 && (
          <span className="text-primary">{processingCount} processing</span>
        )}
        {doneCount > 0 && (
          <span className="text-[hsl(var(--success))]">{doneCount} done</span>
        )}
        {failedCount > 0 && (
          <span className="text-destructive">{failedCount} failed</span>
        )}
      </div>

      {/* Animated status text */}
      <p className="text-sm text-muted-foreground mb-8 h-5 transition-opacity duration-500">
        {LOADING_PHRASES[phraseIdx]}
      </p>

      {/* Repo cards with progress status */}
      <div className="w-full max-w-lg space-y-3">
        {importProgress.slice(0, visibleRepos).map((item, idx) => {
          const statusInfo = getStatusInfo(item.status);
          return (
            <div
              key={item.fullName}
              className={`flex items-center gap-3 p-3 rounded-lg border bg-card animate-in slide-in-from-bottom-2 fade-in duration-500 ${
                item.status === 'done' ? 'border-[hsl(var(--success))]/30' :
                item.status === 'failed' ? 'border-destructive/30' :
                item.status === 'processing' ? 'border-primary/30' : ''
              }`}
              style={{ animationDelay: `${idx * 100}ms` }}
            >
              <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${statusInfo.bgColor}`}>
                {item.status === 'done' ? (
                  <Sparkles className="h-4 w-4 text-[hsl(var(--success))]" />
                ) : item.status === 'failed' ? (
                  <X className="h-4 w-4 text-destructive" />
                ) : item.status === 'processing' ? (
                  <RefreshCw className="h-4 w-4 text-primary animate-spin" />
                ) : idx % 3 === 0 ? (
                  <GitBranch className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                ) : idx % 3 === 1 ? (
                  <FileCode className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                ) : (
                  <Code2 className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{item.name}</p>
                <div className="flex gap-2 mt-1 items-center">
                  {item.status === 'processing' ? (
                    <>
                      <div className="h-2 bg-muted rounded-full overflow-hidden flex-1 max-w-[180px]">
                        <div
                          className="h-full bg-violet-600 rounded-full animate-pulse"
                          style={{ width: '100%', animationDuration: '1.5s' }}
                        />
                      </div>
                      <span className={`text-[10px] whitespace-nowrap ${statusInfo.color}`}>{statusInfo.text}</span>
                    </>
                  ) : (
                    <span className={`text-[10px] whitespace-nowrap ${statusInfo.color}`}>{statusInfo.text}</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Ghost cards for repos not yet shown */}
        {visibleRepos < importProgress.length && (
          <div className="flex items-center gap-3 p-3 rounded-lg border border-dashed bg-muted/30 animate-pulse">
            <div className="w-8 h-8 rounded-lg bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-3 bg-muted rounded w-32" />
              <div className="h-2 bg-muted rounded w-24" />
            </div>
          </div>
        )}
      </div>

      <p className="text-xs text-muted-foreground mt-6 text-center max-w-md">
        Each repository is analyzed by AI to extract technologies, highlights, and project details. This may take a moment.
      </p>
    </div>
  );
}

'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Briefcase, Loader2, Timer, TrendingUp, CalendarClock, ChevronLeft, ChevronRight, X, Linkedin, CheckCircle2 } from 'lucide-react';
import { jobMatchApi, tailorApi, resumesApi, userApi, applicationsApi, type Job, type TrackingStatuses, type Application } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { timeAgo, getUserId } from './job-scout/format';
import { useCountdown } from './job-scout/use-countdown';
import { StatCard } from './job-scout/stat-card';
import { JobRow } from './job-scout/job-row';
import { JobDetailModal } from './job-scout/job-detail-modal';
import { CATEGORIES, ROWS_PER_PAGE, KANBAN_STATUSES, SOURCES, SourceFilter } from './job-scout/constants';

export function JobScoutShell() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  // Track freshly-tailored resumes in this session (optimistic, before refetch)
  const [freshTailored, setFreshTailored] = useState<Record<string, string>>({});

  // ── Query: fetch user's resumes to derive jobId → resumeId map ────────────
  const { data: userResumes = [] } = useQuery({
    queryKey: ['resumes'],
    queryFn: async () => (await resumesApi.list()).data as Array<{ id: string; job_id?: string; type?: string }>,
    staleTime: 2 * 60_000,
  });

  // Derive the tailored resumes map from real data + any freshly-generated ones
  const tailoredResumes = useMemo(() => {
    const map: Record<string, string> = {};
    const existingResumeIds = new Set(userResumes.map((r) => r.id));
    for (const r of userResumes) {
      if (r.type === 'tailored' && r.job_id) {
        map[r.job_id] = r.id;
      }
    }
    // Merge in freshly-tailored entries, but only if the resume still exists
    for (const [jobId, resumeId] of Object.entries(freshTailored)) {
      if (existingResumeIds.has(resumeId) || !userResumes.length) {
        map[jobId] = resumeId;
      }
    }
    return map;
  }, [userResumes, freshTailored]);

  // Category filter (persisted in localStorage)
  // SSR-safe: always start with 'All', then sync from localStorage after mount
  const [activeCategory, setActiveCategory] = useState<string>('All');
  const [activeSource, setActiveSource] = useState<SourceFilter>('All');
  useEffect(() => {
    const stored = localStorage.getItem('jobScout_category');
    if (stored) setActiveCategory(stored);
  }, []);

  const handleCategoryChange = useCallback((cat: string) => {
    setActiveCategory(cat);
    setPage(0);
    if (typeof window !== 'undefined') {
      localStorage.setItem('jobScout_category', cat);
    }
  }, []);

  // ── Queries ────────────────────────────────────────────────────────────

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', 'matches'],
    queryFn: async () => (await jobMatchApi.list()).data,
    refetchInterval: 5 * 60_000, // refresh every 5 minutes
  });

  const { data: stats } = useQuery({
    queryKey: ['jobs', 'stats'],
    queryFn: async () => (await jobMatchApi.stats()).data,
    refetchInterval: 5 * 60_000,
  });

  const { data: scheduler } = useQuery({
    queryKey: ['jobs', 'scheduler'],
    queryFn: async () => (await jobMatchApi.schedulerStatus()).data,
    refetchInterval: 30_000, // every 30s for countdown accuracy
  });

  const { data: tracking = {} } = useQuery<TrackingStatuses>({
    queryKey: ['jobs', 'tracking'],
    queryFn: async () => (await jobMatchApi.getTracking()).data,
  });

  // ── Applications query (for cross-page sync) ───────────────────────────

  const userId = typeof window !== 'undefined' ? getUserId() : '';

  const { data: applications = [] } = useQuery<Application[]>({
    queryKey: ['applications', userId],
    queryFn: async () => {
      if (!userId) return [];
      return (await applicationsApi.list(userId)).data;
    },
    enabled: !!userId,
    staleTime: 30_000,
  });

  // jobId → existing Application record (for upsert logic)
  const appByJobId = useMemo(() => {
    const m: Record<string, Application> = {};
    for (const a of applications) m[a.jobId] = a;
    return m;
  }, [applications]);

  // Keep refs so the async onSuccess closure always sees fresh data
  const appByJobIdRef = useRef(appByJobId);
  useEffect(() => { appByJobIdRef.current = appByJobId; }, [appByJobId]);
  const jobsRef = useRef(jobs);
  useEffect(() => { jobsRef.current = jobs; }, [jobs]);

  // ── Tracking mutation ──────────────────────────────────────────────────

  const trackMutation = useMutation({
    mutationFn: async ({ jobId, status }: { jobId: string; status: string }) => {
      await jobMatchApi.track(jobId, status);
    },
    onSuccess: async (_, { jobId, status }) => {
      queryClient.invalidateQueries({ queryKey: ['jobs', 'tracking'] });

      // Sync to Apply & Track pipeline for kanban-visible statuses
      if (KANBAN_STATUSES.has(status)) {
        const existingApp = appByJobIdRef.current[jobId];
        try {
          if (existingApp) {
            await applicationsApi.update(existingApp.applicationId, {
              status: status as Application['status'],
            });
          } else {
            const job = jobsRef.current.find((j) => j.jobId === jobId);
            await applicationsApi.create({
              jobId,
              companyName: job?.company,
              roleTitle: job?.title,
              url: job?.url,
              status,
            });
          }
          queryClient.invalidateQueries({ queryKey: ['applications'] });
        } catch {
          // sync failure is non-critical — pipeline stays eventually consistent
        }
      }
    },
    onError: () => {
      toast({ title: 'Failed to update status', variant: 'destructive' });
    },
  });

  // ── Tailor mutation ─────────────────────────────────────────────────────

  const [tailoringJobId, setTailoringJobId] = useState<string | null>(null);

  const tailorMutation = useMutation({
    mutationFn: async (jobId: string) => {
      setTailoringJobId(jobId);
      return (await tailorApi.generate(jobId)).data;
    },
    onSuccess: (data) => {
      setTailoringJobId(null);
      // Optimistically track the new tailored resume
      setFreshTailored((prev) => ({ ...prev, [data.jobId]: data.resumeId }));
      // Invalidate resumes list so the real data catches up
      queryClient.invalidateQueries({ queryKey: ['resumes'] });

      if (data.compilationError) {
        toast({
          title: 'Resume tailored but PDF compilation failed',
          description: 'You can still open it in the editor to fix issues.',
          variant: 'destructive',
        });
        return;
      }
      toast({
        title: 'Tailored resume generated!',
        description: data.matchKeywords?.length
          ? `Matched ${data.matchKeywords.length} keywords. Click "Editor" to refine.`
          : 'Resume ready — click "Editor" to open.',
      });
    },
    onError: () => {
      setTailoringJobId(null);
      toast({ title: 'Failed to generate tailored resume', variant: 'destructive' });
    },
  });

  // ── LinkedIn import modal ───────────────────────────────────────────────

  const [showLinkedInModal, setShowLinkedInModal] = useState(false);
  const [linkedInUrlInput, setLinkedInUrlInput] = useState('');
  const [importResult, setImportResult] = useState<{
    name?: string;
    headline?: string;
    location?: string;
    summary: boolean;
    website?: string;
    phone?: string;
    email?: string;
    education_added: number;
    education?: Array<{ school: string; degree?: string; field?: string; dates?: string }>;
    certifications_added: number;
  } | null>(null);

  const importLinkedInMutation = useMutation({
    mutationFn: async (url: string) => {
      const res = await userApi.importLinkedInProfile(url || undefined);
      return res.data;
    },
    onSuccess: (data) => {
      setImportResult(data.imported);
      toast({
        title: 'LinkedIn profile imported!',
        description: [
          data.imported.name && `Name: ${data.imported.name}`,
          data.imported.headline && 'Headline',
          data.imported.summary && 'Summary',
          data.imported.website && 'Website',
          data.imported.phone && 'Phone',
          data.imported.education_added > 0 && `${data.imported.education_added} education entries`,
          data.imported.certifications_added > 0 && `${data.imported.certifications_added} certifications`,
        ]
          .filter(Boolean)
          .join(' · ') || 'Profile updated',
      });
    },
    onError: (err: any) => {
      toast({
        title: 'Import failed',
        description: err?.response?.data?.detail || 'Could not import LinkedIn profile.',
        variant: 'destructive',
      });
    },
  });

  // ── Countdown ──────────────────────────────────────────────────────────

  const countdown = useCountdown(scheduler?.nextRunTime ?? null);

  // ── Filtering & search ─────────────────────────────────────────────────

  const filtered = useMemo(() => {
    let list = jobs;

    // Source filter
    if (activeSource !== 'All') {
      list = list.filter((j) => (j.source || '').toLowerCase() === activeSource);
    }

    // Category filter
    if (activeCategory !== 'All') {
      const cat = activeCategory.toLowerCase();
      list = list.filter((j) => {
        const category = (j.category || '').toLowerCase();
        const title = (j.title || '').toLowerCase();
        const skills = (j.requiredSkills || []).join(' ').toLowerCase();
        return category.includes(cat) || title.includes(cat) || skills.includes(cat);
      });
    }

    // Free-text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (j) =>
          (j.title || '').toLowerCase().includes(q) ||
          (j.company || '').toLowerCase().includes(q) ||
          (j.location || '').toLowerCase().includes(q)
      );
    }

    return list;
  }, [jobs, activeCategory, activeSource, searchQuery]);

  // ── Pagination ─────────────────────────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(filtered.length / ROWS_PER_PAGE));
  const paginated = filtered.slice(
    page * ROWS_PER_PAGE,
    (page + 1) * ROWS_PER_PAGE
  );

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* ── Header row ────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Job Scout</h1>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 border-[#0A66C2]/30 text-[#0A66C2] hover:bg-[#0A66C2]/10 dark:border-[#0A66C2]/40 dark:text-[#4FA3FF]"
          onClick={() => { setImportResult(null); setShowLinkedInModal(true); }}
        >
          <Linkedin className="h-4 w-4" />
          Import from LinkedIn
        </Button>
      </div>

      {/* ── Stats cards ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Total Jobs"
          value={stats?.totalJobs ?? 0}
          subtitle={`${stats?.analyzedJobs ?? 0} analyzed`}
          icon={Briefcase}
        />
        <StatCard
          title="New Today"
          value={stats?.newToday ?? 0}
          subtitle="Added in last 24h"
          icon={TrendingUp}
        />
        <StatCard
          title="Next Auto-Scrape"
          value={countdown}
          subtitle={
            scheduler?.lastScrape?.timestamp
              ? `Last: ${timeAgo(scheduler.lastScrape.timestamp)}`
              : 'Scheduler starting…'
          }
          icon={CalendarClock}
        />
      </div>

      {/* ── Last scrape status banner ─────────────────────────────────── */}
      {scheduler?.lastScrape?.status && (
        <Card
          className={
            scheduler.lastScrape.status === 'success'
              ? 'border-[hsl(var(--success))]/20 bg-[hsl(var(--success))]/5'
              : 'border-destructive/20 bg-destructive/5'
          }
        >
          <CardContent className="flex items-center gap-3 px-5 py-3">
            <Timer className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="text-sm">
              <span className="font-medium">
                {scheduler.lastScrape.status === 'success'
                  ? 'Last Scrape Completed'
                  : 'Last Scrape Failed'}
              </span>
              {' — '}
              <span className="text-muted-foreground">
                {scheduler.lastScrape.message}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Category filters + search ─────────────────────────────────── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((cat) => (
            <Button
              key={cat}
              size="sm"
              variant={activeCategory === cat ? 'default' : 'outline'}
              className="h-7 rounded-full px-3 text-xs"
              onClick={() => handleCategoryChange(cat)}
            >
              {cat}
            </Button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs…"
            className="h-9 pl-8"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(0);
            }}
          />
        </div>
      </div>

      {/* ── Jobs table ────────────────────────────────────────────────── */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                <th className="whitespace-nowrap px-4 py-3 w-10">
                  <div className="flex flex-col gap-1">
                    <span>Source</span>
                    <select
                      value={activeSource}
                      onChange={(e) => { setActiveSource(e.target.value as SourceFilter); setPage(0); }}
                      className="mt-0.5 w-24 rounded border border-border/60 bg-background px-1 py-0.5 text-[10px] font-normal normal-case text-foreground cursor-pointer"
                    >
                      {SOURCES.map((s) => (
                        <option key={s} value={s}>{s === 'All' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}</option>
                      ))}
                    </select>
                  </div>
                </th>
                <th className="whitespace-nowrap px-4 py-3 w-72">Title</th>
                <th className="whitespace-nowrap px-4 py-3">Company</th>
                <th className="whitespace-nowrap px-4 py-3 hidden md:table-cell">Location</th>
                <th className="whitespace-nowrap px-4 py-3 hidden lg:table-cell">Posted</th>
                <th className="whitespace-nowrap px-4 py-3">Status</th>
                <th className="whitespace-nowrap px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {jobsLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 animate-pulse rounded bg-muted" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : paginated.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                    {filtered.length === 0 && jobs.length > 0
                      ? 'No jobs match the current filters.'
                      : 'No jobs yet. The scheduler will scrape automatically every hour.'}
                  </td>
                </tr>
              ) : (
                paginated.map((job) => (
                  <JobRow
                    key={job.jobId}
                    job={job}
                    trackingStatus={tracking[job.jobId]?.status || 'pending'}
                    onTrack={(status) =>
                      trackMutation.mutate({ jobId: job.jobId, status })
                    }
                    onTailor={() => tailorMutation.mutate(job.jobId)}
                    isTailoring={tailoringJobId === job.jobId}
                    onTitleClick={() => setSelectedJob(job)}
                    tailoredResumeId={tailoredResumes[job.jobId]}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* ── Pagination ────────────────────────────────────────────── */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t px-4 py-3">
            <p className="text-xs text-muted-foreground">
              {filtered.length} jobs · Page {page + 1} of {totalPages}
            </p>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-8 w-8 p-0"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 w-8 p-0"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* ── LinkedIn Import Modal ──────────────────────────────────────── */}
      {showLinkedInModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <Card className="w-full max-w-md mx-4 shadow-2xl">
            <CardContent className="p-6 space-y-5">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Linkedin className="h-5 w-5 text-[#0A66C2]" />
                  <h2 className="text-base font-semibold">Import from LinkedIn</h2>
                </div>
                <button
                  onClick={() => { setShowLinkedInModal(false); setImportResult(null); }}
                  className="rounded-sm opacity-70 hover:opacity-100 transition-opacity"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {importResult ? (
                /* ── Success state ── */
                <div className="space-y-4">
                  <div className="rounded-lg border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/5 p-4 space-y-2">
                    <p className="text-sm font-medium text-[hsl(var(--success))]">Import complete!</p>
                    <ul className="text-sm text-muted-foreground space-y-1">
                      {importResult.name && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Name: {importResult.name}
                        </li>
                      )}
                      {importResult.headline && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Headline: {importResult.headline}
                        </li>
                      )}
                      {importResult.location && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Location: {importResult.location}
                        </li>
                      )}
                      {importResult.summary && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Summary / About section
                        </li>
                      )}
                      {importResult.email && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Email: {importResult.email}
                        </li>
                      )}
                      {importResult.phone && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Phone: {importResult.phone}
                        </li>
                      )}
                      {importResult.website && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          Website: {importResult.website}
                        </li>
                      )}
                      {importResult.education_added > 0 && (
                        <li className="flex flex-col gap-0.5">
                          <span className="flex items-center gap-2">
                            <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                            {importResult.education_added} education entr{importResult.education_added === 1 ? 'y' : 'ies'} added
                          </span>
                          {importResult.education && importResult.education.length > 0 && (
                            <ul className="ml-6 mt-0.5 space-y-0.5">
                              {importResult.education.map((e, i) => (
                                <li key={i} className="text-xs">
                                  <span className="font-medium">{e.school}</span>
                                  {e.degree && <span className="text-muted-foreground/70"> · {e.degree}</span>}
                                  {e.field && <span className="text-muted-foreground/70">, {e.field}</span>}
                                  {e.dates && <span className="text-muted-foreground/50"> ({e.dates})</span>}
                                </li>
                              ))}
                            </ul>
                          )}
                        </li>
                      )}
                      {importResult.certifications_added > 0 && (
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                          {importResult.certifications_added} certification{importResult.certifications_added === 1 ? '' : 's'} added
                        </li>
                      )}
                    </ul>
                  </div>
                  <Button
                    className="w-full"
                    onClick={() => { setShowLinkedInModal(false); setImportResult(null); }}
                  >
                    Done
                  </Button>
                </div>
              ) : (
                /* ── Input state ── */
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Enter your LinkedIn profile URL to import your education,
                    certifications, summary, contact info, and website.
                  </p>
                  <p className="text-xs text-muted-foreground bg-muted/50 rounded p-2">
                    <strong>Note:</strong> A browser window may open on first use for a one-time
                    LinkedIn login. Your session is saved for all future imports.
                  </p>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      LinkedIn Profile URL
                    </label>
                    <Input
                      placeholder="https://www.linkedin.com/in/your-username"
                      value={linkedInUrlInput}
                      onChange={(e) => setLinkedInUrlInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && linkedInUrlInput.trim()) {
                          importLinkedInMutation.mutate(linkedInUrlInput.trim());
                        }
                      }}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => setShowLinkedInModal(false)}
                      disabled={importLinkedInMutation.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      className="flex-1 gap-2 bg-[#0A66C2] hover:bg-[#0A66C2]/90"
                      onClick={() => importLinkedInMutation.mutate(linkedInUrlInput.trim())}
                      disabled={!linkedInUrlInput.trim() || importLinkedInMutation.isPending}
                    >
                      {importLinkedInMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Importing…
                        </>
                      ) : (
                        <>
                          <Linkedin className="h-4 w-4" />
                          Import
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── Job Detail Modal ───────────────────────────────────────────── */}
      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          trackingStatus={tracking[selectedJob.jobId]?.status || 'pending'}
          onTrack={(status) => trackMutation.mutate({ jobId: selectedJob.jobId, status })}
          onTailor={() => {
            tailorMutation.mutate(selectedJob.jobId);
            setSelectedJob(null);
          }}
        />
      )}
    </div>
  );
}

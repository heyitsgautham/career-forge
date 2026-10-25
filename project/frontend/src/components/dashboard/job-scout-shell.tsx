'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Search,
  Briefcase,
  Timer,
  TrendingUp,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Linkedin,
} from 'lucide-react';
import {
  jobMatchApi,
  tailorApi,
  resumesApi,
  applicationsApi,
  type Job,
  type TrackingStatuses,
  type Application,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { timeAgo, getUserId } from './job-scout/format';
import { useCountdown } from './job-scout/use-countdown';
import { StatCard } from './job-scout/stat-card';
import { JobRow } from './job-scout/job-row';
import { JobDetailModal } from './job-scout/job-detail-modal';
import {
  CATEGORIES,
  ROWS_PER_PAGE,
  KANBAN_STATUSES,
  SOURCES,
  SourceFilter,
} from './job-scout/constants';
import { LinkedInImportModal } from './job-scout/linkedin-import-modal';

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
    queryFn: async () =>
      (await resumesApi.list()).data as Array<{ id: string; job_id?: string; type?: string }>,
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
  useEffect(() => {
    appByJobIdRef.current = appByJobId;
  }, [appByJobId]);
  const jobsRef = useRef(jobs);
  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

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
  const paginated = filtered.slice(page * ROWS_PER_PAGE, (page + 1) * ROWS_PER_PAGE);

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
          // The modal mounts fresh on each open, so its import result starts empty
          onClick={() => setShowLinkedInModal(true)}
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
              <span className="text-muted-foreground">{scheduler.lastScrape.message}</span>
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
                      onChange={(e) => {
                        setActiveSource(e.target.value as SourceFilter);
                        setPage(0);
                      }}
                      className="mt-0.5 w-24 rounded border border-border/60 bg-background px-1 py-0.5 text-[10px] font-normal normal-case text-foreground cursor-pointer"
                    >
                      {SOURCES.map((s) => (
                        <option key={s} value={s}>
                          {s === 'All' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
                        </option>
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
                    onTrack={(status) => trackMutation.mutate({ jobId: job.jobId, status })}
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
      {showLinkedInModal && <LinkedInImportModal onClose={() => setShowLinkedInModal(false)} />}

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

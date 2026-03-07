'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Search,
  MapPin,
  Building2,
  ExternalLink,
  Briefcase,
  Clock,
  Loader2,
  Timer,
  TrendingUp,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  FileText,
  X,
  Star,
  BarChart3,
  Zap,
  Edit,
} from 'lucide-react';
import { jobMatchApi, tailorApi, type Job, type TrackingStatuses } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

// ── Category filter labels ───────────────────────────────────────────────────

const CATEGORIES = [
  'All',
  'SDE',
  'AI/ML',
  'Data',
  'Web',
  'Mobile',
  'DevOps',
  'Security',
  'Embedded',
  'Blockchain',
  'Research',
  'Database',
  'GenAI',
] as const;

const TRACKING_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offered', label: 'Offered' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'ignored', label: 'Ignored' },
];

const TRACKING_COLORS: Record<string, string> = {
  pending: 'bg-muted text-muted-foreground',
  saved: 'bg-primary/10 text-primary',
  applied: 'bg-[hsl(var(--accent))]/10 text-[hsl(var(--accent))]',
  interviewing: 'bg-primary/10 text-primary',
  offered: 'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]',
  rejected: 'bg-destructive/10 text-destructive',
  ignored: 'bg-muted text-muted-foreground',
};

const ROWS_PER_PAGE = 25;

// ── localStorage helpers for tailored resume persistence ─────────────────────

const TAILORED_STORAGE_KEY = 'jobScout_tailoredResumes';

function loadTailoredResumes(): Record<string, string> {
  try {
    const raw = localStorage.getItem(TAILORED_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveTailoredResumes(map: Record<string, string>) {
  try {
    localStorage.setItem(TAILORED_STORAGE_KEY, JSON.stringify(map));
  } catch { /* quota exceeded — best effort */ }
}

// ── Rich markdown description renderer ───────────────────────────────────────

function unescapeMarkdown(text: string): string {
  return text.replace(/\\([\-&#+_~`>|{}\[\]()!])/g, '$1');
}

function RichDescription({ text }: { text: string }) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let bulletBuffer: string[] = [];
  let key = 0;

  const flushBullets = () => {
    if (bulletBuffer.length === 0) return;
    elements.push(
      <ul key={key++} className="list-disc list-outside pl-5 space-y-1 my-1">
        {bulletBuffer.map((b, i) => (
          <li key={i}>{renderInline(b)}</li>
        ))}
      </ul>
    );
    bulletBuffer = [];
  };

  const renderInline = (line: string): React.ReactNode => {
    const cleaned = unescapeMarkdown(line);
    const parts: React.ReactNode[] = [];
    let lastIdx = 0;
    // Match **bold** segments
    const boldRe = /\*\*([^*]+)\*\*/g;
    let m: RegExpExecArray | null;
    while ((m = boldRe.exec(cleaned)) !== null) {
      if (m.index > lastIdx) {
        parts.push(cleaned.slice(lastIdx, m.index));
      }
      parts.push(<strong key={`b${m.index}`}>{m[1]}</strong>);
      lastIdx = m.index + m[0].length;
    }
    if (lastIdx < cleaned.length) {
      parts.push(cleaned.slice(lastIdx));
    }
    return parts.length === 1 ? parts[0] : <>{parts}</>;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    // Bullet line: starts with "* " or "- "
    const bulletMatch = line.match(/^\s*(?:\*|-)\s+(.+)/);
    if (bulletMatch) {
      bulletBuffer.push(bulletMatch[1]);
      continue;
    }

    // Non-bullet line — flush any pending bullets
    flushBullets();

    // Empty line → spacing
    if (line.trim() === '') {
      elements.push(<div key={key++} className="h-2" />);
      continue;
    }

    // Heading-like: entire line is bold
    const headingMatch = line.match(/^\s*\*\*([^*]+)\*\*\s*$/);
    if (headingMatch) {
      elements.push(
        <p key={key++} className="font-semibold mt-3 mb-1">
          {unescapeMarkdown(headingMatch[1])}
        </p>
      );
      continue;
    }

    // Regular paragraph with inline bold
    elements.push(
      <p key={key++} className="my-0.5 leading-relaxed">
        {renderInline(line)}
      </p>
    );
  }

  flushBullets();

  return <div className="text-sm">{elements}</div>;
}

// ── Countdown timer hook ─────────────────────────────────────────────────────

function useCountdown(targetIso: string | null) {
  const [remaining, setRemaining] = useState('');

  useEffect(() => {
    if (!targetIso) {
      setRemaining('—');
      return;
    }
    const tick = () => {
      const diff = new Date(targetIso).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining('Scraping now…');
        return;
      }
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(`${m}m ${s.toString().padStart(2, '0')}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  return remaining;
}

// ── Relative time formatter ──────────────────────────────────────────────────

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

// ── Ordinal date formatter ────────────────────────────────────────────────────

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function ordinalSuffix(d: number) {
  if (d >= 11 && d <= 13) return 'th';
  return ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th'][d % 10];
}

function formatPostedDate(
  datePosted: string | undefined | null,
  createdAt: string | undefined | null,
): string {
  // Prefer createdAt (has time); fall back to datePosted
  const src = createdAt || datePosted;
  if (!src || src === 'nan') return '—';
  const d = new Date(src);
  if (isNaN(d.getTime())) return datePosted && datePosted !== 'nan' ? datePosted : '—';
  const day = d.getDate();
  const month = MONTHS[d.getMonth()];
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${day}${ordinalSuffix(day)} ${month}, ${hh}:${mm}`;
}

// ── Stats Card ───────────────────────────────────────────────────────────────

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: typeof Briefcase;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {title}
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
            {subtitle && (
              <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
            )}
          </div>
          <div className="rounded-lg bg-primary/10 p-2.5">
            <Icon className="h-5 w-5 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export function JobScoutShell() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [tailoredResumes, setTailoredResumes] = useState<Record<string, string>>({});

  // Restore tailored resume map from localStorage on mount
  useEffect(() => {
    setTailoredResumes(loadTailoredResumes());
  }, []);

  // Category filter (persisted in localStorage)
  // SSR-safe: always start with 'All', then sync from localStorage after mount
  const [activeCategory, setActiveCategory] = useState<string>('All');
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

  // ── Tracking mutation ──────────────────────────────────────────────────

  const trackMutation = useMutation({
    mutationFn: async ({ jobId, status }: { jobId: string; status: string }) => {
      await jobMatchApi.track(jobId, status);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs', 'tracking'] });
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
      // Store the mapping: jobId → resumeId (state + localStorage)
      setTailoredResumes((prev) => {
        const next = { ...prev, [data.jobId]: data.resumeId };
        saveTailoredResumes(next);
        return next;
      });
      // Invalidate resumes list so it shows up in the Resumes tab
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

  // ── Countdown ──────────────────────────────────────────────────────────

  const countdown = useCountdown(scheduler?.nextRunTime ?? null);

  // ── Filtering & search ─────────────────────────────────────────────────

  const filtered = useMemo(() => {
    let list = jobs;

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
  }, [jobs, activeCategory, searchQuery]);

  // ── Pagination ─────────────────────────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(filtered.length / ROWS_PER_PAGE));
  const paginated = filtered.slice(
    page * ROWS_PER_PAGE,
    (page + 1) * ROWS_PER_PAGE
  );

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
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
                    {Array.from({ length: 6 }).map((_, j) => (
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

// ── Single table row ─────────────────────────────────────────────────────────

function JobRow({
  job,
  trackingStatus,
  onTrack,
  onTailor,
  isTailoring,
  onTitleClick,
  tailoredResumeId,
}: {
  job: Job;
  trackingStatus: string;
  onTrack: (status: string) => void;
  onTailor: () => void;
  isTailoring: boolean;
  onTitleClick: () => void;
  tailoredResumeId?: string;
}) {
  return (
    <tr className="group transition-all duration-150 hover:bg-primary/[0.03]">
      {/* Title + salary */}
      <td className="px-4 py-3 w-72 max-w-[18rem]">
        <button
          className="font-medium leading-tight line-clamp-1 max-w-[17rem] text-left text-primary hover:underline cursor-pointer transition-colors"
          title={`Click to view details: ${job.title}`}
          onClick={onTitleClick}
        >
          {job.title}
        </button>
        {job.salary && (
          <span className="text-xs text-[hsl(var(--success))]">
            {job.salary}
          </span>
        )}
      </td>

      {/* Company */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <Building2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="line-clamp-1">{job.company || '—'}</span>
        </div>
      </td>

      {/* Location */}
      <td className="hidden px-4 py-3 md:table-cell">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          <span className="line-clamp-1">{job.location || '—'}</span>
        </div>
      </td>

      {/* Posted */}
      <td className="hidden px-4 py-3 lg:table-cell">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap">
          <Clock className="h-3.5 w-3.5 shrink-0" />
          {formatPostedDate(job.datePosted, job.createdAt)}
        </div>
      </td>

      {/* Tracking status */}
      <td className="px-4 py-3">
        <select
          className={`cursor-pointer rounded-md border px-2 py-1 text-xs font-medium transition ${trackingStatus
              ? TRACKING_COLORS[trackingStatus] || ''
              : 'bg-background text-muted-foreground'
            }`}
          value={trackingStatus}
          onChange={(e) => onTrack(e.target.value)}
        >
          {TRACKING_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2 whitespace-nowrap">
          {tailoredResumeId ? (
            <Link
              href={`/dashboard/resumes/${tailoredResumeId}/edit`}
              className="inline-flex items-center justify-center gap-1 w-[5.25rem] rounded-md border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/10 px-2 py-1 text-xs font-medium text-[hsl(var(--success))] hover:bg-[hsl(var(--success))]/20 transition"
              title="Open tailored resume in editor"
            >
              <Edit className="h-3 w-3" />
              Editor
            </Link>
          ) : (
            <button
              className={`inline-flex items-center justify-center gap-1 w-[5.25rem] rounded-md border px-2 py-1 text-xs font-medium transition ${
                isTailoring
                  ? 'text-muted-foreground opacity-60 cursor-wait'
                  : 'text-primary hover:bg-primary/10 cursor-pointer'
              }`}
              title="Generate tailored resume for this job"
              disabled={isTailoring}
              onClick={onTailor}
            >
              {isTailoring ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <FileText className="h-3 w-3" />
              )}
              {isTailoring ? 'Tailoring…' : 'Resume'}
            </button>
          )}
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 transition"
            >
              View
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Job Detail Modal ──────────────────────────────────────────────────────────

function JobDetailModal({
  job,
  onClose,
  trackingStatus,
  onTrack,
  onTailor,
}: {
  job: Job;
  onClose: () => void;
  trackingStatus: string;
  onTrack: (status: string) => void;
  onTailor: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-background border border-border/60 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4 p-6 border-b border-border/60">
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-bold leading-tight truncate">{job.title}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              {job.company && (
                <span className="flex items-center gap-1">
                  <Building2 className="h-3.5 w-3.5" /> {job.company}
                </span>
              )}
              {job.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" /> {job.location}
                </span>
              )}
              {job.jobType && (
                <Badge variant="secondary" className="text-xs">{job.jobType}</Badge>
              )}
            </div>
          </div>
          <Button variant="ghost" size="icon" className="shrink-0" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* ── Scrollable body ──────────────────────────────────────── */}
        <div className="overflow-y-auto p-6 space-y-5" style={{ maxHeight: 'calc(85vh - 10rem)' }}>

          {/* Quick info badges row */}
          <div className="flex flex-wrap gap-2">
            {job.salary && (
              <Badge className="gap-1 bg-[hsl(var(--success))]/10 text-[hsl(var(--success))] border-[hsl(var(--success))]/30">
                $ {job.salary}
              </Badge>
            )}
            {job.experienceLevel && (
              <Badge variant="outline" className="gap-1">
                <Star className="h-3 w-3" /> {job.experienceLevel}
              </Badge>
            )}
            {job.category && (
              <Badge variant="outline">{job.category}</Badge>
            )}
            {job.source && (
              <Badge variant="secondary" className="text-xs">{job.source}</Badge>
            )}
            {job.datePosted && job.datePosted !== 'nan' && (
              <Badge variant="secondary" className="gap-1 text-xs">
                <Clock className="h-3 w-3" />
                {formatPostedDate(job.datePosted, job.createdAt)}
              </Badge>
            )}
          </div>

          {/* Match score breakdown */}
          {job.matchScore != null && (
            <div className="rounded-lg border border-border/60 bg-muted/30 p-4">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Match Score</h3>
                <span className="ml-auto text-lg font-bold text-primary">                  {typeof job.matchScore === 'number' ? `${Math.round(job.matchScore)}%` : job.matchScore}
                </span>
              </div>
              {job.matchBreakdown && (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {job.matchBreakdown.vectorScore != null && (
                    <div>
                      <p className="text-xs text-muted-foreground">Vector Similarity</p>
                      <p className="font-medium">{Math.round(job.matchBreakdown.vectorScore * 100)}%</p>
                    </div>
                  )}
                  {job.matchBreakdown.keywordScore != null && (
                    <div>
                      <p className="text-xs text-muted-foreground">Keyword Match</p>
                      <p className="font-medium">{Math.round(job.matchBreakdown.keywordScore * 100)}%</p>
                    </div>
                  )}
                  {job.matchBreakdown.matchedSkills && job.matchBreakdown.matchedSkills.length > 0 && (
                    <div className="col-span-2">
                      <p className="text-xs text-muted-foreground mb-1">Matched Skills</p>
                      <div className="flex flex-wrap gap-1">
                        {job.matchBreakdown.matchedSkills.map((s) => (
                          <Badge key={s} className="text-xs bg-primary/10 text-primary border-primary/30">{s}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {job.matchBreakdown.explanation && (
                    <div className="col-span-2">
                      <p className="text-xs text-muted-foreground mb-1">Explanation</p>
                      <p className="text-sm">{job.matchBreakdown.explanation}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Description */}
          {job.description && (
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Job Description</h3>
              <div className="bg-muted/40 rounded-lg p-4 max-h-60 overflow-y-auto">
                <RichDescription text={job.description} />
              </div>
            </div>
          )}

          {/* Required Skills */}
          {job.requiredSkills && job.requiredSkills.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Required Skills</h3>
              <div className="flex flex-wrap gap-1.5">
                {job.requiredSkills.map((skill) => (
                  <Badge key={skill} variant="default" className="text-xs">{skill}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* Preferred Skills */}
          {job.preferredSkills && job.preferredSkills.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Preferred Skills</h3>
              <div className="flex flex-wrap gap-1.5">
                {job.preferredSkills.map((skill) => (
                  <Badge key={skill} variant="outline" className="text-xs">{skill}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* Missing Skills */}
          {job.missingSkills && job.missingSkills.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">Skills You&apos;re Missing</h3>
              <div className="flex flex-wrap gap-1.5">
                {job.missingSkills.map((skill) => (
                  <Badge key={skill} variant="destructive" className="text-xs">{skill}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* ATS Keywords */}
          {job.atsKeywords && job.atsKeywords.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground mb-2">ATS Keywords</h3>
              <div className="flex flex-wrap gap-1.5">
                {job.atsKeywords.map((kw) => (
                  <Badge key={kw} variant="secondary" className="text-xs">{kw}</Badge>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Footer actions ───────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-3 border-t border-border/60 p-4">
          <select
            className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium transition ${
              TRACKING_COLORS[trackingStatus] || 'bg-background text-muted-foreground'
            }`}
            value={trackingStatus}
            onChange={(e) => onTrack(e.target.value)}
          >
            {TRACKING_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <div className="flex items-center gap-2">
            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/10 transition"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                View Posting
              </a>
            )}
            <Button size="sm" className="gap-1.5" onClick={onTailor}>
              <Zap className="h-3.5 w-3.5" />
              Tailor Resume
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

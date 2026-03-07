'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
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
} from 'lucide-react';
import { jobMatchApi, type Job, type TrackingStatuses } from '@/lib/api';
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
  pending: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  saved: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  applied: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  interviewing: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  offered: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  rejected: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  ignored: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
};

const ROWS_PER_PAGE = 25;

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
              ? 'border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20'
              : 'border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20'
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
    </div>
  );
}

// ── Single table row ─────────────────────────────────────────────────────────

function JobRow({
  job,
  trackingStatus,
  onTrack,
}: {
  job: Job;
  trackingStatus: string;
  onTrack: (status: string) => void;
}) {
  return (
    <tr className="group transition-colors hover:bg-muted/30">
      {/* Title + salary */}
      <td className="px-4 py-3 w-72 max-w-[18rem]">
        <div className="font-medium leading-tight line-clamp-1 max-w-[17rem]" title={job.title}>{job.title}</div>
        {job.salary && (
          <span className="text-xs text-emerald-600 dark:text-emerald-400">
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
          <button
            className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium text-muted-foreground opacity-50 cursor-not-allowed"
            title="Coming in M5 — Tailored Apply"
            disabled
          >
            <FileText className="h-3 w-3" />
            Resume
          </button>
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

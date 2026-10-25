'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Briefcase, TrendingUp, CalendarClock, Linkedin } from 'lucide-react';
import type { Job } from '@/lib/api';
import { timeAgo } from './job-scout/format';
import { useCountdown } from './job-scout/use-countdown';
import { StatCard } from './job-scout/stat-card';
import { JobDetailModal } from './job-scout/job-detail-modal';
import { CATEGORIES, type SourceFilter } from './job-scout/constants';
import { LinkedInImportModal } from './job-scout/linkedin-import-modal';
import { filterJobs, pageCount, pageSlice } from './job-scout/filter-jobs';
import { JobsTable } from './job-scout/jobs-table';
import { ScrapeStatusBanner } from './job-scout/scrape-status-banner';
import { useJobScoutData } from './job-scout/use-job-scout-data';

export function JobScoutShell() {
  const {
    jobs,
    jobsLoading,
    stats,
    scheduler,
    tracking,
    tailoredResumes,
    tailoringJobId,
    track,
    tailor,
  } = useJobScoutData();

  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [showLinkedInModal, setShowLinkedInModal] = useState(false);

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

  const countdown = useCountdown(scheduler?.nextRunTime ?? null);

  const filtered = useMemo(
    () => filterJobs(jobs, { source: activeSource, category: activeCategory, query: searchQuery }),
    [jobs, activeCategory, activeSource, searchQuery]
  );
  const totalPages = pageCount(filtered.length);

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
      <ScrapeStatusBanner lastScrape={scheduler?.lastScrape} />

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
      <JobsTable
        rows={pageSlice(filtered, page)}
        loading={jobsLoading}
        filteredCount={filtered.length}
        totalCount={jobs.length}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        source={activeSource}
        onSourceChange={(source) => {
          setActiveSource(source);
          setPage(0);
        }}
        tracking={tracking}
        tailoredResumes={tailoredResumes}
        tailoringJobId={tailoringJobId}
        onTrack={track}
        onTailor={tailor}
        onSelect={setSelectedJob}
      />

      {/* ── LinkedIn Import Modal ──────────────────────────────────────── */}
      {showLinkedInModal && <LinkedInImportModal onClose={() => setShowLinkedInModal(false)} />}

      {/* ── Job Detail Modal ───────────────────────────────────────────── */}
      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          trackingStatus={tracking[selectedJob.jobId]?.status || 'pending'}
          onTrack={(status) => track(selectedJob.jobId, status)}
          onTailor={() => {
            tailor(selectedJob.jobId);
            setSelectedJob(null);
          }}
        />
      )}
    </div>
  );
}

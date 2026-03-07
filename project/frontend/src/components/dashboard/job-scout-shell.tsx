'use client';

import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import {
  Search,
  MapPin,
  Building2,
  Sparkles,
  ArrowRight,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Briefcase,
  Clock,
  FileText,
  Loader2,
  Trash2,
  SlidersHorizontal,
  BarChart3,
  X,
} from 'lucide-react';
import { jobMatchApi, type Job } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

/* ─── Skeleton job card ──────────────────────────────────────────────────── */
function SkeletonJobCard({ index }: { index: number }) {
  const opacity = 0.15 + (4 - index) * 0.04;
  return (
    <Card className="border-dashed" style={{ opacity }} aria-hidden="true">
      <CardContent className="p-4 space-y-3">
        <div className="space-y-2">
          <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
          <div className="flex items-center gap-2">
            <div className="h-3 w-24 rounded bg-muted animate-pulse" />
            <div className="h-3 w-20 rounded bg-muted animate-pulse" />
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Array.from({ length: 3 + (index % 2) }, (_, j) => (
            <div
              key={j}
              className="h-5 rounded-full bg-muted animate-pulse"
              style={{ width: `${48 + j * 16}px` }}
            />
          ))}
        </div>
        <div className="flex items-center justify-between pt-1">
          <div className="h-3 w-16 rounded bg-muted animate-pulse" />
          <div className="h-6 w-12 rounded-full bg-muted animate-pulse" />
        </div>
      </CardContent>
    </Card>
  );
}

/* ─── Match Score Badge ──────────────────────────────────────────────────── */
export function MatchScoreBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) {
    return (
      <Badge variant="outline" className="font-mono text-xs tabular-nums text-muted-foreground">
        —
      </Badge>
    );
  }
  let colorClass = 'bg-match-low/10 text-match-low border-match-low/20';
  if (score >= 80) {
    colorClass = 'bg-match-high/10 text-match-high border-match-high/20';
  } else if (score >= 60) {
    colorClass = 'bg-match-mid/10 text-match-mid border-match-mid/20';
  }

  return (
    <Badge variant="secondary" className={`${colorClass} font-mono text-xs tabular-nums`}>
      {Math.round(score)}%
    </Badge>
  );
}

/* ─── Job Card ───────────────────────────────────────────────────────────── */
function JobCard({
  job,
  onDelete,
}: {
  job: Job;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const requiredSkills = job.requiredSkills || [];
  const missingSkills = job.missingSkills || [];
  const matchedSkills = job.matchBreakdown?.matchedSkills || [];

  return (
    <article className="group">
      <Card className="transition-shadow hover:shadow-md">
        <CardContent className="p-4 space-y-3">
          {/* Header: title + match score */}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold text-sm leading-tight truncate">{job.title}</h3>
              <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                <span className="flex items-center gap-1 truncate">
                  <Building2 className="h-3 w-3 shrink-0" aria-hidden="true" />
                  {job.company}
                </span>
                {job.location && (
                  <span className="flex items-center gap-1 truncate">
                    <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
                    {job.location}
                  </span>
                )}
              </div>
            </div>
            <MatchScoreBadge score={job.matchScore} />
          </div>

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {job.category && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {job.category}
              </Badge>
            )}
            {job.experienceLevel && (
              <span className="flex items-center gap-1">
                <Briefcase className="h-3 w-3" aria-hidden="true" />
                {job.experienceLevel}
              </span>
            )}
            {job.salary && (
              <span className="font-medium text-foreground">{job.salary}</span>
            )}
            {job.datePosted && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" aria-hidden="true" />
                {job.datePosted}
              </span>
            )}
            {job.source && (
              <span className="capitalize">{job.source}</span>
            )}
          </div>

          {/* Skill chips */}
          <div className="flex flex-wrap gap-1">
            {requiredSkills.slice(0, 6).map((skill) => {
              const isMatched = matchedSkills.some(
                (s) => s.toLowerCase() === skill.toLowerCase()
              );
              const isMissing = missingSkills.some(
                (s) => s.toLowerCase() === skill.toLowerCase()
              );
              return (
                <Badge
                  key={skill}
                  variant="secondary"
                  className={`text-[10px] px-1.5 py-0 ${
                    isMissing
                      ? 'bg-destructive/10 text-destructive border-destructive/20'
                      : isMatched
                      ? 'bg-match-high/10 text-match-high border-match-high/20'
                      : ''
                  }`}
                >
                  {skill}
                </Badge>
              );
            })}
            {requiredSkills.length > 6 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                +{requiredSkills.length - 6}
              </Badge>
            )}
          </div>

          {/* Missing skills */}
          {missingSkills.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-[10px] text-muted-foreground mr-1 self-center">Missing:</span>
              {missingSkills.slice(0, 4).map((skill) => (
                <Badge
                  key={skill}
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 border-amber-500/30 text-amber-600 bg-amber-50 dark:bg-amber-950/20"
                >
                  {skill}
                </Badge>
              ))}
              {missingSkills.length > 4 && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  +{missingSkills.length - 4}
                </Badge>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-1 border-t">
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="h-3 w-3" aria-hidden="true" />
                ) : (
                  <ChevronDown className="h-3 w-3" aria-hidden="true" />
                )}
                {expanded ? 'Hide' : 'Details'}
              </Button>
              {job.url && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs gap-1"
                  asChild
                >
                  <a href={job.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    Apply
                  </a>
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs gap-1 text-muted-foreground hover:text-destructive"
                onClick={() => onDelete(job.jobId)}
              >
                <Trash2 className="h-3 w-3" aria-hidden="true" />
              </Button>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs gap-1"
              aria-label={`Generate tailored resume for ${job.title}`}
              title="Coming in M5 — Tailored Apply"
            >
              <FileText className="h-3 w-3" aria-hidden="true" />
              Tailored Resume
            </Button>
          </div>

          {/* Expandable detail */}
          {expanded && (
            <div className="pt-2 border-t space-y-2">
              {job.matchBreakdown?.explanation && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Match insight: </span>
                  {job.matchBreakdown.explanation}
                </p>
              )}
              {job.atsKeywords && job.atsKeywords.length > 0 && (
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground mb-1">ATS Keywords</p>
                  <div className="flex flex-wrap gap-1">
                    {job.atsKeywords.map((kw) => (
                      <Badge key={kw} variant="outline" className="text-[10px] px-1.5 py-0">
                        {kw}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {job.description && (
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground mb-1">Full Description</p>
                  <p className="text-xs text-muted-foreground whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                    {job.description}
                  </p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </article>
  );
}

/* ─── Stats Bar ──────────────────────────────────────────────────────────── */
function StatsBar() {
  const { data: stats } = useQuery({
    queryKey: ['job-scout-stats'],
    queryFn: async () => {
      const res = await jobMatchApi.stats();
      return res.data;
    },
    staleTime: 30_000,
  });

  if (!stats || stats.totalJobs === 0) return null;

  return (
    <div className="flex flex-wrap gap-3">
      <div className="flex items-center gap-1.5 text-xs">
        <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">Jobs:</span>
        <span className="font-medium">{stats.totalJobs}</span>
      </div>
      <div className="flex items-center gap-1.5 text-xs">
        <Sparkles className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">Analyzed:</span>
        <span className="font-medium">{stats.analyzedJobs}</span>
      </div>
      {stats.averageMatch !== null && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">Avg Match:</span>
          <MatchScoreBadge score={stats.averageMatch} />
        </div>
      )}
      {stats.topCategories.slice(0, 3).map((cat) => (
        <Badge key={cat.category} variant="outline" className="text-[10px] px-1.5 py-0">
          {cat.category} ({cat.count})
        </Badge>
      ))}
    </div>
  );
}

/* ─── Scan Dialog ────────────────────────────────────────────────────────── */
function ScanDialog({
  open,
  onClose,
  onScan,
  isScanning,
}: {
  open: boolean;
  onClose: () => void;
  onScan: (term: string, location: string, count: number) => void;
  isScanning: boolean;
}) {
  const [term, setTerm] = useState('Software Developer');
  const [location, setLocation] = useState('India');
  const [count, setCount] = useState(20);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Scan for jobs"
    >
      <Card className="w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Scan for Jobs</h3>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="scan-term">
                Search Term
              </label>
              <Input
                id="scan-term"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                placeholder="e.g. Backend Developer"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="scan-location">
                Location
              </label>
              <Input
                id="scan-location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. India, Remote"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="scan-count">
                Results (max 50)
              </label>
              <Input
                id="scan-count"
                type="number"
                min={5}
                max={50}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
              />
            </div>
          </div>
          <Button
            className="w-full gap-2"
            onClick={() => onScan(term, location, count)}
            disabled={isScanning || !term.trim()}
          >
            {isScanning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Scanning &amp; Analyzing...
              </>
            ) : (
              <>
                <Search className="h-4 w-4" aria-hidden="true" />
                Start Scan
              </>
            )}
          </Button>
          <p className="text-[10px] text-center text-muted-foreground">
            Scrapes portals → AI-analyzes each JD → scores against your profile
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Main Component ─────────────────────────────────────────────────────── */
export function JobScoutShell() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Filters
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [minMatch, setMinMatch] = useState<string>('0');
  const [sortBy, setSortBy] = useState<string>('match');
  const [showScanDialog, setShowScanDialog] = useState(false);

  // Fetch jobs
  const { data: jobs, isLoading, isError } = useQuery({
    queryKey: ['job-scout-matches'],
    queryFn: async () => {
      const res = await jobMatchApi.list();
      return res.data;
    },
    staleTime: 30_000,
  });

  // Scan mutation
  const scanMutation = useMutation({
    mutationFn: (params: { search_term: string; location: string; results_wanted: number }) =>
      jobMatchApi.scan(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-scout-matches'] });
      queryClient.invalidateQueries({ queryKey: ['job-scout-stats'] });
      setShowScanDialog(false);
      toast({ title: 'Jobs scanned!', description: 'Jobs have been scraped, analyzed, and scored.' });
    },
    onError: (err: any) => {
      toast({
        title: 'Scan failed',
        description: err?.response?.data?.detail || 'Could not complete job scan',
        variant: 'destructive',
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => jobMatchApi.delete(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-scout-matches'] });
      queryClient.invalidateQueries({ queryKey: ['job-scout-stats'] });
      toast({ title: 'Job removed' });
    },
  });

  // Derive unique categories from loaded jobs
  const categories = useMemo(() => {
    if (!jobs) return [];
    const cats = new Set(jobs.map((j) => j.category).filter(Boolean));
    return Array.from(cats).sort();
  }, [jobs]);

  // Apply client-side filters + sorting
  const filteredJobs = useMemo(() => {
    if (!jobs) return [];
    let result = [...jobs];

    // Role filter
    if (roleFilter && roleFilter !== 'all') {
      result = result.filter((j) => j.category === roleFilter);
    }

    // Min match
    const minMatchNum = Number(minMatch) || 0;
    if (minMatchNum > 0) {
      result = result.filter((j) => (j.matchScore ?? 0) >= minMatchNum);
    }

    // Sort
    if (sortBy === 'date') {
      result.sort((a, b) => (b.datePosted || '').localeCompare(a.datePosted || ''));
    } else if (sortBy === 'company') {
      result.sort((a, b) => (a.company || '').localeCompare(b.company || ''));
    } else {
      result.sort((a, b) => (b.matchScore ?? 0) - (a.matchScore ?? 0));
    }

    return result;
  }, [jobs, roleFilter, minMatch, sortBy]);

  const handleScan = useCallback(
    (term: string, location: string, count: number) => {
      scanMutation.mutate({ search_term: term, location, results_wanted: count });
    },
    [scanMutation]
  );

  const handleDelete = useCallback(
    (jobId: string) => {
      deleteMutation.mutate(jobId);
    },
    [deleteMutation]
  );

  const hasJobs = jobs && jobs.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Job Scout</h2>
          <p className="text-sm text-muted-foreground mt-1">
            AI-matched jobs ranked by fit against your profile — powered by semantic embeddings
          </p>
        </div>
        <Button
          className="gap-2 shrink-0"
          onClick={() => setShowScanDialog(true)}
          disabled={scanMutation.isPending}
          aria-label="Scan for jobs"
        >
          {scanMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Search className="h-4 w-4" aria-hidden="true" />
          )}
          Scan Jobs
        </Button>
      </div>

      {/* Stats bar */}
      {hasJobs && <StatsBar />}

      {/* Filter bar */}
      {hasJobs && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
            Filters
          </div>
          <Select
            className="h-8 w-[160px] text-xs"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="all">All categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat!}>
                {cat}
              </option>
            ))}
          </Select>

          <Select
            className="h-8 w-[130px] text-xs"
            value={minMatch}
            onChange={(e) => setMinMatch(e.target.value)}
          >
            <option value="0">No minimum</option>
            <option value="25">25%+</option>
            <option value="50">50%+</option>
            <option value="75">75%+</option>
          </Select>

          <Select
            className="h-8 w-[130px] text-xs"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="match">Match score</option>
            <option value="date">Date posted</option>
            <option value="company">Company</option>
          </Select>

          <span className="text-xs text-muted-foreground ml-auto">
            {filteredJobs.length} job{filteredJobs.length !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 5 }, (_, i) => (
            <SkeletonJobCard key={i} index={i} />
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && !isLoading && (
        <Card className="border-destructive/30">
          <CardContent className="py-8 text-center">
            <p className="text-sm text-destructive">Failed to load jobs. Please try again.</p>
          </CardContent>
        </Card>
      )}

      {/* Job cards grid */}
      {!isLoading && hasJobs && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredJobs.map((job) => (
            <JobCard key={job.jobId} job={job} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !hasJobs && !isError && (
        <Card className="border-dashed">
          <CardContent className="py-10 flex flex-col items-center text-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Sparkles className="h-6 w-6 text-primary" aria-hidden="true" />
            </div>
            <div className="space-y-1.5 max-w-md">
              <h3 className="text-base font-semibold">No jobs scanned yet</h3>
              <p className="text-sm text-muted-foreground">
                Job Scout uses Titan embeddings to match your skills, projects, and experience against
                live job listings. Each match shows how well you fit — and what skills are missing.
              </p>
            </div>

            <div className="flex flex-wrap gap-2 justify-center mt-2">
              <Badge variant="outline" className="gap-1.5">
                <Building2 className="h-3 w-3" aria-hidden="true" />
                Company match
              </Badge>
              <Badge variant="outline" className="gap-1.5">
                <MapPin className="h-3 w-3" aria-hidden="true" />
                Location filter
              </Badge>
              <Badge variant="outline" className="gap-1.5">
                <Sparkles className="h-3 w-3" aria-hidden="true" />
                85%+ match score
              </Badge>
            </div>

            <Button
              className="gap-2 mt-2"
              onClick={() => setShowScanDialog(true)}
              aria-label="Start scanning for jobs"
            >
              Start Scanning
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Scan dialog */}
      <ScanDialog
        open={showScanDialog}
        onClose={() => setShowScanDialog(false)}
        onScan={handleScan}
        isScanning={scanMutation.isPending}
      />
    </div>
  );
}

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { Job, TrackingStatuses } from '@/lib/api';
import { SOURCES, type SourceFilter } from './constants';
import { JobRow } from './job-row';

const COLUMN_COUNT = 7;

export interface JobsTableProps {
  rows: Job[];
  loading: boolean;
  /** Jobs left after filtering, across every page. */
  filteredCount: number;
  /** Jobs before filtering, used to tell "no jobs yet" apart from "nothing matches". */
  totalCount: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  source: SourceFilter;
  onSourceChange: (source: SourceFilter) => void;
  tracking: TrackingStatuses;
  tailoredResumes: Record<string, string>;
  tailoringJobId: string | null;
  onTrack: (jobId: string, status: string) => void;
  onTailor: (jobId: string) => void;
  onSelect: (job: Job) => void;
}

export function JobsTable({
  rows,
  loading,
  filteredCount,
  totalCount,
  page,
  totalPages,
  onPageChange,
  source,
  onSourceChange,
  tracking,
  tailoredResumes,
  tailoringJobId,
  onTrack,
  onTailor,
  onSelect,
}: JobsTableProps) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
              <th className="whitespace-nowrap px-4 py-3 w-10">
                <div className="flex flex-col gap-1">
                  <span>Source</span>
                  <select
                    aria-label="Filter by source"
                    value={source}
                    onChange={(e) => onSourceChange(e.target.value as SourceFilter)}
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
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: COLUMN_COUNT }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 animate-pulse rounded bg-muted" />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={COLUMN_COUNT} className="px-4 py-12 text-center text-muted-foreground">
                  {filteredCount === 0 && totalCount > 0
                    ? 'No jobs match the current filters.'
                    : 'No jobs yet. The scheduler will scrape automatically every hour.'}
                </td>
              </tr>
            ) : (
              rows.map((job) => (
                <JobRow
                  key={job.jobId}
                  job={job}
                  trackingStatus={tracking[job.jobId]?.status || 'pending'}
                  onTrack={(status) => onTrack(job.jobId, status)}
                  onTailor={() => onTailor(job.jobId)}
                  isTailoring={tailoringJobId === job.jobId}
                  onTitleClick={() => onSelect(job)}
                  tailoredResumeId={tailoredResumes[job.jobId]}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {filteredCount} jobs · Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0"
              aria-label="Previous page"
              disabled={page === 0}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0"
              aria-label="Next page"
              disabled={page >= totalPages - 1}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

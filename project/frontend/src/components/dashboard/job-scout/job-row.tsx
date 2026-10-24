'use client';

import Link from 'next/link';
import { MapPin, Building2, ExternalLink, Clock, Loader2, FileText, Edit } from 'lucide-react';
import { type Job } from '@/lib/api';
import { formatPostedDate } from './format';
import { TRACKING_OPTIONS, TRACKING_COLORS, SOURCE_ICONS } from './constants';

export function SourceLogo({ source }: { source?: string }) {
  const key = (source || '').toLowerCase();
  const icon = SOURCE_ICONS[key];
  if (!icon) return <Building2 className="h-7 w-7 shrink-0 text-muted-foreground" />;
  return (
    <img
      src={icon}
      alt={key}
      title={key.charAt(0).toUpperCase() + key.slice(1)}
      className="h-7 w-7 shrink-0 rounded object-contain"
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
    />
  );
}

// ── Single table row ─────────────────────────────────────────────────────────

export function JobRow({
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
      {/* Source icon */}
      <td className="px-4 py-3 w-10">
        <SourceLogo source={job.source} />
      </td>

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

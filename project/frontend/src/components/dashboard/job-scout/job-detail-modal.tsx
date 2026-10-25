'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MapPin, Building2, ExternalLink, Clock, X, Star, BarChart3, Zap } from 'lucide-react';
import { type Job } from '@/lib/api';
import { formatPostedDate } from './format';
import { RichDescription } from './rich-description';
import { TRACKING_OPTIONS, TRACKING_COLORS } from './constants';
import { Portal } from '@/components/ui/portal';

// ── Job Detail Modal ──────────────────────────────────────────────────────────

export function JobDetailModal({
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
    <Portal>
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
                  <Badge variant="secondary" className="text-xs">
                    {job.jobType}
                  </Badge>
                )}
              </div>
            </div>
            <Button variant="ghost" size="icon" className="shrink-0" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* ── Scrollable body ──────────────────────────────────────── */}
          <div
            className="overflow-y-auto p-6 space-y-5"
            style={{ maxHeight: 'calc(85vh - 10rem)' }}
          >
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
              {job.category && <Badge variant="outline">{job.category}</Badge>}
              {job.source && (
                <Badge variant="secondary" className="text-xs">
                  {job.source}
                </Badge>
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
                  <span className="ml-auto text-lg font-bold text-primary">
                    {' '}
                    {typeof job.matchScore === 'number'
                      ? `${Math.round(job.matchScore)}%`
                      : job.matchScore}
                  </span>
                </div>
                {job.matchBreakdown && (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {job.matchBreakdown.vectorScore != null && (
                      <div>
                        <p className="text-xs text-muted-foreground">Vector Similarity</p>
                        <p className="font-medium">
                          {Math.round(job.matchBreakdown.vectorScore * 100)}%
                        </p>
                      </div>
                    )}
                    {job.matchBreakdown.keywordScore != null && (
                      <div>
                        <p className="text-xs text-muted-foreground">Keyword Match</p>
                        <p className="font-medium">
                          {Math.round(job.matchBreakdown.keywordScore * 100)}%
                        </p>
                      </div>
                    )}
                    {job.matchBreakdown.matchedSkills &&
                      job.matchBreakdown.matchedSkills.length > 0 && (
                        <div className="col-span-2">
                          <p className="text-xs text-muted-foreground mb-1">Matched Skills</p>
                          <div className="flex flex-wrap gap-1">
                            {job.matchBreakdown.matchedSkills.map((s) => (
                              <Badge
                                key={s}
                                className="text-xs bg-primary/10 text-primary border-primary/30"
                              >
                                {s}
                              </Badge>
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
                <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                  Job Description
                </h3>
                <div className="bg-muted/40 rounded-lg p-4 max-h-60 overflow-y-auto">
                  <RichDescription text={job.description} />
                </div>
              </div>
            )}

            {/* Required Skills */}
            {job.requiredSkills && job.requiredSkills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                  Required Skills
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {job.requiredSkills.map((skill) => (
                    <Badge key={skill} variant="default" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Preferred Skills */}
            {job.preferredSkills && job.preferredSkills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                  Preferred Skills
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {job.preferredSkills.map((skill) => (
                    <Badge key={skill} variant="outline" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Missing Skills */}
            {job.missingSkills && job.missingSkills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                  Skills You&apos;re Missing
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {job.missingSkills.map((skill) => (
                    <Badge key={skill} variant="destructive" className="text-xs">
                      {skill}
                    </Badge>
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
                    <Badge key={kw} variant="secondary" className="text-xs">
                      {kw}
                    </Badge>
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
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
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
    </Portal>
  );
}

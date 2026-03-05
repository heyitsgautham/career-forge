'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Search, MapPin, Building2, Sparkles, ArrowRight } from 'lucide-react';

/* ─── Skeleton job card ──────────────────────────────────────────────────── */
function SkeletonJobCard({ index }: { index: number }) {
    // Stagger opacity so it looks more natural
    const opacity = 0.15 + (4 - index) * 0.04;

    return (
        <Card
            className="border-dashed"
            style={{ opacity }}
            aria-hidden="true"
        >
            <CardContent className="p-4 space-y-3">
                {/* Title shimmer */}
                <div className="space-y-2">
                    <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
                    <div className="flex items-center gap-2">
                        <div className="h-3 w-24 rounded bg-muted animate-pulse" />
                        <div className="h-3 w-20 rounded bg-muted animate-pulse" />
                    </div>
                </div>

                {/* Skills shimmer */}
                <div className="flex flex-wrap gap-1.5">
                    {Array.from({ length: 3 + (index % 2) }, (_, j) => (
                        <div
                            key={j}
                            className="h-5 rounded-full bg-muted animate-pulse"
                            style={{ width: `${48 + j * 16}px` }}
                        />
                    ))}
                </div>

                {/* Match score shimmer */}
                <div className="flex items-center justify-between pt-1">
                    <div className="h-3 w-16 rounded bg-muted animate-pulse" />
                    <div className="h-6 w-12 rounded-full bg-muted animate-pulse" />
                </div>
            </CardContent>
        </Card>
    );
}

/* ─── Match Score Badge (design system) ──────────────────────────────────── */
export function MatchScoreBadge({ score }: { score: number }) {
    let variant: 'default' | 'secondary' | 'destructive' | 'outline' = 'secondary';
    let colorClass = 'bg-match-low/10 text-match-low border-match-low/20';

    if (score >= 80) {
        colorClass = 'bg-match-high/10 text-match-high border-match-high/20';
    } else if (score >= 60) {
        colorClass = 'bg-match-mid/10 text-match-mid border-match-mid/20';
    }

    return (
        <Badge variant={variant} className={`${colorClass} font-mono text-xs tabular-nums`}>
            {score}%
        </Badge>
    );
}

export function JobScoutShell() {
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
                <Button disabled className="gap-2 shrink-0" aria-label="Scan for jobs (coming soon)">
                    <Search className="h-4 w-4" aria-hidden="true" />
                    Scan Jobs
                </Button>
            </div>

            {/* Empty state with skeleton cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 5 }, (_, i) => (
                    <SkeletonJobCard key={i} index={i} />
                ))}
            </div>

            {/* CTA card — full width */}
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

                    <Button disabled className="gap-2 mt-2" aria-label="Start scanning (coming soon)">
                        Start Scanning
                        <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </Button>
                    <p className="text-xs text-muted-foreground">
                        Coming in Milestone&nbsp;4
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}

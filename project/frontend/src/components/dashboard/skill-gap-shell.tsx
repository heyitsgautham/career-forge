'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Target, BookOpen, ArrowRight, TrendingUp } from 'lucide-react';

/* ─── Static SVG Radar (placeholder for real D3/recharts in M3) ─────────── */
function RadarPlaceholder() {
    const size = 240;
    const cx = size / 2;
    const cy = size / 2;
    const levels = 4;
    const labels = ['Frontend', 'Backend', 'DevOps', 'System Design', 'ML/AI', 'Cloud'];
    const n = labels.length;
    const maxR = 100;

    const points = (radius: number) =>
        Array.from({ length: n }, (_, i) => {
            const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
            return `${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`;
        }).join(' ');

    // Simulated user scores (0–1)
    const scores = [0.7, 0.55, 0.3, 0.45, 0.2, 0.6];
    const dataPoints = scores
        .map((s, i) => {
            const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
            return `${cx + maxR * s * Math.cos(angle)},${cy + maxR * s * Math.sin(angle)}`;
        })
        .join(' ');

    return (
        <svg
            viewBox={`0 0 ${size} ${size}`}
            className="mx-auto w-full max-w-[280px] opacity-30"
            aria-hidden="true"
            role="img"
        >
            <title>Skill radar placeholder</title>

            {/* Grid rings */}
            {Array.from({ length: levels }, (_, l) => (
                <polygon
                    key={l}
                    points={points(((l + 1) * maxR) / levels)}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="0.5"
                    className="text-border"
                />
            ))}

            {/* Axes */}
            {Array.from({ length: n }, (_, i) => {
                const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
                return (
                    <line
                        key={i}
                        x1={cx}
                        y1={cy}
                        x2={cx + maxR * Math.cos(angle)}
                        y2={cy + maxR * Math.sin(angle)}
                        stroke="currentColor"
                        strokeWidth="0.5"
                        className="text-border"
                    />
                );
            })}

            {/* Data polygon */}
            <polygon
                points={dataPoints}
                fill="hsl(var(--primary))"
                fillOpacity="0.15"
                stroke="hsl(var(--primary))"
                strokeWidth="1.5"
            />

            {/* Labels */}
            {labels.map((label, i) => {
                const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
                const lx = cx + (maxR + 18) * Math.cos(angle);
                const ly = cy + (maxR + 18) * Math.sin(angle);
                return (
                    <text
                        key={label}
                        x={lx}
                        y={ly}
                        textAnchor="middle"
                        dominantBaseline="central"
                        className="fill-muted-foreground text-[8px]"
                    >
                        {label}
                    </text>
                );
            })}
        </svg>
    );
}

export function SkillGapShell() {
    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-xl font-semibold tracking-tight">Skill Gap Analysis</h2>
                <p className="text-sm text-muted-foreground mt-1">
                    Identify gaps between your current skills and target roles — powered by Amazon&nbsp;Bedrock
                </p>
            </div>

            {/* Empty state */}
            <div className="grid gap-6 lg:grid-cols-2">
                {/* Radar preview */}
                <Card className="border-dashed">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Target className="h-4 w-4 text-primary" aria-hidden="true" />
                            Your Skill Radar
                        </CardTitle>
                        <CardDescription>
                            A personalised radar chart comparing your skills against the target role
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <RadarPlaceholder />
                        <p className="text-center text-xs text-muted-foreground mt-4">
                            Placeholder — real data arrives after analysis
                        </p>
                    </CardContent>
                </Card>

                {/* CTA card */}
                <Card className="border-dashed flex flex-col">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <TrendingUp className="h-4 w-4 text-primary" aria-hidden="true" />
                            Get Started
                        </CardTitle>
                        <CardDescription>
                            Paste a job description or pick a target role to begin
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col justify-center gap-4">
                        <div className="space-y-3 text-sm text-muted-foreground">
                            <div className="flex items-start gap-3">
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-medium">
                                    1
                                </span>
                                <span>Paste a job description or select a saved job</span>
                            </div>
                            <div className="flex items-start gap-3">
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-medium">
                                    2
                                </span>
                                <span>AI analyses the gap between your profile &amp; the role</span>
                            </div>
                            <div className="flex items-start gap-3">
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-medium">
                                    3
                                </span>
                                <span>Get a personalised learning roadmap via LearnWeave</span>
                            </div>
                        </div>

                        <Button disabled className="w-full gap-2 mt-2" aria-label="Run Skill Gap Analysis (coming soon)">
                            <BookOpen className="h-4 w-4" aria-hidden="true" />
                            Analyse Skill Gap
                            <ArrowRight className="h-4 w-4 ml-auto" aria-hidden="true" />
                        </Button>
                        <p className="text-xs text-center text-muted-foreground">
                            Coming in Milestone&nbsp;3
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    Send,
    Kanban,
    Plus,
    FileText,
    ArrowRight,
    CheckCircle2,
    Clock,
    XCircle,
    PhoneCall,
} from 'lucide-react';

/* ─── Kanban column placeholder ──────────────────────────────────────────── */
const COLUMNS = [
    { key: 'applied', label: 'Applied', icon: Send, color: 'text-blue-500' },
    { key: 'interviewing', label: 'Interviewing', icon: PhoneCall, color: 'text-amber-500' },
    { key: 'offer', label: 'Offer', icon: CheckCircle2, color: 'text-green-500' },
    { key: 'rejected', label: 'Rejected', icon: XCircle, color: 'text-red-500' },
] as const;

function KanbanColumn({
    label,
    icon: Icon,
    color,
}: {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    color: string;
}) {
    return (
        <div className="flex-1 min-w-[180px]">
            <div className="flex items-center gap-2 mb-3 px-1">
                <Icon className={`h-4 w-4 ${color}`} aria-hidden="true" />
                <span className="text-sm font-medium">{label}</span>
                <Badge variant="secondary" className="ml-auto text-[10px] px-1.5">
                    0
                </Badge>
            </div>
            <div className="min-h-[200px] rounded-lg border border-dashed border-border/50 p-3 flex items-center justify-center">
                <p className="text-xs text-muted-foreground text-center">
                    Drag applications here
                </p>
            </div>
        </div>
    );
}

export function ApplyTrackShell() {
    const [showAddModal, setShowAddModal] = useState(false);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h2 className="text-xl font-semibold tracking-tight">Apply &amp; Track</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                        Generate tailored resumes and track your application pipeline
                    </p>
                </div>
                <Button
                    variant="outline"
                    className="gap-2 shrink-0"
                    onClick={() => setShowAddModal(true)}
                    disabled
                    aria-label="Add application (coming soon)"
                >
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    Add Application
                </Button>
            </div>

            {/* Two-panel layout */}
            <div className="grid gap-6 lg:grid-cols-5">
                {/* Left panel — Tailored resume generator */}
                <Card className="border-dashed lg:col-span-2">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                            Tailored Resume
                        </CardTitle>
                        <CardDescription>
                            Paste a job description to auto-generate a resume tailored to the role
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Textarea placeholder */}
                        <div className="rounded-md border border-dashed border-border/50 bg-muted/30 p-4 min-h-[160px] flex items-center justify-center">
                            <p className="text-sm text-muted-foreground text-center max-w-[200px]">
                                Paste a job description here to generate a tailored resume…
                            </p>
                        </div>

                        <Button disabled className="w-full gap-2" aria-label="Generate tailored resume (coming soon)">
                            <FileText className="h-4 w-4" aria-hidden="true" />
                            Generate Tailored Resume
                            <ArrowRight className="h-4 w-4 ml-auto" aria-hidden="true" />
                        </Button>

                        <p className="text-xs text-center text-muted-foreground">
                            Coming in Milestone&nbsp;5
                        </p>
                    </CardContent>
                </Card>

                {/* Right panel — Kanban board */}
                <Card className="border-dashed lg:col-span-3">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Kanban className="h-4 w-4 text-primary" aria-hidden="true" />
                            Application Pipeline
                        </CardTitle>
                        <CardDescription>
                            Track applications through your hiring pipeline
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex gap-3 overflow-x-auto pb-2">
                            {COLUMNS.map((col) => (
                                <KanbanColumn
                                    key={col.key}
                                    label={col.label}
                                    icon={col.icon}
                                    color={col.color}
                                />
                            ))}
                        </div>

                        <div className="mt-6 flex flex-col items-center gap-2 text-center">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                                <Clock className="h-5 w-5 text-primary" aria-hidden="true" />
                            </div>
                            <p className="text-sm text-muted-foreground max-w-sm">
                                Your application tracker is empty. Add applications manually or let Job Scout auto-populate matched positions.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

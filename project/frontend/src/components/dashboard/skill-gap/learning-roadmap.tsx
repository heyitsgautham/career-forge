'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { BookOpen, CheckCircle2, ExternalLink, ChevronDown, ChevronUp, Clock } from 'lucide-react';
import { type Roadmap } from '@/lib/api';

export function LearningRoadmap({
  roadmap,
  open,
  onToggle,
  onMarkComplete,
}: {
  roadmap: Roadmap;
  open: boolean;
  onToggle: () => void;
  onMarkComplete: (week: number) => void;
}) {
  return (
    <Card className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" aria-hidden="true" />
            Learning Roadmap — {roadmap.roleName}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            aria-label={open ? 'Collapse roadmap' : 'Expand roadmap'}
          >
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
        {/* Progress bar */}
        <div className="space-y-1 mt-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {roadmap.completedWeeks} of {roadmap.totalWeeks} weeks completed
            </span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>
              {roadmap.totalWeeks > 0
                ? Math.round((roadmap.completedWeeks / roadmap.totalWeeks) * 100)
                : 0}
              %
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{
                width: `${
                  roadmap.totalWeeks > 0 ? (roadmap.completedWeeks / roadmap.totalWeeks) * 100 : 0
                }%`,
              }}
            />
          </div>
        </div>
      </CardHeader>

      {open && (
        <CardContent className="pt-0">
          <div className="relative space-y-0">
            {/* Timeline line */}
            <div className="absolute left-[18px] top-2 bottom-2 w-0.5 bg-border" />

            {roadmap.weeks.map((week) => {
              const done = !!week.completedAt;
              return (
                <div key={week.week} className="relative flex gap-4 pb-6 last:pb-0">
                  {/* Timeline dot */}
                  <div
                    className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 ${
                      done
                        ? 'border-[hsl(var(--success))] bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]'
                        : 'border-border bg-background text-muted-foreground'
                    }`}
                  >
                    {done ? (
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <span className="text-xs font-bold">{week.week}</span>
                    )}
                  </div>

                  {/* Card */}
                  <div className={`flex-1 rounded-lg border p-4 ${done ? 'bg-muted/30' : ''}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4
                          className={`font-medium ${done ? 'line-through text-muted-foreground' : ''}`}
                        >
                          Week {week.week}: {week.projectTitle}
                        </h4>
                        {week.description && (
                          <p className="text-xs text-muted-foreground mt-1">{week.description}</p>
                        )}
                      </div>
                      {!done && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="shrink-0 text-xs gap-1"
                          onClick={() => onMarkComplete(week.week)}
                        >
                          <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                          Complete
                        </Button>
                      )}
                      {done && (
                        <Badge
                          variant="outline"
                          className="bg-[hsl(var(--success))]/10 text-[hsl(var(--success))] border-[hsl(var(--success))]/20 text-xs"
                        >
                          Done
                        </Badge>
                      )}
                    </div>

                    {/* Tech stack chips */}
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {week.techStack.map((tech) => (
                        <Badge key={tech} variant="secondary" className="text-xs">
                          {tech}
                        </Badge>
                      ))}
                      <Badge variant="outline" className="text-xs gap-1">
                        <Clock className="h-3 w-3" aria-hidden="true" />~{week.estimatedHours}h
                      </Badge>
                    </div>

                    {/* Resources */}
                    {week.resources.length > 0 && (
                      <div className="mt-3 space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">Resources</p>
                        {week.resources.map((r, i) => (
                          <a
                            key={i}
                            href={r.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`${r.title} — opens in new tab`}
                            className="flex items-center gap-1.5 text-xs text-primary hover:underline"
                          >
                            <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                            {r.title}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

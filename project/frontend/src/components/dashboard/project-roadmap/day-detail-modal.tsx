'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Loader2,
  Clock,
  CheckCircle2,
  ExternalLink,
  X,
  Wrench,
  Layers,
  ListChecks,
  BookOpen,
} from 'lucide-react';
import { type RoadmapDay } from '@/lib/api';
import { DAY_COLORS } from './constants';
import { Portal } from '@/components/ui/portal';

export function DayDetailModal({
  day,
  color,
  canComplete,
  onClose,
  onComplete,
  completing,
}: {
  day: RoadmapDay;
  color: (typeof DAY_COLORS)[0];
  canComplete: boolean;
  onClose: () => void;
  onComplete: () => void;
  completing: boolean;
}) {
  const isCompleted = !!day.completedAt;

  return (
    <Portal>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in-up"
        onClick={onClose}
      >
        <Card
          className="w-full max-w-lg max-h-[85vh] overflow-y-auto shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm ${isCompleted ? 'bg-emerald-500' : color.bg}`}
                >
                  {isCompleted ? <CheckCircle2 className="h-5 w-5" /> : `D${day.day}`}
                </div>
                <div>
                  <CardTitle className="text-lg">{day.title}</CardTitle>
                  <CardDescription className="flex items-center gap-2 mt-0.5">
                    <Clock className="h-3 w-3" /> {day.estimatedHours} hours
                    {isCompleted && (
                      <Badge
                        variant="outline"
                        className="text-emerald-600 border-emerald-300 text-xs ml-1"
                      >
                        Completed
                      </Badge>
                    )}
                  </CardDescription>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>

          <CardContent className="space-y-5 pt-0">
            {/* Description */}
            <p className="text-sm text-muted-foreground leading-relaxed">{day.description}</p>

            {/* Tasks */}
            <div>
              <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-2">
                <ListChecks className="h-4 w-4 text-primary" /> Tasks
              </h4>
              <ul className="space-y-1.5">
                {day.tasks.map((task, i) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${color.bg}`} />
                    {task}
                  </li>
                ))}
              </ul>
            </div>

            {/* Tech details */}
            {day.techDetails && (
              <div>
                <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-2">
                  <Wrench className="h-4 w-4 text-amber-500" /> Tech Stack & Tools
                </h4>
                <p className="text-sm text-muted-foreground leading-relaxed bg-muted/40 rounded-lg p-3">
                  {day.techDetails}
                </p>
              </div>
            )}

            {/* Architecture */}
            {day.architecture && (
              <div>
                <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-2">
                  <Layers className="h-4 w-4 text-violet-500" /> Architecture & Design
                </h4>
                <p className="text-sm text-muted-foreground leading-relaxed bg-muted/40 rounded-lg p-3">
                  {day.architecture}
                </p>
              </div>
            )}

            {/* Resources */}
            {day.resources.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-2">
                  <BookOpen className="h-4 w-4 text-blue-500" /> Learning Resources
                </h4>
                <div className="space-y-2">
                  {day.resources.map((r, i) => (
                    <a
                      key={i}
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-primary hover:underline"
                    >
                      <ExternalLink className="h-3.5 w-3.5 shrink-0" /> {r.title}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Complete button */}
            {!isCompleted && canComplete && (
              <Button onClick={onComplete} disabled={completing} className="w-full gap-2">
                {completing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Mark Day {day.day} Complete
              </Button>
            )}
            {!isCompleted && !canComplete && (
              <p className="text-sm text-muted-foreground text-center py-2">
                Complete previous days first to unlock this day.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </Portal>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   STEP 2 — Pick 1 of 3 projects
   ═══════════════════════════════════════════════════════════════════════════ */

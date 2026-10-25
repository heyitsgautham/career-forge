'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, Clock, CheckCircle2, ArrowLeft, Trophy, Star, Lock, Unlock } from 'lucide-react';
import { type ProjectRoadmap, type RoadmapDay } from '@/lib/api';
import { DAY_COLORS, progressPercent } from './constants';

/* ─── Mountain-curve SVG connector between day cards ─────────────────────── */
export function MountainConnector({
  fromLeft,
  completed,
}: {
  fromLeft: boolean;
  completed: boolean;
}) {
  // Cubic bezier swooping from one side to the other
  const d = fromLeft ? 'M 160,5 C 160,65 340,55 340,115' : 'M 340,5 C 340,65 160,55 160,115';

  // Decorative terrain slash-marks scattered around the curve
  const marks: [number, number, number][] = fromLeft
    ? [
        [210, 28, 35],
        [185, 52, -25],
        [240, 60, 42],
        [275, 70, -20],
        [310, 82, 30],
        [330, 44, -35],
      ]
    : [
        [290, 28, -35],
        [315, 52, 25],
        [260, 60, -42],
        [225, 70, 20],
        [190, 82, -30],
        [170, 44, 35],
      ];

  return (
    <div
      className={`w-full select-none pointer-events-none ${
        completed ? 'text-primary/30' : 'text-muted-foreground/20'
      }`}
    >
      <svg viewBox="0 0 500 120" className="w-full h-[100px]" preserveAspectRatio="xMidYMid meet">
        {/* Main curved dashed line */}
        <path
          d={d}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeDasharray="10 7"
          strokeLinecap="round"
        />
        {/* Terrain hash marks */}
        {marks.map(([mx, my, angle], idx) => {
          const a = (angle * Math.PI) / 180;
          const len = 9;
          return (
            <line
              key={idx}
              x1={mx - len * Math.cos(a)}
              y1={my - len * Math.sin(a)}
              x2={mx + len * Math.cos(a)}
              y2={my + len * Math.sin(a)}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.7"
            />
          );
        })}
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   STEP 3 — Mountain-curve winding 7-day path
   ═══════════════════════════════════════════════════════════════════════════ */

export function DuolingoPath({
  roadmap,
  onDayClick,
  onBack,
  onUnlockAll,
  unlocking,
}: {
  roadmap: ProjectRoadmap;
  onDayClick: (day: RoadmapDay) => void;
  onBack: () => void;
  onUnlockAll: () => void;
  unlocking: boolean;
}) {
  const completedCount = roadmap.days.filter((d) => d.completedAt).length;
  const percent = progressPercent(completedCount, roadmap.totalDays);
  const allUnlocked = !!roadmap.unlockedAll;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 -ml-2 mb-2 text-muted-foreground"
            onClick={onBack}
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <h2 className="text-2xl font-bold">{roadmap.projectTitle}</h2>
          <p className="text-sm text-muted-foreground mt-1">{roadmap.projectDescription}</p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {roadmap.techStack.map((t) => (
              <Badge key={t} variant="secondary" className="text-xs">
                {t}
              </Badge>
            ))}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-3xl font-bold text-primary tabular-nums">{percent}%</div>
          <p className="text-xs text-muted-foreground">
            {completedCount}/{roadmap.totalDays} days
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="relative h-3 rounded-full bg-muted overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary via-violet-500 to-emerald-500 rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Unlock All button */}
      {!allUnlocked && (
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={onUnlockAll}
            disabled={unlocking}
          >
            {unlocking ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Unlock className="h-3.5 w-3.5" />
            )}
            Unlock All Days
          </Button>
        </div>
      )}
      {allUnlocked && (
        <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 justify-end">
          <Unlock className="h-3.5 w-3.5" /> All days unlocked
        </div>
      )}

      {/* ── Mountain-curve winding path ──────────────────────────────────── */}
      <div className="relative pt-4 pb-8">
        {/* Right-side progress rail (xl screens only) */}
        <div className="absolute -right-20 top-0 bottom-0 hidden xl:block">
          <div className="relative h-full w-px bg-border/40 mx-auto">
            {roadmap.days.map((day, i) => {
              const isCompleted = !!day.completedAt;
              const isNext = !isCompleted && roadmap.days.slice(0, i).every((d) => d.completedAt);
              const color = DAY_COLORS[i % DAY_COLORS.length];
              const topPct = roadmap.totalDays > 1 ? (i / (roadmap.totalDays - 1)) * 100 : 50;
              return (
                <div
                  key={day.day}
                  className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2"
                  style={{ top: `${topPct}%` }}
                >
                  <div className="text-right mr-1">
                    <p className="text-[9px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                      Day {day.day}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[80px]">
                      {day.title}
                    </p>
                  </div>
                  <div
                    className={`w-3 h-3 rounded-full border-2 shrink-0 transition-colors ${
                      isCompleted
                        ? 'bg-emerald-500 border-emerald-400'
                        : isNext
                          ? `${color.bg} border-white shadow-sm`
                          : 'bg-muted border-border'
                    }`}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Cards + mountain-curve connectors */}
        <div className="space-y-0">
          {roadmap.days.map((day, i) => {
            const color = DAY_COLORS[i % DAY_COLORS.length];
            const isCompleted = !!day.completedAt;
            const isNext = !isCompleted && roadmap.days.slice(0, i).every((d) => d.completedAt);
            const isLocked = !allUnlocked && !isCompleted && !isNext;
            const isLeft = i % 2 === 0;

            return (
              <div
                key={day.day}
                className="mountain-node"
                style={{ animationDelay: `${i * 100}ms` }}
              >
                {/* Curved SVG connector from previous card */}
                {i > 0 && (
                  <MountainConnector fromLeft={!isLeft} completed={isCompleted || isNext} />
                )}

                {/* Day card — alternates left / right */}
                <div
                  className={`flex ${
                    isLeft ? 'justify-center sm:justify-start' : 'justify-center sm:justify-end'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => onDayClick(day)}
                    className={`mountain-card group relative w-[85%] sm:w-[60%] text-center rounded-2xl border-2 p-5 pb-4 transition-all duration-300
                      ${
                        isCompleted
                          ? 'border-emerald-300/70 bg-emerald-50/50 dark:border-emerald-800/50 dark:bg-emerald-950/20 shadow-sm cursor-pointer hover:shadow-md'
                          : isNext
                            ? 'border-primary/70 bg-card shadow-xl cursor-pointer hover:shadow-2xl hover:-translate-y-0.5'
                            : 'border-dashed border-border/50 bg-muted/30 cursor-pointer hover:opacity-80 opacity-60'
                      }`}
                  >
                    {/* START badge for next available day */}
                    {isNext && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                        <Badge className="bg-primary text-primary-foreground px-4 py-0.5 text-[11px] font-bold shadow-md uppercase tracking-widest">
                          Start
                        </Badge>
                      </div>
                    )}

                    {/* Icon circle */}
                    <div className="flex justify-center mb-3">
                      <div
                        className={`w-16 h-16 rounded-full flex items-center justify-center transition-transform duration-300 group-hover:scale-105
                        ${
                          isCompleted
                            ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400'
                            : isLocked
                              ? 'bg-muted/60 text-muted-foreground/60'
                              : `${color.bgLight} ${color.text}`
                        }`}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="h-7 w-7" />
                        ) : isLocked ? (
                          <Lock className="h-7 w-7" />
                        ) : (
                          <span className="text-xl font-bold">D{day.day}</span>
                        )}
                      </div>
                    </div>

                    {/* Day label */}
                    <p className="text-[11px] uppercase tracking-widest text-muted-foreground font-medium">
                      Day {day.day}
                    </p>

                    {/* Title */}
                    <h3
                      className={`text-base font-bold mt-1 ${isCompleted ? 'line-through opacity-60' : ''}`}
                    >
                      {day.title}
                    </h3>

                    {/* Description */}
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                      {day.description}
                    </p>

                    {/* Stats */}
                    <div className="flex items-center justify-center gap-4 mt-3">
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" /> +
                        {day.tasks.length}
                      </span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" /> {day.estimatedHours}h
                      </span>
                    </div>

                    {/* START button for next day */}
                    {isNext && (
                      <div className="mt-4">
                        <div className="w-full py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-sm">
                          START
                        </div>
                      </div>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Completion */}
      {completedCount === roadmap.totalDays && (
        <Card className="border-2 border-emerald-300 dark:border-emerald-700 bg-emerald-50/60 dark:bg-emerald-950/30 text-center py-8 animate-fade-in-up">
          <Trophy className="h-14 w-14 text-amber-500 mx-auto mb-3" />
          <h3 className="text-xl font-bold">Project Complete!</h3>
          <p className="text-muted-foreground mt-1">
            You&apos;ve built <strong>{roadmap.projectTitle}</strong> in {roadmap.totalDays} days.
            Amazing work!
          </p>
        </Card>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Day detail modal — shows tech stack, process, architecture, tasks
   ═══════════════════════════════════════════════════════════════════════════ */

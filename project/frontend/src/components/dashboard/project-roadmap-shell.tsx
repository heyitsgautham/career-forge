'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Map, Loader2, ChevronDown, Clock, CheckCircle2,
  ExternalLink, Sparkles, ArrowLeft, Trophy, Star, Lock, Unlock, Trash2,
  Code2, Rocket, X, Wrench, Layers, ListChecks, BookOpen,
} from 'lucide-react';
import {
  projectRoadmapApi,
  type ProjectRoadmap,
  type ProjectSuggestion,
  type RoadmapDay,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

/* ─── Domain suggestions for quick-pick ──────────────────────────────────── */
const DOMAIN_CHIPS = [
  'Web Development', 'Backend Development', 'Mobile Development',
  'Machine Learning', 'Data Engineering', 'DevOps & Cloud',
  'Blockchain', 'Game Development', 'Cybersecurity',
  'AI / LLM Apps', 'System Design', 'Embedded Systems',
];

/* ─── Day theme colours (cycle through a spectrum) ───────────────────────── */
const DAY_COLORS = [
  { ring: 'ring-blue-400',   bg: 'bg-blue-500',   bgLight: 'bg-blue-50 dark:bg-blue-950/40',   text: 'text-blue-600 dark:text-blue-400',   glow: 'shadow-blue-400/40' },
  { ring: 'ring-violet-400', bg: 'bg-violet-500',  bgLight: 'bg-violet-50 dark:bg-violet-950/40', text: 'text-violet-600 dark:text-violet-400', glow: 'shadow-violet-400/40' },
  { ring: 'ring-amber-400',  bg: 'bg-amber-500',   bgLight: 'bg-amber-50 dark:bg-amber-950/40',  text: 'text-amber-600 dark:text-amber-400',  glow: 'shadow-amber-400/40' },
  { ring: 'ring-emerald-400',bg: 'bg-emerald-500', bgLight: 'bg-emerald-50 dark:bg-emerald-950/40', text: 'text-emerald-600 dark:text-emerald-400', glow: 'shadow-emerald-400/40' },
  { ring: 'ring-rose-400',   bg: 'bg-rose-500',    bgLight: 'bg-rose-50 dark:bg-rose-950/40',    text: 'text-rose-600 dark:text-rose-400',    glow: 'shadow-rose-400/40' },
  { ring: 'ring-cyan-400',   bg: 'bg-cyan-500',    bgLight: 'bg-cyan-50 dark:bg-cyan-950/40',    text: 'text-cyan-600 dark:text-cyan-400',    glow: 'shadow-cyan-400/40' },
  { ring: 'ring-orange-400', bg: 'bg-orange-500',   bgLight: 'bg-orange-50 dark:bg-orange-950/40', text: 'text-orange-600 dark:text-orange-400', glow: 'shadow-orange-400/40' },
];

/* ─── Mountain-curve SVG connector between day cards ─────────────────────── */
function MountainConnector({ fromLeft, completed }: { fromLeft: boolean; completed: boolean }) {
  // Cubic bezier swooping from one side to the other
  const d = fromLeft
    ? 'M 160,5 C 160,65 340,55 340,115'
    : 'M 340,5 C 340,65 160,55 160,115';

  // Decorative terrain slash-marks scattered around the curve
  const marks: [number, number, number][] = fromLeft
    ? [[210,28,35],[185,52,-25],[240,60,42],[275,70,-20],[310,82,30],[330,44,-35]]
    : [[290,28,-35],[315,52,25],[260,60,-42],[225,70,20],[190,82,-30],[170,44,35]];

  return (
    <div className={`w-full select-none pointer-events-none ${
      completed ? 'text-primary/30' : 'text-muted-foreground/20'
    }`}>
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
          const a = angle * Math.PI / 180;
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
function DuolingoPath({
  roadmap,
  onDayClick,
  onComplete,
  onBack,
  onUnlockAll,
  unlocking,
}: {
  roadmap: ProjectRoadmap;
  onDayClick: (day: RoadmapDay) => void;
  onComplete: (dayNum: number) => void;
  onBack: () => void;
  onUnlockAll: () => void;
  unlocking: boolean;
}) {
  const completedCount = roadmap.days.filter(d => d.completedAt).length;
  const progressPercent = Math.round((completedCount / roadmap.totalDays) * 100);
  const allUnlocked = !!roadmap.unlockedAll;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" className="gap-1 -ml-2 mb-2 text-muted-foreground" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <h2 className="text-2xl font-bold">{roadmap.projectTitle}</h2>
          <p className="text-sm text-muted-foreground mt-1">{roadmap.projectDescription}</p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {roadmap.techStack.map(t => (
              <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
            ))}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-3xl font-bold text-primary tabular-nums">{progressPercent}%</div>
          <p className="text-xs text-muted-foreground">{completedCount}/{roadmap.totalDays} days</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="relative h-3 rounded-full bg-muted overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary via-violet-500 to-emerald-500 rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${progressPercent}%` }}
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
            {unlocking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unlock className="h-3.5 w-3.5" />}
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
              const isNext = !isCompleted && roadmap.days.slice(0, i).every(d => d.completedAt);
              const color = DAY_COLORS[i % DAY_COLORS.length];
              const topPct = roadmap.totalDays > 1 ? (i / (roadmap.totalDays - 1)) * 100 : 50;
              return (
                <div
                  key={day.day}
                  className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2"
                  style={{ top: `${topPct}%` }}
                >
                  <div className="text-right mr-1">
                    <p className="text-[9px] uppercase tracking-wider text-muted-foreground/70 font-semibold">Day {day.day}</p>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[80px]">{day.title}</p>
                  </div>
                  <div className={`w-3 h-3 rounded-full border-2 shrink-0 transition-colors ${
                    isCompleted ? 'bg-emerald-500 border-emerald-400'
                    : isNext ? `${color.bg} border-white shadow-sm`
                    : 'bg-muted border-border'
                  }`} />
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
            const isNext = !isCompleted && roadmap.days.slice(0, i).every(d => d.completedAt);
            const isLocked = !allUnlocked && !isCompleted && !isNext;
            const isAccessible = allUnlocked || isCompleted || isNext;
            const isLeft = i % 2 === 0;

            return (
              <div key={day.day} className="mountain-node" style={{ animationDelay: `${i * 100}ms` }}>
                {/* Curved SVG connector from previous card */}
                {i > 0 && (
                  <MountainConnector
                    fromLeft={!isLeft}
                    completed={isCompleted || isNext}
                  />
                )}

                {/* Day card — alternates left / right */}
                <div className={`flex ${
                  isLeft
                    ? 'justify-center sm:justify-start'
                    : 'justify-center sm:justify-end'
                }`}>
                  <button
                    type="button"
                    onClick={() => onDayClick(day)}
                    className={`mountain-card group relative w-[85%] sm:w-[60%] text-center rounded-2xl border-2 p-5 pb-4 transition-all duration-300
                      ${isCompleted
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
                      <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-transform duration-300 group-hover:scale-105
                        ${isCompleted
                          ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400'
                          : isLocked
                            ? 'bg-muted/60 text-muted-foreground/60'
                            : `${color.bgLight} ${color.text}`
                        }`}>
                        {isCompleted
                          ? <CheckCircle2 className="h-7 w-7" />
                          : isLocked
                            ? <Lock className="h-7 w-7" />
                            : <span className="text-xl font-bold">D{day.day}</span>
                        }
                      </div>
                    </div>

                    {/* Day label */}
                    <p className="text-[11px] uppercase tracking-widest text-muted-foreground font-medium">
                      Day {day.day}
                    </p>

                    {/* Title */}
                    <h3 className={`text-base font-bold mt-1 ${isCompleted ? 'line-through opacity-60' : ''}`}>
                      {day.title}
                    </h3>

                    {/* Description */}
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                      {day.description}
                    </p>

                    {/* Stats */}
                    <div className="flex items-center justify-center gap-4 mt-3">
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" /> +{day.tasks.length}
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
            You&apos;ve built <strong>{roadmap.projectTitle}</strong> in {roadmap.totalDays} days. Amazing work!
          </p>
        </Card>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Day detail modal — shows tech stack, process, architecture, tasks
   ═══════════════════════════════════════════════════════════════════════════ */
function DayDetailModal({
  day,
  color,
  canComplete,
  onClose,
  onComplete,
  completing,
}: {
  day: RoadmapDay;
  color: typeof DAY_COLORS[0];
  canComplete: boolean;
  onClose: () => void;
  onComplete: () => void;
  completing: boolean;
}) {
  const isCompleted = !!day.completedAt;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in-up" onClick={onClose}>
      <Card className="w-full max-w-lg max-h-[85vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm ${isCompleted ? 'bg-emerald-500' : color.bg}`}>
                {isCompleted ? <CheckCircle2 className="h-5 w-5" /> : `D${day.day}`}
              </div>
              <div>
                <CardTitle className="text-lg">{day.title}</CardTitle>
                <CardDescription className="flex items-center gap-2 mt-0.5">
                  <Clock className="h-3 w-3" /> {day.estimatedHours} hours
                  {isCompleted && <Badge variant="outline" className="text-emerald-600 border-emerald-300 text-xs ml-1">Completed</Badge>}
                </CardDescription>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
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
              <p className="text-sm text-muted-foreground leading-relaxed bg-muted/40 rounded-lg p-3">{day.techDetails}</p>
            </div>
          )}

          {/* Architecture */}
          {day.architecture && (
            <div>
              <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-2">
                <Layers className="h-4 w-4 text-violet-500" /> Architecture & Design
              </h4>
              <p className="text-sm text-muted-foreground leading-relaxed bg-muted/40 rounded-lg p-3">{day.architecture}</p>
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
              {completing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
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
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   STEP 2 — Pick 1 of 3 projects
   ═══════════════════════════════════════════════════════════════════════════ */
function ProjectPicker({
  suggestions,
  onPick,
  picking,
  onBack,
}: {
  suggestions: { domain: string; projects: ProjectSuggestion[] };
  onPick: (p: ProjectSuggestion) => void;
  picking: boolean;
  onBack: () => void;
}) {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="gap-1 -ml-2 mb-2 text-muted-foreground" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" /> Change domain
        </Button>
        <h2 className="text-2xl font-bold">Choose Your Project</h2>
        <p className="text-muted-foreground text-sm mt-1">
          Pick one of these <strong>{suggestions.domain}</strong> projects.
          We&apos;ll build a 7-day plan for the one you choose.
        </p>
      </div>

      <div className="grid gap-4 stagger-children">
        {suggestions.projects.map((p) => (
          <Card
            key={p.id}
            className="group relative border-2 cursor-pointer transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:-translate-y-0.5 overflow-hidden"
            onClick={() => !picking && onPick(p)}
          >
            {/* Difficulty strip */}
            <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${p.difficulty === 'hard' ? 'bg-rose-500' : 'bg-amber-500'}`} />

            <CardContent className="flex items-start gap-4 p-5 pl-6">
              {/* Icon */}
              <div className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${
                p.difficulty === 'hard'
                  ? 'bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:text-rose-400'
                  : 'bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400'
              }`}>
                {p.difficulty === 'hard' ? <Rocket className="h-6 w-6" /> : <Code2 className="h-6 w-6" />}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold">{p.title}</h3>
                  <Badge variant="outline" className={`text-xs capitalize ${
                    p.difficulty === 'hard'
                      ? 'border-rose-200 text-rose-600 dark:border-rose-800 dark:text-rose-400'
                      : 'border-amber-200 text-amber-600 dark:border-amber-800 dark:text-amber-400'
                  }`}>
                    {p.difficulty}
                  </Badge>
                </div>

                <p className="text-sm text-muted-foreground leading-relaxed">{p.description}</p>

                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {p.techStack.map(t => (
                    <Badge key={t} variant="secondary" className="text-xs font-normal">{t}</Badge>
                  ))}
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> ~{p.estimatedHours}h</span>
                  {p.keySkills.slice(0, 3).map((s, i) => (
                    <span key={i} className="flex items-center gap-1"><Sparkles className="h-3 w-3" /> {s}</span>
                  ))}
                </div>
              </div>

              {/* Hover arrow */}
              <div className="self-center opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronDown className="h-5 w-5 text-primary rotate-[-90deg]" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {picking && (
        <div className="flex items-center justify-center gap-2 text-primary py-4">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm font-medium">Building your 7-day plan...</span>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Main component — orchestrates the 3 steps
   ═══════════════════════════════════════════════════════════════════════════ */
export function ProjectRoadmapShell() {
  const { toast } = useToast();

  // Step tracking
  type Step = 'form' | 'pick' | 'path';
  const [step, setStep] = useState<Step>('form');

  // Form state
  const [domain, setDomain] = useState('');

  // Suggestion state
  const [suggestions, setSuggestions] = useState<{ domain: string; projects: ProjectSuggestion[] } | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  // Plan state
  const [activeRoadmap, setActiveRoadmap] = useState<ProjectRoadmap | null>(null);
  const [planning, setPlanning] = useState(false);

  // Day detail modal
  const [selectedDay, setSelectedDay] = useState<RoadmapDay | null>(null);
  const [completing, setCompleting] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  // History
  const { data: historyData, refetch: refetchHistory } = useQuery({
    queryKey: ['project-roadmaps'],
    queryFn: async () => {
      const res = await projectRoadmapApi.list();
      return res.data.roadmaps || [];
    },
    staleTime: 5 * 60 * 1000,
  });
  const history = historyData || [];

  // Step 1: Suggest projects
  const handleSuggest = useCallback(async () => {
    if (!domain.trim()) {
      toast({ title: 'Enter a domain', description: 'Please specify which domain you want to learn.', variant: 'destructive' });
      return;
    }
    setSuggesting(true);
    try {
      const res = await projectRoadmapApi.suggest(domain.trim());
      if (res.data?.projects?.length) {
        setSuggestions(res.data);
        setStep('pick');
      }
    } catch (err: any) {
      toast({ title: 'Failed to get suggestions', description: typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Please try again.', variant: 'destructive' });
    } finally {
      setSuggesting(false);
    }
  }, [domain, toast]);

  // Step 2: Generate plan for chosen project
  const handlePick = useCallback(async (project: ProjectSuggestion) => {
    if (!suggestions) return;
    setPlanning(true);
    try {
      const res = await projectRoadmapApi.plan({
        domain: suggestions.domain,
        projectTitle: project.title,
        projectDescription: project.description,
        techStack: project.techStack,
      });
      if (res.data?.projectRoadmapId) {
        setActiveRoadmap(res.data);
        setStep('path');
        refetchHistory();
        toast({ title: 'Roadmap ready!', description: `7-day plan for "${project.title}" generated.` });
      }
    } catch (err: any) {
      toast({ title: 'Plan generation failed', description: typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Please try again.', variant: 'destructive' });
    } finally {
      setPlanning(false);
    }
  }, [suggestions, toast, refetchHistory]);

  // Mark day complete
  const handleDayComplete = useCallback(async (dayNum: number) => {
    if (!activeRoadmap) return;
    setCompleting(true);
    try {
      const res = await projectRoadmapApi.markDayComplete(activeRoadmap.projectRoadmapId, dayNum);
      setActiveRoadmap(res.data);
      // Update selected day too if modal is open
      const updated = res.data.days.find((d: RoadmapDay) => d.day === dayNum);
      if (updated) setSelectedDay(updated);
      refetchHistory();
      toast({ title: `Day ${dayNum} complete!`, description: 'Keep the momentum going!' });
    } catch (err: any) {
      toast({ title: 'Failed to update', description: typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Please try again.', variant: 'destructive' });
    } finally {
      setCompleting(false);
    }
  }, [activeRoadmap, toast, refetchHistory]);

  // Load from history
  const handleLoadRoadmap = useCallback(async (id: string) => {
    try {
      const res = await projectRoadmapApi.get(id);
      setActiveRoadmap(res.data);
      setStep('path');
    } catch {
      toast({ title: 'Failed to load roadmap', variant: 'destructive' });
    }
  }, [toast]);

  // Unlock all days
  const handleUnlockAll = useCallback(async () => {
    if (!activeRoadmap) return;
    setUnlocking(true);
    try {
      const res = await projectRoadmapApi.unlockAll(activeRoadmap.projectRoadmapId);
      setActiveRoadmap(res.data);
      toast({ title: 'All days unlocked!', description: 'You can now access any day in any order.' });
    } catch (err: any) {
      toast({ title: 'Failed to unlock', description: typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Please try again.', variant: 'destructive' });
    } finally {
      setUnlocking(false);
    }
  }, [activeRoadmap, toast]);

  // Delete roadmap
  const handleDelete = useCallback(async (id: string) => {
    setDeleting(id);
    try {
      await projectRoadmapApi.delete(id);
      refetchHistory();
      if (activeRoadmap?.projectRoadmapId === id) {
        setActiveRoadmap(null);
        setStep('form');
      }
      toast({ title: 'Roadmap deleted' });
    } catch (err: any) {
      toast({ title: 'Failed to delete', description: typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Please try again.', variant: 'destructive' });
    } finally {
      setDeleting(null);
    }
  }, [activeRoadmap, toast, refetchHistory]);

  /* ─── STEP 3: S-curve path ─────────────────────────────────────────────── */
  if (step === 'path' && activeRoadmap) {
    return (
      <>
        <DuolingoPath
          roadmap={activeRoadmap}
          onDayClick={(day) => setSelectedDay(day)}
          onComplete={handleDayComplete}
          onBack={() => { setStep('form'); setActiveRoadmap(null); }}
          onUnlockAll={handleUnlockAll}
          unlocking={unlocking}
        />
        {selectedDay && activeRoadmap && (() => {
          const dayIdx = selectedDay.day - 1;
          const prevDone = activeRoadmap.days.slice(0, dayIdx).every(d => d.completedAt);
          return (
            <DayDetailModal
              day={selectedDay}
              color={DAY_COLORS[(selectedDay.day - 1) % DAY_COLORS.length]}
              canComplete={prevDone}
              onClose={() => setSelectedDay(null)}
              onComplete={() => handleDayComplete(selectedDay.day)}
              completing={completing}
            />
          );
        })()}
      </>
    );
  }

  /* ─── STEP 2: Pick project ─────────────────────────────────────────────── */
  if (step === 'pick' && suggestions) {
    return (
      <ProjectPicker
        suggestions={suggestions}
        onPick={handlePick}
        picking={planning}
        onBack={() => setStep('form')}
      />
    );
  }

  /* ─── STEP 1: Domain + hours form ──────────────────────────────────────── */
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Hero */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-2">
          <Map className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-3xl font-bold tracking-tight">Project Roadmap</h2>
        <p className="text-muted-foreground max-w-lg mx-auto">
          Choose a domain and we&apos;ll suggest 3 real-world projects — pick one and get a day-by-day build plan!
        </p>
      </div>

      {/* Form */}
      <Card className="border-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            What do you want to build?
          </CardTitle>
          <CardDescription>Pick a domain to get started</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Domain input */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Domain / Area</label>
            <input
              type="text"
              value={domain}
              onChange={e => setDomain(e.target.value)}
              placeholder="e.g., Web Development, Machine Learning..."
              className="w-full rounded-xl border border-input px-4 py-3 text-sm bg-background transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40"
              onKeyDown={e => e.key === 'Enter' && handleSuggest()}
            />
            <div className="flex flex-wrap gap-2 pt-1">
              {DOMAIN_CHIPS.map(d => (
                <button
                  key={d}
                  onClick={() => setDomain(d)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-200 ${
                    domain === d
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-muted/50 text-muted-foreground border-border hover:bg-primary/10 hover:text-primary hover:border-primary/30'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Generate button */}
          <Button
            onClick={handleSuggest}
            disabled={suggesting || !domain.trim()}
            className="w-full h-12 text-base gap-2 rounded-xl"
            size="lg"
          >
            {suggesting ? (
              <><Loader2 className="h-5 w-5 animate-spin" /> Finding projects...</>
            ) : (
              <><Sparkles className="h-5 w-5" /> Suggest 3 Projects</>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Previous Roadmaps — always visible */}
      {history.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Previous Roadmaps ({history.length})
          </h3>
          <div className="space-y-2">
            {history.map(rm => {
              const pct = Math.round((rm.completedDays / rm.totalDays) * 100);
              return (
                <Card
                  key={rm.projectRoadmapId}
                  className="group cursor-pointer hover:shadow-md transition-all duration-200 hover:border-primary/30"
                  onClick={() => handleLoadRoadmap(rm.projectRoadmapId)}
                >
                  <CardContent className="flex items-center justify-between p-4 gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium truncate">{rm.projectTitle}</p>
                      <p className="text-xs text-muted-foreground">
                        {rm.completedDays}/{rm.totalDays} days • {rm.domain}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="w-20 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium tabular-nums w-8 text-right">{pct}%</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={(e) => { e.stopPropagation(); handleDelete(rm.projectRoadmapId); }}
                        disabled={deleting === rm.projectRoadmapId}
                      >
                        {deleting === rm.projectRoadmapId
                          ? <Loader2 className="h-4 w-4 animate-spin" />
                          : <Trash2 className="h-4 w-4" />
                        }
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

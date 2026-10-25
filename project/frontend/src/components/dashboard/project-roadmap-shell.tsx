'use client';

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Map, Loader2, Sparkles, Unlock, Trash2 } from 'lucide-react';
import {
  projectRoadmapApi,
  type ProjectRoadmap,
  type ProjectSuggestion,
  type RoadmapDay,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { DOMAIN_CHIPS, DAY_COLORS } from './project-roadmap/constants';
import { DuolingoPath } from './project-roadmap/duolingo-path';
import { DayDetailModal } from './project-roadmap/day-detail-modal';
import { ProjectPicker } from './project-roadmap/project-picker';

export function ProjectRoadmapShell() {
  const { toast } = useToast();

  // Step tracking
  type Step = 'form' | 'pick' | 'path';
  const [step, setStep] = useState<Step>('form');

  // Form state
  const [domain, setDomain] = useState('');

  // Suggestion state
  const [suggestions, setSuggestions] = useState<{
    domain: string;
    projects: ProjectSuggestion[];
  } | null>(null);
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
      toast({
        title: 'Enter a domain',
        description: 'Please specify which domain you want to learn.',
        variant: 'destructive',
      });
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
      toast({
        title: 'Failed to get suggestions',
        description:
          typeof err?.response?.data?.detail === 'string'
            ? err.response.data.detail
            : 'Please try again.',
        variant: 'destructive',
      });
    } finally {
      setSuggesting(false);
    }
  }, [domain, toast]);

  // Step 2: Generate plan for chosen project
  const handlePick = useCallback(
    async (project: ProjectSuggestion) => {
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
          toast({
            title: 'Roadmap ready!',
            description: `7-day plan for "${project.title}" generated.`,
          });
        }
      } catch (err: any) {
        toast({
          title: 'Plan generation failed',
          description:
            typeof err?.response?.data?.detail === 'string'
              ? err.response.data.detail
              : 'Please try again.',
          variant: 'destructive',
        });
      } finally {
        setPlanning(false);
      }
    },
    [suggestions, toast, refetchHistory]
  );

  // Mark day complete
  const handleDayComplete = useCallback(
    async (dayNum: number) => {
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
        toast({
          title: 'Failed to update',
          description:
            typeof err?.response?.data?.detail === 'string'
              ? err.response.data.detail
              : 'Please try again.',
          variant: 'destructive',
        });
      } finally {
        setCompleting(false);
      }
    },
    [activeRoadmap, toast, refetchHistory]
  );

  // Load from history
  const handleLoadRoadmap = useCallback(
    async (id: string) => {
      try {
        const res = await projectRoadmapApi.get(id);
        setActiveRoadmap(res.data);
        setStep('path');
      } catch {
        toast({ title: 'Failed to load roadmap', variant: 'destructive' });
      }
    },
    [toast]
  );

  // Unlock all days
  const handleUnlockAll = useCallback(async () => {
    if (!activeRoadmap) return;
    setUnlocking(true);
    try {
      const res = await projectRoadmapApi.unlockAll(activeRoadmap.projectRoadmapId);
      setActiveRoadmap(res.data);
      toast({
        title: 'All days unlocked!',
        description: 'You can now access any day in any order.',
      });
    } catch (err: any) {
      toast({
        title: 'Failed to unlock',
        description:
          typeof err?.response?.data?.detail === 'string'
            ? err.response.data.detail
            : 'Please try again.',
        variant: 'destructive',
      });
    } finally {
      setUnlocking(false);
    }
  }, [activeRoadmap, toast]);

  // Delete roadmap
  const handleDelete = useCallback(
    async (id: string) => {
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
        toast({
          title: 'Failed to delete',
          description:
            typeof err?.response?.data?.detail === 'string'
              ? err.response.data.detail
              : 'Please try again.',
          variant: 'destructive',
        });
      } finally {
        setDeleting(null);
      }
    },
    [activeRoadmap, toast, refetchHistory]
  );

  /* ─── STEP 3: S-curve path ─────────────────────────────────────────────── */
  if (step === 'path' && activeRoadmap) {
    return (
      <>
        <DuolingoPath
          roadmap={activeRoadmap}
          onDayClick={(day) => setSelectedDay(day)}
          onComplete={handleDayComplete}
          onBack={() => {
            setStep('form');
            setActiveRoadmap(null);
          }}
          onUnlockAll={handleUnlockAll}
          unlocking={unlocking}
        />
        {selectedDay &&
          activeRoadmap &&
          (() => {
            const dayIdx = selectedDay.day - 1;
            const prevDone = activeRoadmap.days.slice(0, dayIdx).every((d) => d.completedAt);
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
          Choose a domain and we&apos;ll suggest 3 real-world projects — pick one and get a
          day-by-day build plan!
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
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g., Web Development, Machine Learning..."
              className="w-full rounded-xl border border-input px-4 py-3 text-sm bg-background transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40"
              onKeyDown={(e) => e.key === 'Enter' && handleSuggest()}
            />
            <div className="flex flex-wrap gap-2 pt-1">
              {DOMAIN_CHIPS.map((d) => (
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
              <>
                <Loader2 className="h-5 w-5 animate-spin" /> Finding projects...
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5" /> Suggest 3 Projects
              </>
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
            {history.map((rm) => {
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
                      <span className="text-xs font-medium tabular-nums w-8 text-right">
                        {pct}%
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(rm.projectRoadmapId);
                        }}
                        disabled={deleting === rm.projectRoadmapId}
                      >
                        {deleting === rm.projectRoadmapId ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
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

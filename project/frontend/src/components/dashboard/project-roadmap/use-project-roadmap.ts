import { useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  projectRoadmapApi,
  type ProjectRoadmap,
  type ProjectSuggestion,
  type RoadmapDay,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

export type RoadmapStep = 'form' | 'pick' | 'path';

/**
 * State and API calls behind the Project Roadmap tab: suggest projects for a
 * domain, plan one as a seven-day roadmap, then complete, unlock, reload or
 * delete roadmaps.
 */
export function useProjectRoadmap() {
  const { toast } = useToast();

  const [step, setStep] = useState<RoadmapStep>('form');

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
  const handleSuggest = useCallback(
    async (domain: string) => {
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
      } catch (err: unknown) {
        toast({
          title: 'Failed to get suggestions',
          description: apiErrorDetail(err, 'Please try again.'),
          variant: 'destructive',
        });
      } finally {
        setSuggesting(false);
      }
    },
    [toast]
  );

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
      } catch (err: unknown) {
        toast({
          title: 'Plan generation failed',
          description: apiErrorDetail(err, 'Please try again.'),
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
      } catch (err: unknown) {
        toast({
          title: 'Failed to update',
          description: apiErrorDetail(err, 'Please try again.'),
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
    } catch (err: unknown) {
      toast({
        title: 'Failed to unlock',
        description: apiErrorDetail(err, 'Please try again.'),
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
      } catch (err: unknown) {
        toast({
          title: 'Failed to delete',
          description: apiErrorDetail(err, 'Please try again.'),
          variant: 'destructive',
        });
      } finally {
        setDeleting(null);
      }
    },
    [activeRoadmap, toast, refetchHistory]
  );

  const closeRoadmap = useCallback(() => {
    setStep('form');
    setActiveRoadmap(null);
  }, []);

  return {
    step,
    setStep,
    suggestions,
    suggesting,
    activeRoadmap,
    planning,
    selectedDay,
    setSelectedDay,
    completing,
    unlocking,
    deleting,
    history,
    suggest: handleSuggest,
    pick: handlePick,
    completeDay: handleDayComplete,
    loadRoadmap: handleLoadRoadmap,
    unlockAll: handleUnlockAll,
    deleteRoadmap: handleDelete,
    closeRoadmap,
  };
}

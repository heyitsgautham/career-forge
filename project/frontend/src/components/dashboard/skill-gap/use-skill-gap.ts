import { useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { roadmapApi, skillGapApi, type Roadmap, type SkillGapReport } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

/**
 * Roles, the gap report for one role, and the learning roadmap built from that
 * report, with the API calls that produce them.
 */
export function useSkillGap() {
  const { toast } = useToast();

  // State
  const [report, setReport] = useState<SkillGapReport | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [generatingRoadmap, setGeneratingRoadmap] = useState(false);
  const [roadmapOpen, setRoadmapOpen] = useState(true);

  // Load roles via React Query (static data, long cache)
  const { data: roles = [], isLoading: loadingRoles } = useQuery({
    queryKey: ['skill-gap-roles'],
    queryFn: async () => {
      const res = await skillGapApi.getRoles();
      return res.data.roles || [];
    },
    staleTime: 60 * 60 * 1000, // 1 hour — static data
    gcTime: 2 * 60 * 60 * 1000, // 2 hours
  });

  // Run analysis
  const handleAnalyse = useCallback(
    async (selectedRole: string | null) => {
      if (!selectedRole) return;
      setAnalysing(true);
      setReport(null);
      setRoadmap(null);

      try {
        const res = await skillGapApi.analyse(selectedRole);
        if (res.data && res.data.reportId) {
          setReport(res.data);
          toast({
            title: 'Analysis complete!',
            description: `Overall fit: ${res.data.overallFitPercent}%`,
          });
        } else {
          toast({
            title: 'No results',
            description: 'Could not compute gap analysis.',
            variant: 'destructive',
          });
        }
      } catch (err: unknown) {
        toast({
          title: 'Analysis failed',
          description: apiErrorDetail(err, 'An error occurred.'),
          variant: 'destructive',
        });
      } finally {
        setAnalysing(false);
      }
    },
    [toast]
  );

  // Generate roadmap
  const handleGenerateRoadmap = useCallback(
    async (selectedRole: string | null) => {
      if (!selectedRole || !report) return;
      setGeneratingRoadmap(true);

      try {
        const res = await roadmapApi.generate(selectedRole, report.reportId);
        if (res.data && res.data.roadmapId) {
          setRoadmap(res.data);
          setRoadmapOpen(true);
          toast({ title: 'Roadmap generated!' });
        }
      } catch (err: unknown) {
        toast({
          title: 'Roadmap generation failed',
          description: apiErrorDetail(err, 'An error occurred.'),
          variant: 'destructive',
        });
      } finally {
        setGeneratingRoadmap(false);
      }
    },
    [report, toast]
  );

  // Mark milestone complete
  const handleMarkComplete = useCallback(
    async (week: number) => {
      if (!roadmap) return;
      try {
        const res = await roadmapApi.markComplete(roadmap.roadmapId, week);
        if (res.data) {
          setRoadmap(res.data);
          toast({ title: `Week ${week} completed!` });
        }
      } catch {
        toast({ title: 'Failed to update milestone', variant: 'destructive' });
      }
    },
    [roadmap, toast]
  );

  return {
    roles,
    loadingRoles,
    report,
    roadmap,
    analysing,
    generatingRoadmap,
    roadmapOpen,
    toggleRoadmap: () => setRoadmapOpen((open) => !open),
    analyse: handleAnalyse,
    generateRoadmap: handleGenerateRoadmap,
    markWeekComplete: handleMarkComplete,
  };
}

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  applicationsApi,
  jobMatchApi,
  resumesApi,
  tailorApi,
  type Application,
  type TrackingStatuses,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { KANBAN_STATUSES } from './constants';
import { getUserId } from './format';
import { tailoredResumeMap, type ResumeSummary } from './tailored-resumes';

/**
 * Loads everything the Job Scout tab shows and owns its two writes.
 *
 * `track` saves a job's status and mirrors Kanban statuses into the Apply &
 * Track pipeline. `tailor` generates a tailored resume for a job.
 */
export function useJobScoutData() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Track freshly-tailored resumes in this session (optimistic, before refetch)
  const [freshTailored, setFreshTailored] = useState<Record<string, string>>({});
  const [tailoringJobId, setTailoringJobId] = useState<string | null>(null);

  const { data: userResumes = [] } = useQuery({
    queryKey: ['resumes'],
    queryFn: async () => (await resumesApi.list()).data as ResumeSummary[],
    staleTime: 2 * 60_000,
  });

  const tailoredResumes = useMemo(
    () => tailoredResumeMap(userResumes, freshTailored),
    [userResumes, freshTailored]
  );

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', 'matches'],
    queryFn: async () => (await jobMatchApi.list()).data,
    refetchInterval: 5 * 60_000, // refresh every 5 minutes
  });

  const { data: stats } = useQuery({
    queryKey: ['jobs', 'stats'],
    queryFn: async () => (await jobMatchApi.stats()).data,
    refetchInterval: 5 * 60_000,
  });

  const { data: scheduler } = useQuery({
    queryKey: ['jobs', 'scheduler'],
    queryFn: async () => (await jobMatchApi.schedulerStatus()).data,
    refetchInterval: 30_000, // every 30s for countdown accuracy
  });

  const { data: tracking = {} } = useQuery<TrackingStatuses>({
    queryKey: ['jobs', 'tracking'],
    queryFn: async () => (await jobMatchApi.getTracking()).data,
  });

  // ── Applications query (for cross-page sync) ───────────────────────────

  const userId = typeof window !== 'undefined' ? getUserId() : '';

  const { data: applications = [] } = useQuery<Application[]>({
    queryKey: ['applications', userId],
    queryFn: async () => {
      if (!userId) return [];
      return (await applicationsApi.list(userId)).data;
    },
    enabled: !!userId,
    staleTime: 30_000,
  });

  // jobId → existing Application record (for upsert logic)
  const appByJobId = useMemo(() => {
    const m: Record<string, Application> = {};
    for (const a of applications) m[a.jobId] = a;
    return m;
  }, [applications]);

  // Keep refs so the async onSuccess closure always sees fresh data
  const appByJobIdRef = useRef(appByJobId);
  useEffect(() => {
    appByJobIdRef.current = appByJobId;
  }, [appByJobId]);
  const jobsRef = useRef(jobs);
  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  const trackMutation = useMutation({
    mutationFn: async ({ jobId, status }: { jobId: string; status: string }) => {
      await jobMatchApi.track(jobId, status);
    },
    onSuccess: async (_, { jobId, status }) => {
      queryClient.invalidateQueries({ queryKey: ['jobs', 'tracking'] });

      // Sync to Apply & Track pipeline for kanban-visible statuses
      if (KANBAN_STATUSES.has(status)) {
        const existingApp = appByJobIdRef.current[jobId];
        try {
          if (existingApp) {
            await applicationsApi.update(existingApp.applicationId, {
              status: status as Application['status'],
            });
          } else {
            const job = jobsRef.current.find((j) => j.jobId === jobId);
            await applicationsApi.create({
              jobId,
              companyName: job?.company,
              roleTitle: job?.title,
              url: job?.url,
              status,
            });
          }
          queryClient.invalidateQueries({ queryKey: ['applications'] });
        } catch {
          // sync failure is non-critical — pipeline stays eventually consistent
        }
      }
    },
    onError: () => {
      toast({ title: 'Failed to update status', variant: 'destructive' });
    },
  });

  const tailorMutation = useMutation({
    mutationFn: async (jobId: string) => {
      setTailoringJobId(jobId);
      return (await tailorApi.generate(jobId)).data;
    },
    onSuccess: (data) => {
      setTailoringJobId(null);
      // Optimistically track the new tailored resume
      setFreshTailored((prev) => ({ ...prev, [data.jobId]: data.resumeId }));
      // Invalidate resumes list so the real data catches up
      queryClient.invalidateQueries({ queryKey: ['resumes'] });

      if (data.compilationError) {
        toast({
          title: 'Resume tailored but PDF compilation failed',
          description: 'You can still open it in the editor to fix issues.',
          variant: 'destructive',
        });
        return;
      }
      toast({
        title: 'Tailored resume generated!',
        description: data.matchKeywords?.length
          ? `Matched ${data.matchKeywords.length} keywords. Click "Editor" to refine.`
          : 'Resume ready — click "Editor" to open.',
      });
    },
    onError: () => {
      setTailoringJobId(null);
      toast({ title: 'Failed to generate tailored resume', variant: 'destructive' });
    },
  });

  return {
    jobs,
    jobsLoading,
    stats,
    scheduler,
    tracking,
    tailoredResumes,
    tailoringJobId,
    track: (jobId: string, status: string) => trackMutation.mutate({ jobId, status }),
    tailor: (jobId: string) => tailorMutation.mutate(jobId),
  };
}

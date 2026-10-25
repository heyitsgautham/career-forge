import { useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { applicationsApi, jobMatchApi, type Application } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { currentUserId } from '@/lib/session';

export interface NewApplication {
  jobId: string;
  companyName: string;
  roleTitle: string;
  notes: string;
  url: string;
}

/**
 * The user's applications and the scouted jobs to pick from, with create,
 * move and delete. Moving an application also updates its Job Scout status.
 */
export function useApplications(onCreated: () => void) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const userId = currentUserId();

  // Fetch applications
  const { data: applications = [], isLoading } = useQuery({
    queryKey: ['applications', userId],
    queryFn: async () => {
      if (!userId) return [];
      const res = await applicationsApi.list(userId);
      return res.data;
    },
    enabled: !!userId,
    staleTime: 15_000,
  });

  // Fetch jobs (for job selector in tailor panel + add modal)
  const { data: jobs = [] } = useQuery({
    queryKey: ['job-scout-matches'],
    queryFn: async () => {
      const res = await jobMatchApi.list();
      return res.data;
    },
    staleTime: 30_000,
  });

  // Create application mutation
  const createMutation = useMutation({
    mutationFn: (data: NewApplication) => applicationsApi.create(data),
    onSuccess: () => {
      onCreated();
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      toast({ title: 'Application added!' });
    },
    onError: (err: unknown) => {
      toast({
        title: 'Failed to create application',
        description: apiErrorDetail(err, 'Something went wrong'),
        variant: 'destructive',
      });
    },
  });

  // Update application mutation (for DnD status changes)
  const updateMutation = useMutation({
    mutationFn: (params: { applicationId: string; status: string }) =>
      applicationsApi.update(params.applicationId, {
        status: params.status as Application['status'],
      }),
    onError: (err: unknown) => {
      // Rollback on error — refetch
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      toast({
        title: 'Failed to update status',
        description: apiErrorDetail(err, 'Could not move application'),
        variant: 'destructive',
      });
    },
  });

  // Delete application mutation
  const deleteMutation = useMutation({
    mutationFn: (applicationId: string) => applicationsApi.delete(applicationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      toast({ title: 'Application removed' });
    },
    onError: (err: unknown) => {
      toast({
        title: 'Failed to remove application',
        description: apiErrorDetail(err, 'Please try again.'),
        variant: 'destructive',
      });
    },
  });

  // Optimistic status change, then sync the tracking status back to Job Scout
  const moveApplication = useCallback(
    (applicationId: string, newStatus: string) => {
      // Find the moved application to get its jobId for cross-page sync
      const movedApp = applications.find((a) => a.applicationId === applicationId);

      // Optimistic update in cache
      queryClient.setQueryData(['applications', userId], (old: Application[] | undefined) => {
        if (!old) return old;
        return old.map((app) =>
          app.applicationId === applicationId
            ? { ...app, status: newStatus as Application['status'] }
            : app
        );
      });

      // Persist application status to API
      updateMutation.mutate({ applicationId, status: newStatus });

      // Sync tracking status back to Job Scout (fire-and-forget)
      if (movedApp && !movedApp.jobId.startsWith('manual-')) {
        jobMatchApi
          .track(movedApp.jobId, newStatus)
          .then(() => queryClient.invalidateQueries({ queryKey: ['jobs', 'tracking'] }))
          .catch(() => {
            /* sync failure is non-critical */
          });
      }
    },
    [queryClient, userId, updateMutation, applications]
  );

  const removeApplication = useCallback(
    (applicationId: string) => {
      deleteMutation.mutate(applicationId);
    },
    [deleteMutation]
  );

  return {
    applications,
    isLoading,
    jobs,
    createApplication: (data: NewApplication) => createMutation.mutate(data),
    creating: createMutation.isPending,
    moveApplication,
    removeApplication,
  };
}

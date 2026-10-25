'use client';

import { useState, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DragDropContext, type DropResult } from '@hello-pangea/dnd';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Kanban, Plus, Briefcase } from 'lucide-react';
import { applicationsApi, jobMatchApi, type Application, type Job } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { COLUMNS, getUserId } from './apply/helpers';
import { KanbanColumn, StatsBar } from './apply/kanban';
import { AddApplicationModal } from './apply/add-application-modal';

/* ─── Main Component ─────────────────────────────────────────────────────── */

export function ApplyTrackShell() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const userId = getUserId();

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

  // Group applications by status for Kanban columns
  const columnApps = useMemo(() => {
    const grouped: Record<string, Application[]> = {};
    for (const col of COLUMNS) {
      grouped[col.key] = [];
    }
    for (const app of applications) {
      const key = app.status as string;
      if (grouped[key]) {
        grouped[key].push(app);
      } else {
        // Status not in columns (saved, viewed) — put in "applied"
        grouped['applied']?.push(app);
      }
    }
    return grouped;
  }, [applications]);

  // Create application mutation
  const createMutation = useMutation({
    mutationFn: (data: {
      jobId: string;
      companyName: string;
      roleTitle: string;
      notes: string;
      url: string;
    }) => applicationsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      setShowAddModal(false);
      toast({ title: 'Application added!' });
    },
    onError: (err: any) => {
      toast({
        title: 'Failed to create application',
        description: err?.response?.data?.detail || 'Something went wrong',
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
    onError: (err: any) => {
      // Rollback on error — refetch
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      toast({
        title: 'Failed to update status',
        description: err?.response?.data?.detail || 'Could not move application',
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
  });

  // DnD handler — optimistic update + sync to Job Scout tracking
  const handleDragEnd = useCallback(
    (result: DropResult) => {
      const { draggableId, source, destination } = result;
      if (!destination || destination.droppableId === source.droppableId) return;

      const newStatus = destination.droppableId;

      // Find the dragged application to get its jobId for cross-page sync
      const draggedApp = applications.find((a) => a.applicationId === draggableId);

      // Optimistic update in cache
      queryClient.setQueryData(['applications', userId], (old: Application[] | undefined) => {
        if (!old) return old;
        return old.map((app) =>
          app.applicationId === draggableId
            ? { ...app, status: newStatus as Application['status'] }
            : app
        );
      });

      // Persist application status to API
      updateMutation.mutate({ applicationId: draggableId, status: newStatus });

      // Sync tracking status back to Job Scout (fire-and-forget)
      if (draggedApp && !draggedApp.jobId.startsWith('manual-')) {
        jobMatchApi
          .track(draggedApp.jobId, newStatus)
          .then(() => queryClient.invalidateQueries({ queryKey: ['jobs', 'tracking'] }))
          .catch(() => {
            /* sync failure is non-critical */
          });
      }
    },
    [queryClient, userId, updateMutation, applications]
  );

  const handleDelete = useCallback(
    (applicationId: string) => {
      deleteMutation.mutate(applicationId);
    },
    [deleteMutation]
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Apply &amp; Track</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Track your job applications and manage your pipeline
          </p>
        </div>
        <Button
          variant="outline"
          className="gap-2 shrink-0"
          onClick={() => setShowAddModal(true)}
          aria-label="Add application"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add Application
        </Button>
      </div>

      {/* Stats bar */}
      <StatsBar applications={applications} />

      {/* Application Pipeline — full-width Kanban */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Kanban className="h-4 w-4 text-primary" aria-hidden="true" />
            Application Pipeline
          </CardTitle>
          <CardDescription>
            Drag applications between columns to update status · synced with Job Scout
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DragDropContext onDragEnd={handleDragEnd}>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {COLUMNS.map((col) => (
                <KanbanColumn
                  key={col.key}
                  columnKey={col.key}
                  label={col.label}
                  icon={col.icon}
                  color={col.color}
                  bg={col.bg}
                  apps={columnApps[col.key] || []}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          </DragDropContext>

          {!isLoading && applications.length === 0 && (
            <div className="mt-6 flex flex-col items-center gap-2 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Briefcase className="h-5 w-5 text-primary" aria-hidden="true" />
              </div>
              <p className="text-sm text-muted-foreground max-w-sm">
                Your application tracker is empty. Add applications manually or track jobs from Job
                Scout.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Application Modal */}
      <AddApplicationModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSubmit={(data) => createMutation.mutate(data)}
        isSubmitting={createMutation.isPending}
        jobs={jobs}
      />
    </div>
  );
}

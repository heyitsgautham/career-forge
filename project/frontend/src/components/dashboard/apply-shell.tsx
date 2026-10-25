'use client';

import { useState, useCallback, useMemo } from 'react';
import { DragDropContext, type DropResult } from '@hello-pangea/dnd';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Kanban, Plus, Briefcase } from 'lucide-react';
import { COLUMNS, groupByColumn } from './apply/helpers';
import { KanbanColumn, StatsBar } from './apply/kanban';
import { AddApplicationModal } from './apply/add-application-modal';
import { useApplications } from './apply/use-applications';

export function ApplyTrackShell() {
  const [showAddModal, setShowAddModal] = useState(false);
  const {
    applications,
    isLoading,
    jobs,
    createApplication,
    creating,
    moveApplication,
    removeApplication,
  } = useApplications(() => setShowAddModal(false));

  const columnApps = useMemo(() => groupByColumn(applications), [applications]);

  const handleDragEnd = useCallback(
    ({ draggableId, source, destination }: DropResult) => {
      if (!destination || destination.droppableId === source.droppableId) return;
      moveApplication(draggableId, destination.droppableId);
    },
    [moveApplication]
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
                  onDelete={removeApplication}
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
        onSubmit={createApplication}
        isSubmitting={creating}
        jobs={jobs}
      />
    </div>
  );
}

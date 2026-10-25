'use client';

import { useMemo } from 'react';
import { Droppable, Draggable } from '@hello-pangea/dnd';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Kanban, FileText, Trash2, Calendar, Building2, BarChart3 } from 'lucide-react';
import { type Application } from '@/lib/api';
import { formatDate } from './helpers';

/* ─── Application Card (Draggable) ───────────────────────────────────────── */

export function ApplicationCard({
  app,
  index,
  onDelete,
}: {
  app: Application;
  index: number;
  onDelete: (id: string) => void;
}) {
  return (
    <Draggable draggableId={app.applicationId} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={`rounded-lg border bg-card p-3 space-y-1.5 transition-all duration-200 ${
            snapshot.isDragging ? 'shadow-lg ring-2 ring-primary/30 -rotate-1' : 'hover:shadow-sm'
          }`}
        >
          <div className="flex items-start justify-between gap-1">
            <div className="min-w-0 flex-1">
              <h4 className="text-sm font-semibold truncate">{app.roleTitle}</h4>
              <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                <Building2 className="h-3 w-3 shrink-0" aria-hidden="true" />
                {app.companyName}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(app.applicationId);
              }}
              aria-label="Delete application"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-0.5">
              <Calendar className="h-3 w-3" aria-hidden="true" />
              {formatDate(app.appliedAt)}
            </span>
            {app.resumeId && (
              <span className="flex items-center gap-0.5 text-primary">
                <FileText className="h-3 w-3" aria-hidden="true" />
                Resume
              </span>
            )}
          </div>

          {app.notes && <p className="text-xs text-muted-foreground line-clamp-2">{app.notes}</p>}
        </div>
      )}
    </Draggable>
  );
}

/* ─── Kanban Column ──────────────────────────────────────────────────────── */

export function KanbanColumn({
  columnKey,
  label,
  icon: Icon,
  color,
  bg,
  apps,
  onDelete,
}: {
  columnKey: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bg: string;
  apps: Application[];
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex-1 min-w-[200px]">
      <div className="flex items-center gap-2 mb-3 px-1">
        <div className={`flex items-center justify-center h-6 w-6 rounded ${bg}`}>
          <Icon className={`h-3.5 w-3.5 ${color}`} aria-hidden="true" />
        </div>
        <span className="text-sm font-semibold">{label}</span>
        <Badge
          variant="secondary"
          className="ml-auto text-xs px-1.5 font-mono"
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          {apps.length}
        </Badge>
      </div>

      <Droppable droppableId={columnKey}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={`min-h-[180px] rounded-lg border border-dashed p-2 space-y-2 transition-colors ${
              snapshot.isDraggingOver ? 'border-primary/50 bg-primary/5' : 'border-border/50'
            }`}
          >
            {apps.map((app, idx) => (
              <ApplicationCard key={app.applicationId} app={app} index={idx} onDelete={onDelete} />
            ))}
            {provided.placeholder}
            {apps.length === 0 && !snapshot.isDraggingOver && (
              <p className="text-xs text-muted-foreground text-center py-6">
                Drag applications here
              </p>
            )}
          </div>
        )}
      </Droppable>
    </div>
  );
}

/* ─── Stats Bar ──────────────────────────────────────────────────────────── */

export function StatsBar({ applications }: { applications: Application[] }) {
  const counts = useMemo(() => {
    const c: Record<string, number> = { applied: 0, interviewing: 0, offered: 0, rejected: 0 };
    for (const app of applications) {
      if (app.status in c) c[app.status]++;
    }
    return c;
  }, [applications]);

  if (applications.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-3 text-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
      <div className="flex items-center gap-1.5">
        <BarChart3 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">Total:</span>
        <span className="font-semibold">{applications.length}</span>
      </div>
      <span className="text-primary font-medium">{counts.applied} Applied</span>
      <span className="text-muted-foreground">&middot;</span>
      <span className="text-[hsl(var(--accent))] font-medium">
        {counts.interviewing} Interviewing
      </span>
      <span className="text-muted-foreground">&middot;</span>
      <span className="text-[hsl(var(--success))] font-medium">{counts.offered} Offer</span>
      <span className="text-muted-foreground">&middot;</span>
      <span className="text-destructive font-medium">{counts.rejected} Rejected</span>
    </div>
  );
}

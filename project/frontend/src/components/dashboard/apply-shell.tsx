'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DragDropContext,
  Droppable,
  Draggable,
  type DropResult,
} from '@hello-pangea/dnd';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Send,
  Kanban,
  Plus,
  FileText,
  CheckCircle2,
  XCircle,
  PhoneCall,
  Loader2,
  Trash2,
  Calendar,
  Building2,
  Briefcase,
  X,
  BarChart3,
} from 'lucide-react';
import {
  applicationsApi,
  jobMatchApi,
  type Application,
  type Job,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

/* ─── Constants ──────────────────────────────────────────────────────────── */

const COLUMNS = [
  { key: 'applied', label: 'Applied', icon: Send, color: 'text-primary', bg: 'bg-primary/10' },
  { key: 'interviewing', label: 'Interviewing', icon: PhoneCall, color: 'text-[hsl(var(--accent))]', bg: 'bg-[hsl(var(--accent))]/10' },
  { key: 'offered', label: 'Offer', icon: CheckCircle2, color: 'text-[hsl(var(--success))]', bg: 'bg-[hsl(var(--success))]/10' },
  { key: 'rejected', label: 'Rejected', icon: XCircle, color: 'text-destructive', bg: 'bg-destructive/10' },
] as const;

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function getUserId(): string {
  if (typeof window === 'undefined') return '';
  try {
    const token = localStorage.getItem('token');
    if (!token) return '';
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub || '';
  } catch {
    return '';
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso.slice(0, 10);
  }
}

/* ─── Application Card (Draggable) ───────────────────────────────────────── */

function ApplicationCard({
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

          {app.notes && (
            <p className="text-xs text-muted-foreground line-clamp-2">{app.notes}</p>
          )}
        </div>
      )}
    </Draggable>
  );
}

/* ─── Kanban Column ──────────────────────────────────────────────────────── */

function KanbanColumn({
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
              snapshot.isDraggingOver
                ? 'border-primary/50 bg-primary/5'
                : 'border-border/50'
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

function StatsBar({ applications }: { applications: Application[] }) {
  const counts = useMemo(() => {
    const c: Record<string, number> = { applied: 0, interviewing: 0, offered: 0, rejected: 0 };
    for (const app of applications) {
      if (app.status in c) c[app.status]++;
    }
    return c;
  }, [applications]);

  if (applications.length === 0) return null;

  return (
    <div
      className="flex flex-wrap gap-3 text-sm"
      style={{ fontVariantNumeric: 'tabular-nums' }}
    >
      <div className="flex items-center gap-1.5">
        <BarChart3 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">Total:</span>
        <span className="font-semibold">{applications.length}</span>
      </div>
      <span className="text-primary font-medium">{counts.applied} Applied</span>
      <span className="text-muted-foreground">&middot;</span>
      <span className="text-[hsl(var(--accent))] font-medium">{counts.interviewing} Interviewing</span>
      <span className="text-muted-foreground">&middot;</span>
      <span className="text-[hsl(var(--success))] font-medium">{counts.offered} Offer</span>
      <span className="text-muted-foreground">&middot;</span>
      <span className="text-destructive font-medium">{counts.rejected} Rejected</span>
    </div>
  );
}

/* ─── Add Application Modal ──────────────────────────────────────────────── */

function AddApplicationModal({
  open,
  onClose,
  onSubmit,
  isSubmitting,
  jobs,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: {
    jobId: string;
    companyName: string;
    roleTitle: string;
    notes: string;
    url: string;
  }) => void;
  isSubmitting: boolean;
  jobs: Job[];
}) {
  const [selectedJobId, setSelectedJobId] = useState('');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [notes, setNotes] = useState('');
  const [url, setUrl] = useState('');
  const [isDirty, setIsDirty] = useState(false);

  // Auto-fill from selected job
  useEffect(() => {
    if (selectedJobId) {
      const job = jobs.find((j) => j.jobId === selectedJobId);
      if (job) {
        setCompany(job.company);
        setRole(job.title);
        if (job.url) setUrl(job.url);
      }
    }
  }, [selectedJobId, jobs]);

  const handleClose = () => {
    if (isDirty) {
      if (!confirm('You have unsaved changes. Discard?')) return;
    }
    onClose();
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-label="Add application"
    >
      <Card className="w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Add Application</h3>
            <Button variant="ghost" size="icon" onClick={handleClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Job selection (optional) */}
          {jobs.length > 0 && (
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="add-app-job">
                Link to Job (optional)
              </label>
              <select
                id="add-app-job"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={selectedJobId}
                onChange={(e) => {
                  setSelectedJobId(e.target.value);
                  setIsDirty(true);
                }}
              >
                <option value="">None — manual entry</option>
                {jobs.map((j) => (
                  <option key={j.jobId} value={j.jobId}>
                    {j.company} — {j.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="add-app-company">
                Company *
              </label>
              <Input
                id="add-app-company"
                value={company}
                onChange={(e) => { setCompany(e.target.value); setIsDirty(true); }}
                placeholder="e.g. Stripe"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="add-app-role">
                Role *
              </label>
              <Input
                id="add-app-role"
                value={role}
                onChange={(e) => { setRole(e.target.value); setIsDirty(true); }}
                placeholder="e.g. Backend SDE"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground" htmlFor="add-app-url">
              Application URL
            </label>
            <Input
              id="add-app-url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setIsDirty(true); }}
              placeholder="https://..."
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground" htmlFor="add-app-notes">
              Notes
            </label>
            <Textarea
              id="add-app-notes"
              value={notes}
              onChange={(e) => { setNotes(e.target.value); setIsDirty(true); }}
              placeholder="Applied via referral, etc."
              className="min-h-[60px]"
            />
          </div>

          <Button
            className="w-full gap-2"
            disabled={isSubmitting || !company.trim() || !role.trim()}
            onClick={() => {
              onSubmit({
                jobId: selectedJobId || `manual-${Date.now()}`,
                companyName: company,
                roleTitle: role,
                notes,
                url,
              });
            }}
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Plus className="h-4 w-4" aria-hidden="true" />
            )}
            {isSubmitting ? 'Creating...' : 'Add Application'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

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
      applicationsApi.update(params.applicationId, { status: params.status as Application['status'] }),
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
      queryClient.setQueryData(
        ['applications', userId],
        (old: Application[] | undefined) => {
          if (!old) return old;
          return old.map((app) =>
            app.applicationId === draggableId
              ? { ...app, status: newStatus as Application['status'] }
              : app
          );
        }
      );

      // Persist application status to API
      updateMutation.mutate({ applicationId: draggableId, status: newStatus });

      // Sync tracking status back to Job Scout (fire-and-forget)
      if (draggedApp && !draggedApp.jobId.startsWith('manual-')) {
        jobMatchApi.track(draggedApp.jobId, newStatus)
          .then(() => queryClient.invalidateQueries({ queryKey: ['jobs', 'tracking'] }))
          .catch(() => { /* sync failure is non-critical */ });
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
                Your application tracker is empty. Add applications manually or track jobs from Job Scout.
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

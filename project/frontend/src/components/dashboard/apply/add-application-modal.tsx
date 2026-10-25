'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Plus, Loader2, X } from 'lucide-react';
import { type Application, type Job } from '@/lib/api';

/* ─── Add Application Modal ──────────────────────────────────────────────── */

export function AddApplicationModal({
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
              <label
                className="text-xs font-medium text-muted-foreground"
                htmlFor="add-app-company"
              >
                Company *
              </label>
              <Input
                id="add-app-company"
                value={company}
                onChange={(e) => {
                  setCompany(e.target.value);
                  setIsDirty(true);
                }}
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
                onChange={(e) => {
                  setRole(e.target.value);
                  setIsDirty(true);
                }}
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
              onChange={(e) => {
                setUrl(e.target.value);
                setIsDirty(true);
              }}
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
              onChange={(e) => {
                setNotes(e.target.value);
                setIsDirty(true);
              }}
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

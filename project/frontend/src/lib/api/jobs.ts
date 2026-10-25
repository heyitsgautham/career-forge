import { api } from './client';
import { z } from 'zod';
import { JobSchema, validated } from './schemas';
import type { Job, Application, SchedulerStatus, TrackingStatuses, TailorResponse } from './types';

// ─── Job Descriptions API ─────────────────────────────────────────────────────

export const jobsApi = {
  list: () => api.get('/api/jobs'),

  create: (data: { title: string; company: string; raw_text: string; url?: string }) =>
    api.post('/api/jobs', data),

  delete: (id: string) => api.delete(`/api/jobs/${id}`),

  analyze: (id: string) => api.post(`/api/jobs/${id}/analyze`),
};

// ─── Job Matching API (M4 — Job Scout v2) ────────────────────────────────────

export const jobMatchApi = {
  /** List all shared jobs (sorted by date) */
  list: () => api.get<Job[]>('/api/jobs/matches').then(validated(z.array(JobSchema))),

  /** Get summary stats (includes newToday & lastScrape) */
  stats: () =>
    api.get<{
      totalJobs: number;
      analyzedJobs: number;
      averageMatch: number | null;
      topCategories: Array<{ category: string; count: number }>;
      matchDistribution: Record<string, number>;
      newToday: number;
      lastScrape: SchedulerStatus['lastScrape'];
    }>('/api/jobs/stats'),

  /** Scheduler status */
  schedulerStatus: () => api.get<SchedulerStatus>('/api/jobs/scheduler/status'),

  /** Track a job (set status) */
  track: (jobId: string, status: string, notes?: string) =>
    api.post(`/api/jobs/scout/${jobId}/track`, { status, notes }),

  /** Get all user tracking statuses */
  getTracking: () => api.get<TrackingStatuses>('/api/jobs/tracking'),
};

export const tailorApi = {
  /** Generate a tailored resume for a specific job */
  generate: (jobId: string) => api.post<TailorResponse>('/api/resumes/tailor', { jobId }),
};

export const applicationsApi = {
  /** List all applications for the current user */
  list: (userId: string) => api.get<Application[]>(`/api/applications/user/${userId}`),

  /** Create a new application record */
  create: (data: {
    jobId: string;
    resumeId?: string;
    companyName?: string;
    roleTitle?: string;
    notes?: string;
    url?: string;
    status?: string;
  }) => api.post<Application>('/api/applications', data),

  /** Update application status or notes */
  update: (
    applicationId: string,
    data: {
      status?: Application['status'];
      notes?: string;
      resumeId?: string;
    }
  ) => api.patch<Application>(`/api/applications/${applicationId}`, data),

  /** Delete an application */
  delete: (applicationId: string) => api.delete(`/api/applications/${applicationId}`),
};

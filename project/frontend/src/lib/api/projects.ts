import { api } from './client';
import { z } from 'zod';
import { ProjectSchema, validated } from './schemas';

// ─── Projects API ─────────────────────────────────────────────────────────────

export const projectsApi = {
  list: () => api.get('/api/projects').then(validated(z.array(ProjectSchema))),

  get: (id: string) => api.get(`/api/projects/${id}`),

  create: (data: {
    title: string;
    description: string;
    technologies?: string[];
    url?: string;
    highlights?: string[];
    start_date?: string;
    end_date?: string;
  }) => api.post('/api/projects', data),

  update: (
    id: string,
    data: Partial<{
      title: string;
      description: string;
      technologies: string[];
      url: string;
      highlights: string[];
      start_date: string;
      end_date: string;
    }>
  ) => api.patch(`/api/projects/${id}`, data),

  delete: (id: string) => api.delete(`/api/projects/${id}`),

  deleteAll: () => api.delete('/api/projects/all'),

  importGithub: (fullNames: string[]) =>
    api.post('/api/projects/ingest/github', {
      full_names: fullNames,
    }),

  syncAllGithub: () => api.post('/api/projects/ingest/github', { sync_all: true }),

  syncGithub: (id: string) => api.post(`/api/projects/${id}/sync`),

  listGithubUserRepos: () => api.get('/api/projects/github/user-repos'),
};

// ─── GitHub Ingestion API ─────────────────────────────────────────────────────

export const githubApi = {
  /** Refresh already-imported repos with latest README + Bedrock summary */
  sync: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, { params: { include_forks: includeForks, mode: 'sync' } }),

  /** Import repos not yet in the Projects table */
  importNew: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, {
      params: { include_forks: includeForks, mode: 'import_new' },
    }),

  /** @deprecated use sync() */
  ingest: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, { params: { include_forks: includeForks, mode: 'sync' } }),

  /** Poll ingestion status */
  getIngestStatus: () =>
    api.get<{
      status: string;
      summary: {
        total: number;
        processed: number;
        failed: number;
        mode?: string;
        lastRunAt: string;
      } | null;
    }>('/api/github/ingest-status'),

  /** List all ingested projects for current user */
  listProjects: () => api.get<Array<Record<string, unknown>>>('/api/github/projects'),
};

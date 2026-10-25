import { api } from './client';
import type { SkillGapReport, Roadmap, Role, SuggestResponse, ProjectRoadmap } from './types';

export const skillGapApi = {
  /** List available career roles */
  getRoles: () => api.get<{ roles: Role[] }>('/api/skill-gap/roles'),

  /** Run skill gap analysis for user vs role */
  analyse: (roleId: string) => api.post<SkillGapReport>('/api/skill-gap/analyse', { roleId }),
};

// ─── Roadmap API ──────────────────────────────────────────────────────────────

export const roadmapApi = {
  /** Generate a learning roadmap from gap analysis */
  generate: (roleId: string, reportId?: string) =>
    api.post<Roadmap>('/api/skill-gap/roadmap/generate', { roleId, reportId }),

  /** Mark a milestone week as complete */
  markComplete: (roadmapId: string, weekNumber: number) =>
    api.patch<Roadmap>(`/api/skill-gap/roadmap/${roadmapId}/milestone/${weekNumber}`),
};

export const projectRoadmapApi = {
  /** Step 1: Suggest 3 project ideas */
  suggest: (domain: string) =>
    api.post<SuggestResponse>('/api/project-roadmap/suggest', { domain }),

  /** Step 2: Generate 7-day plan for chosen project */
  plan: (data: {
    domain: string;
    projectTitle: string;
    projectDescription: string;
    techStack: string[];
  }) => api.post<ProjectRoadmap>('/api/project-roadmap/plan', data),

  /** List all project roadmaps for current user */
  list: () => api.get<{ roadmaps: ProjectRoadmap[] }>('/api/project-roadmap/list'),

  /** Fetch a specific roadmap */
  get: (roadmapId: string) => api.get<ProjectRoadmap>(`/api/project-roadmap/${roadmapId}`),

  /** Mark a day as complete */
  markDayComplete: (roadmapId: string, dayNumber: number) =>
    api.patch<ProjectRoadmap>(`/api/project-roadmap/${roadmapId}/day/${dayNumber}/complete`),

  /** Unlock all days */
  unlockAll: (roadmapId: string) =>
    api.patch<ProjectRoadmap>(`/api/project-roadmap/${roadmapId}/unlock-all`),

  /** Delete a roadmap */
  delete: (roadmapId: string) =>
    api.delete<{ deleted: boolean }>(`/api/project-roadmap/${roadmapId}`),
};

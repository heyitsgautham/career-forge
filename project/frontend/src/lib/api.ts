import axios from 'axios';

// ─── Type Interfaces ──────────────────────────────────────────────────────────

export interface User {
  userId: string;
  username: string;
  email: string;
  avatarUrl: string;
  name?: string;
  githubToken?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  website?: string;
  experience?: Array<{
    title: string;
    company: string;
    location?: string;
    start_date: string;
    end_date?: string;
    highlights: string[];
  }>;
  education?: Array<{
    degree: string;
    school: string;
    location?: string;
    graduation_date: string;
    gpa?: string;
  }>;
  certifications?: string[];
  skills?: string[];
}

export interface Project {
  projectId: string;
  id?: string;
  name: string;
  title?: string;
  description: string;
  skills: string[];
  technologies?: string[];
  repoUrl: string;
  url?: string;
  highlights?: string[];
  start_date?: string;
  end_date?: string;
}

export interface Resume {
  resumeId: string;
  id?: string;
  name?: string;
  pdfUrl: string;
  texUrl: string;
  createdAt: string;
  jobDescriptionId?: string;
  status?: string;
}

export interface SkillGap {
  domain: string;
  userScore: number;
  requiredScore: number;
  gap: number;
  priority: 'high' | 'medium' | 'low';
}

export interface SkillGapReport {
  reportId: string;
  userId: string;
  roleId: string;
  roleName: string;
  userScores: Record<string, number>;
  benchmarkScores: Record<string, number>;
  gaps: SkillGap[];
  overallFitPercent: number;
  projectCount: number;
  createdAt: string;
  report?: null; // present when no report found
}

export interface Job {
  jobId: string;
  title: string;
  company: string;
  matchScore: number | null;
  url: string;
  location?: string;
  source?: string;
  datePosted?: string;
  salary?: string;
  jobType?: string;
  category?: string;
  requiredSkills?: string[];
  preferredSkills?: string[];
  missingSkills?: string[];
  experienceLevel?: string;
  atsKeywords?: string[];
  matchBreakdown?: {
    vectorScore?: number;
    keywordScore?: number;
    matchedSkills?: string[];
    explanation?: string;
  };
  isAnalyzed?: boolean;
  description?: string;
  postedAt?: string; // alias for datePosted
  createdAt?: string;
}

export interface Application {
  applicationId: string;
  userId: string;
  jobId: string;
  companyName: string;
  roleTitle: string;
  status: 'saved' | 'applied' | 'viewed' | 'interviewing' | 'offered' | 'rejected';
  appliedAt: string;
  updatedAt: string;
  resumeId?: string;
  notes?: string;
  url?: string;
}

export interface RoadmapWeek {
  week: number;
  projectTitle: string;
  description?: string;
  techStack: string[];
  estimatedHours: number;
  resources: Array<{ title: string; url: string }>;
  completedAt?: string | null;
}

export interface Roadmap {
  roadmapId: string;
  userId?: string;
  roleId: string;
  roleName: string;
  reportId?: string;
  overallFitPercent?: number;
  weeks: RoadmapWeek[];
  completedWeeks: number;
  totalWeeks: number;
  createdAt: string;
}

// ─── Axios Instance ───────────────────────────────────────────────────────────

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Inject auth token + bypass browser HTTP cache on GETs (React Query handles caching)
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (config.method === 'get') {
    config.headers['Cache-Control'] = 'no-cache';
    config.headers['Pragma'] = 'no-cache';
  }
  return config;
});

// Handle 401 → clear token → redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ─── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post('/api/auth/login', { email, password }),

  register: (email: string, password: string, full_name: string) =>
    api.post('/api/auth/register', { email, password, full_name }),

  githubLogin: () => {
    // Always use standard OAuth flow for login.
    // GitHub App installation (repo selection) happens post-login in the dashboard.
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;
    if (!clientId) {
      console.error('NEXT_PUBLIC_GITHUB_CLIENT_ID is not configured');
      return;
    }
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001').replace(/\/$/, '');
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/github`);
    const scope = encodeURIComponent('read:user user:email repo');
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
  },

  githubCallback: (code: string, installationId?: number) =>
    api.post('/api/auth/github/callback', { code, installation_id: installationId }),

  getProfile: () => api.get('/api/auth/profile'),
};

// ─── User API ─────────────────────────────────────────────────────────────────

export const userApi = {
  getMe: () => api.get('/api/auth/me'),

  getProfile: () => api.get('/api/auth/profile'),

  updateProfile: (data: Partial<User>) =>
    api.put('/api/auth/profile', data),

  getGithubStatus: () => api.get('/api/auth/github/status'),

  uploadResume: (formData: FormData) =>
    api.post('/api/auth/upload-resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
};

// ─── Projects API ─────────────────────────────────────────────────────────────

export const projectsApi = {
  list: () => api.get('/api/projects'),

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

  update: (id: string, data: Partial<{
    title: string;
    description: string;
    technologies: string[];
    url: string;
    highlights: string[];
    start_date: string;
    end_date: string;
  }>) => api.patch(`/api/projects/${id}`, data),

  delete: (id: string) => api.delete(`/api/projects/${id}`),

  deleteAll: () => api.delete('/api/projects/all'),

  importGithub: (fullNames: string[]) =>
    api.post('/api/projects/ingest/github', {
      full_names: fullNames
    }),

  syncAllGithub: () =>
    api.post('/api/projects/ingest/github', { sync_all: true }),

  syncGithub: (id: string) => api.post(`/api/projects/${id}/sync`),

  listGithubUserRepos: () => api.get('/api/projects/github/user-repos'),
};

// ─── Templates API ────────────────────────────────────────────────────────────

export const templatesApi = {
  list: () => api.get('/api/templates'),

  get: (id: string) => api.get(`/api/templates/${id}`),

  create: (data: {
    name: string;
    description: string;
    latex_content: string;
    category?: string;
  }) => api.post('/api/templates', data),

  update: (id: string, data: Partial<{
    name: string;
    description: string;
    latex_content: string;
    category: string;
  }>) => api.patch(`/api/templates/${id}`, data),

  delete: (id: string) => api.delete(`/api/templates/${id}`),

  getSystemTemplates: () => api.get('/api/templates/system'),
};

// ─── Job Descriptions API ─────────────────────────────────────────────────────

export const jobsApi = {
  list: () => api.get('/api/jobs'),

  get: (id: string) => api.get(`/api/jobs/${id}`),

  create: (data: {
    title: string;
    company: string;
    raw_text: string;
    url?: string;
  }) => api.post('/api/jobs', data),

  update: (id: string, data: Partial<{
    title: string;
    company: string;
    raw_text: string;
    url: string;
  }>) => api.patch(`/api/jobs/${id}`, data),

  delete: (id: string) => api.delete(`/api/jobs/${id}`),

  analyze: (id: string) => api.post(`/api/jobs/${id}/analyze`),
};

// ─── Resumes API ──────────────────────────────────────────────────────────────

export const resumesApi = {
  list: () => api.get('/api/resumes'),

  get: (id: string) => api.get(`/api/resumes/${id}`),

  create: (data: {
    name: string;
    template_id?: string;
    job_description_id?: string;
    project_ids?: string[];
  }) => api.post('/api/resumes', data),

  /** M2: Generate resume from S3 project summaries + optional JD */
  generateFromSummaries: (jd?: string) =>
    api.post<{
      resume_id: string;
      pdf_url: string | null;
      tex_url: string | null;
      analysis: string;
      status: string;
    }>('/api/resumes/generate', { jd: jd || null }),

  generate: (id: string, data?: {
    personal?: {
      name: string;
      email: string;
      phone?: string;
      location?: string;
      linkedin?: string;
      github?: string;
      website?: string;
    };
    skills?: string[];
    experience?: Array<{
      title: string;
      company: string;
      location?: string;
      start_date: string;
      end_date?: string;
      highlights: string[];
    }>;
    education?: Array<{
      degree: string;
      school: string;
      location?: string;
      graduation_date: string;
      gpa?: string;
    }>;
    tailor_to_jd?: boolean;
  }) => api.post(`/api/resumes/${id}/generate`, data || {}),

  compile: (id: string) => api.post(`/api/resumes/${id}/compile`),

  /** M2.5: Compile with optional latex_content override (on-demand compile) */
  compileWithContent: (id: string, latex_content?: string) =>
    api.post<{ pdf_url: string | null; status: string; error_message: string | null }>(
      `/api/resumes/${id}/compile`,
      latex_content ? { latex_content } : {},
    ),

  updateLatex: (id: string, latex_content: string) =>
    api.patch(`/api/resumes/${id}/latex`, { latex_content }),

  /** M2.5: Save LaTeX via proper PUT endpoint (also syncs S3 tex key) */
  saveLaTeX: (id: string, latex_content: string) =>
    api.put<{ id: string; updated_at: string }>(`/api/resumes/${id}/latex`, { latex_content }),

  downloadPdf: (id: string) =>
    api.get(`/api/resumes/${id}/pdf`, { responseType: 'blob' }),

  /** Get presigned S3 URL for PDF preview (no redirect) */
  getPdfUrl: (id: string) =>
    api.get<{ url: string }>(`/api/resumes/${id}/pdf-url`),

  downloadTex: (id: string) =>
    api.get(`/api/resumes/${id}/tex`, { responseType: 'blob' }),

  delete: (id: string) => api.delete(`/api/resumes/${id}`),

  /**
   * M2.5: AI edit via SSE stream.
   * Returns the fetch Response so the caller can read `response.body` as a ReadableStream.
   * Uses fetch (not axios) because EventSource doesn't support POST + auth headers.
   */
  aiEdit: async (id: string, message: string, latex_content: string): Promise<Response> => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const response = await fetch(`${baseUrl}/api/resumes/${id}/ai-edit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, latex_content }),
    });
    if (!response.ok) {
      throw new Error(`AI edit failed: ${response.status}`);
    }
    return response;
  },
};

// ─── GitHub Ingestion API ─────────────────────────────────────────────────────

export const githubApi = {
  /** Refresh already-imported repos with latest README + Bedrock summary */
  sync: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, { params: { include_forks: includeForks, mode: 'sync' } }),

  /** Import repos not yet in the Projects table */
  importNew: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, { params: { include_forks: includeForks, mode: 'import_new' } }),

  /** @deprecated use sync() */
  ingest: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, { params: { include_forks: includeForks, mode: 'sync' } }),

  /** Poll ingestion status */
  getIngestStatus: () =>
    api.get<{ status: string; summary: { total: number; processed: number; failed: number; mode?: string; lastRunAt: string } | null }>(
      '/api/github/ingest-status'
    ),

  /** List all ingested projects for current user */
  listProjects: () =>
    api.get<Array<Record<string, unknown>>>('/api/github/projects'),
};

// ─── Skill Gap API ────────────────────────────────────────────────────────────

export interface Role {
  roleId: string;
  role: string;
  icon: string;
  description: string;
  skillDomains: string[];
}

export const skillGapApi = {
  /** List available career roles */
  getRoles: () =>
    api.get<{ roles: Role[] }>('/api/skill-gap/roles'),

  /** Run skill gap analysis for user vs role */
  analyse: (roleId: string) =>
    api.post<SkillGapReport>('/api/skill-gap/analyse', { roleId }),

  /** Fetch cached gap report */
  getReport: (roleId?: string) =>
    api.get<SkillGapReport | { report: null }>('/api/skill-gap/report', {
      params: roleId ? { roleId } : {},
    }),
};

// ─── Roadmap API ──────────────────────────────────────────────────────────────

export const roadmapApi = {
  /** Generate a learning roadmap from gap analysis */
  generate: (roleId: string, reportId?: string) =>
    api.post<Roadmap>('/api/skill-gap/roadmap/generate', { roleId, reportId }),

  /** Fetch a specific roadmap */
  get: (roadmapId: string) =>
    api.get<Roadmap>(`/api/skill-gap/roadmap/${roadmapId}`),

  /** List all roadmaps for current user */
  list: () =>
    api.get<{ roadmaps: Roadmap[] }>('/api/skill-gap/roadmaps'),

  /** Mark a milestone week as complete */
  markComplete: (roadmapId: string, weekNumber: number) =>
    api.patch<Roadmap>(`/api/skill-gap/roadmap/${roadmapId}/milestone/${weekNumber}`),
};

// ─── New interfaces for Job Scout v2 ──────────────────────────────────────────

export interface SchedulerStatus {
  running: boolean;
  nextRunTime: string | null;
  lastScrape: {
    timestamp: string | null;
    total_jobs: number;
    new_jobs: number;
    status: string | null;
    message: string | null;
  } | null;
}

export interface TrackingStatuses {
  [jobId: string]: { status: string; notes: string };
}

export interface BlacklistedCompany {
  companyName: string;
  addedBy?: string;
  createdAt?: string;
}

// ─── Job Matching API (M4 — Job Scout v2) ────────────────────────────────────

export const jobMatchApi = {
  /** List all shared jobs (sorted by date) */
  list: () => api.get<Job[]>('/api/jobs/matches'),

  /** List with filters */
  listFiltered: (params: {
    role?: string;
    minMatch?: number;
    sortBy?: string;
    limit?: number;
  }) =>
    api.get<Job[]>('/api/jobs/matches', { params: { ...params } }),

  /** Get full detail for one job */
  get: (jobId: string) => api.get<Job>(`/api/jobs/scout/${jobId}`),

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

  /** Delete a scraped job (admin only) */
  delete: (jobId: string) => api.delete(`/api/jobs/scout/${jobId}`),

  /** Scheduler status */
  schedulerStatus: () =>
    api.get<SchedulerStatus>('/api/jobs/scheduler/status'),

  /** Track a job (set status) */
  track: (jobId: string, status: string, notes?: string) =>
    api.post(`/api/jobs/scout/${jobId}/track`, { status, notes }),

  /** Get all user tracking statuses */
  getTracking: () =>
    api.get<TrackingStatuses>('/api/jobs/tracking'),

  /** Blacklist CRUD (admin) */
  getBlacklist: () =>
    api.get<BlacklistedCompany[]>('/api/jobs/blacklist'),

  addBlacklist: (companyName: string) =>
    api.post('/api/jobs/blacklist', { companyName }),

  removeBlacklist: (companyName: string) =>
    api.delete(`/api/jobs/blacklist/${encodeURIComponent(companyName)}`),
};

// ─── Applications API (M5) ─────────────────────────────────────────────────

export interface TailorResponse {
  resumeId: string;
  pdfUrl: string | null;
  texUrl: string | null;
  jobId: string;
  matchKeywords: string[];
  diffSummary: {
    skillsReordered?: boolean;
    projectsChanged?: string[];
    keywordsInjected?: string[];
    bulletsRewritten?: number;
    sectionsModified?: string[];
  };
  compilationError?: string | null;
}

export interface ApplicationStats {
  total: number;
  saved: number;
  applied: number;
  viewed: number;
  interviewing: number;
  offered: number;
  rejected: number;
}

export const tailorApi = {
  /** Generate a tailored resume for a specific job */
  generate: (jobId: string) =>
    api.post<TailorResponse>('/api/resumes/tailor', { jobId }),

  /** Fetch existing tailored resume for a job */
  getForJob: (jobId: string) =>
    api.get<TailorResponse>(`/api/resumes/job/${jobId}`),
};

export const applicationsApi = {
  /** List all applications for the current user */
  list: (userId: string) =>
    api.get<Application[]>(`/api/applications/user/${userId}`),

  /** List with status filter */
  listFiltered: (userId: string, status: string) =>
    api.get<Application[]>(`/api/applications/user/${userId}`, {
      params: { status_filter: status },
    }),

  /** Create a new application record */
  create: (data: {
    jobId: string;
    resumeId?: string;
    companyName?: string;
    roleTitle?: string;
    notes?: string;
    url?: string;
  }) => api.post<Application>('/api/applications', data),

  /** Update application status or notes */
  update: (applicationId: string, data: {
    status?: Application['status'];
    notes?: string;
    resumeId?: string;
  }) => api.patch<Application>(`/api/applications/${applicationId}`, data),

  /** Delete an application */
  delete: (applicationId: string) =>
    api.delete(`/api/applications/${applicationId}`),

  /** Get stats summary */
  stats: (userId: string) =>
    api.get<ApplicationStats>(`/api/applications/stats/${userId}`),
};

export { api };
export default api;

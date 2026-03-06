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
  overallScore: number;
  gaps: SkillGap[];
  createdAt: string;
  roleId?: string;
  roleName?: string;
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
}

export interface Application {
  applicationId: string;
  jobId: string;
  company: string;
  role: string;
  status: 'applied' | 'interviewing' | 'offer' | 'rejected';
  appliedAt: string;
  resumeId?: string;
  url?: string;
}

export interface RoadmapWeek {
  week: number;
  projectTitle: string;
  techStack: string[];
  estimatedHours: number;
  resources: Array<{ title: string; url: string }>;
  completedAt?: string;
}

export interface Roadmap {
  roadmapId: string;
  weeks: RoadmapWeek[];
  createdAt: string;
}

// ─── Axios Instance ───────────────────────────────────────────────────────────

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Inject auth token
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
    // Prefer GitHub App install URL (shows repo-selection screen)
    const appSlug = process.env.NEXT_PUBLIC_GITHUB_APP_SLUG;
    if (appSlug) {
      window.location.href = `https://github.com/apps/${appSlug}/installations/new`;
      return;
    }
    // Fallback to legacy OAuth
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;
    if (!clientId) {
      console.error('NEXT_PUBLIC_GITHUB_CLIENT_ID is not configured');
      return;
    }
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/$/, '');
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/github`);
    const scope = encodeURIComponent('read:user user:email');
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

  importGithub: (owner: string, repo: string) =>
    api.post('/api/projects/ingest/github', {
      repo_urls: [`https://github.com/${owner}/${repo}`]
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

  updateLatex: (id: string, latex_content: string) =>
    api.patch(`/api/resumes/${id}/latex`, { latex_content }),

  downloadPdf: (id: string) =>
    api.get(`/api/resumes/${id}/pdf`, { responseType: 'blob' }),

  downloadTex: (id: string) =>
    api.get(`/api/resumes/${id}/tex`, { responseType: 'blob' }),

  delete: (id: string) => api.delete(`/api/resumes/${id}`),
};

// ─── GitHub Ingestion API ─────────────────────────────────────────────────────

export const githubApi = {
  /** Trigger full ingestion: fetch repos → Bedrock summary → S3 + DynamoDB */
  ingest: (includeForks: boolean = false) =>
    api.post('/api/github/ingest', null, { params: { include_forks: includeForks } }),

  /** Poll ingestion status */
  getIngestStatus: () =>
    api.get<{ status: string; summary: { total: number; processed: number; failed: number; lastRunAt: string } | null }>(
      '/api/github/ingest-status'
    ),

  /** List all ingested projects for current user */
  listProjects: () =>
    api.get<Array<Record<string, unknown>>>('/api/github/projects'),
};

// ─── Skill Gap API (Stubs — real in M3) ───────────────────────────────────────

export const skillGapApi = {
  getReport: (_userId: string): Promise<{ data: SkillGapReport | null }> =>
    Promise.resolve({ data: null }),

  analyse: (_userId: string, _jobDescription: string): Promise<{ data: SkillGapReport | null }> =>
    Promise.resolve({ data: null }),
};

// ─── Roadmap API (Stubs — real in M3) ─────────────────────────────────────────

export const roadmapApi = {
  generate: (_userId: string, _roleId: string): Promise<{ data: Roadmap | null }> =>
    Promise.resolve({ data: null }),

  get: (_roadmapId: string): Promise<{ data: Roadmap | null }> =>
    Promise.resolve({ data: null }),

  markComplete: (_roadmapId: string, _week: number): Promise<{ data: void }> =>
    Promise.resolve({ data: undefined }),
};

// ─── Job Matching API (M4 — Job Scout) ───────────────────────────────────────

export const jobMatchApi = {
  /** List all scraped jobs sorted by match score */
  list: () => api.get<Job[]>('/api/jobs/matches'),

  /** List with filters */
  listFiltered: (params: {
    role?: string;
    minMatch?: number;
    sortBy?: string;
    limit?: number;
  }) =>
    api.get<Job[]>('/api/jobs/matches', { params: { ...params } }),

  /** Trigger a new scrape + analysis + scoring */
  scan: (data?: {
    search_term?: string;
    location?: string;
    results_wanted?: number;
  }) => api.post<Job[]>('/api/jobs/scrape', data || { search_term: 'Software Developer' }),

  /** Get full detail for one job */
  get: (jobId: string) => api.get<Job>(`/api/jobs/scout/${jobId}`),

  /** Get summary stats */
  stats: () =>
    api.get<{
      totalJobs: number;
      analyzedJobs: number;
      averageMatch: number | null;
      topCategories: Array<{ category: string; count: number }>;
      matchDistribution: Record<string, number>;
    }>('/api/jobs/stats'),

  /** Delete a scraped job */
  delete: (jobId: string) => api.delete(`/api/jobs/scout/${jobId}`),
};

// ─── Applications API (Stubs — real in M5) ────────────────────────────────────

export const applicationsApi = {
  list: (_userId: string): Promise<{ data: Application[] }> =>
    Promise.resolve({ data: [] }),

  create: (_data: Partial<Application>): Promise<{ data: Application | null }> =>
    Promise.resolve({ data: null }),

  updateStatus: (_id: string, _status: Application['status']): Promise<{ data: void }> =>
    Promise.resolve({ data: undefined }),
};

export { api };
export default api;

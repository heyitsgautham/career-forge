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
  matchScore: number;
  url: string;
  location?: string;
  skills?: string[];
  missingSkills?: string[];
  description?: string;
  postedAt?: string;
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
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID || 'Ov23li7PyDbHv0U1oqbZ';
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/$/, '');
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/github`);
    const scope = encodeURIComponent('read:user user:email repo');
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
  },

  githubCallback: (code: string) =>
    api.post('/api/auth/github/callback', { code }),

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

  delete: (id: string) => api.delete(`/api/resumes/${id}`),
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

// ─── Job Matching API (Stubs — real in M4) ────────────────────────────────────

export const jobMatchApi = {
  list: (_userId: string): Promise<{ data: Job[] }> =>
    Promise.resolve({ data: [] }),

  scan: (_userId: string): Promise<{ data: Job[] }> =>
    Promise.resolve({ data: [] }),
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

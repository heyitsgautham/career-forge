import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
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

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/api/auth/login', { email, password }),
  
  register: (email: string, password: string, full_name: string) =>
    api.post('/api/auth/register', { email, password, full_name }),
  
  githubCallback: (code: string) =>
    api.post('/api/auth/github/callback', { code }),
  
  getProfile: () => api.get('/api/auth/me'),
};

// Projects API
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

// Templates API
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

// Job Descriptions API
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

// Resumes API
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

export { api };
export default api;

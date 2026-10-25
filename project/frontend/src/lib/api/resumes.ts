import { api } from './client';
import { z } from 'zod';
import { ResumeSummarySchema, TemplateListItemSchema, TemplateSchema, validated } from './schemas';

// ─── Templates API ────────────────────────────────────────────────────────────

export const templatesApi = {
  list: () => api.get('/api/templates').then(validated(z.array(TemplateListItemSchema))),

  get: (id: string) => api.get(`/api/templates/${id}`).then(validated(TemplateSchema)),

  create: (data: { name: string; description: string; latex_content: string; category?: string }) =>
    api.post('/api/templates', data),

  delete: (id: string) => api.delete(`/api/templates/${id}`),
};

// ─── Resumes API ──────────────────────────────────────────────────────────────

export const resumesApi = {
  list: () => api.get('/api/resumes').then(validated(z.array(ResumeSummarySchema))),

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

  generate: (
    id: string,
    data?: {
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
    }
  ) => api.post(`/api/resumes/${id}/generate`, data || {}),

  compile: (id: string) => api.post(`/api/resumes/${id}/compile`),

  /** M2.5: Compile with optional latex_content override (on-demand compile) */
  compileWithContent: (id: string, latex_content?: string) =>
    api.post<{ pdf_url: string | null; status: string; error_message: string | null }>(
      `/api/resumes/${id}/compile`,
      latex_content ? { latex_content } : {}
    ),

  /** M2.5: Save LaTeX via proper PUT endpoint (also syncs S3 tex key) */
  saveLaTeX: (id: string, latex_content: string) =>
    api.put<{ id: string; updated_at: string }>(`/api/resumes/${id}/latex`, { latex_content }),

  /** Get presigned S3 URL for PDF preview (no Content-Disposition) */
  getPdfUrl: (id: string) => api.get<{ url: string }>(`/api/resumes/${id}/pdf-url`),

  /** Get presigned S3 URL with Content-Disposition: attachment for download */
  getPdfDownloadUrl: (id: string) =>
    api.get<{ url: string }>(`/api/resumes/${id}/pdf-url?download=true`),

  downloadTex: (id: string) => api.get(`/api/resumes/${id}/tex`, { responseType: 'blob' }),

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

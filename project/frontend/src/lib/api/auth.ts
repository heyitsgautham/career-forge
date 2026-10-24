import { api } from './client';
import type { User } from './types';

// ─── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) => api.post('/api/auth/login', { email, password }),

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
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/$/, '');
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/github`);
    const scope = encodeURIComponent('read:user user:email repo');
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
  },

  githubInstall: () => {
    // GitHub App installation flow — lets user pick repos and authorizes in one step.
    // Used from dashboard "Connect GitHub" (post-login).
    const slug = process.env.NEXT_PUBLIC_GITHUB_APP_SLUG;
    if (!slug) {
      console.error('NEXT_PUBLIC_GITHUB_APP_SLUG is not configured');
      return;
    }
    // Pass the current JWT so the callback can link GitHub to the existing user
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const state = token ? encodeURIComponent(token) : '';
    window.location.href = `https://github.com/apps/${slug}/installations/new${state ? `?state=${state}` : ''}`;
  },

  githubCallback: (code: string, installationId?: number, linkToken?: string) =>
    api.post('/api/auth/github/callback', {
      code,
      installation_id: installationId,
      link_token: linkToken || undefined,
    }),

  cognitoGoogleLogin: () => {
    const domain = process.env.NEXT_PUBLIC_COGNITO_DOMAIN;
    const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
    if (!domain || !clientId) {
      console.error('Cognito env vars not configured');
      return;
    }
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/$/, '');
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/cognito`);
    window.location.href = `https://${domain}/oauth2/authorize?client_id=${clientId}&response_type=code&scope=openid+email+profile&redirect_uri=${redirectUri}&identity_provider=Google`;
  },

  cognitoCallback: (code: string) => api.post('/api/auth/cognito/callback', { code }),

  getProfile: () => api.get('/api/auth/profile'),
};

// ─── User API ─────────────────────────────────────────────────────────────────

export const userApi = {
  getMe: () => api.get('/api/auth/me'),

  getProfile: () => api.get('/api/auth/profile'),

  updateProfile: (data: Partial<User>) => api.put('/api/auth/profile', data),

  getGithubStatus: () => api.get('/api/auth/github/status'),

  uploadResume: (formData: FormData) =>
    api.post('/api/auth/upload-resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  importLinkedInProfile: (linkedinUrl?: string) =>
    api.post('/api/auth/linkedin/import-profile', linkedinUrl ? { linkedin_url: linkedinUrl } : {}),

  scrapeCertifications: () => api.post('/api/auth/linkedin/scrape-certifications'),
};

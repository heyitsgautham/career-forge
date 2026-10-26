import axios from 'axios';
import { clearCachedData } from '@/lib/query-cache';

// ─── Axios Instance ───────────────────────────────────────────────────────────

export const api = axios.create({
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
        // The full page load below drops the in-memory cache; this drops the persisted copy.
        void clearCachedData();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

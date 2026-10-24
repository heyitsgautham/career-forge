/**
 * Typed client for the CareerForge backend.
 *
 * Everything is re-exported here, so callers keep importing from '@/lib/api'.
 * client.ts holds the axios instance with the auth and 401 interceptors, and
 * each other module wraps one group of backend routes.
 */
export * from './types';
export * from './auth';
export * from './projects';
export * from './resumes';
export * from './jobs';
export * from './roadmaps';
export { api } from './client';
export { api as default } from './client';

import type { Application } from '@/lib/api';

export const TOKEN_U1 = `h.${btoa(JSON.stringify({ sub: 'u1' }))}.s`;

/** A synthetic tracked application. */
export function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    applicationId: 'a1',
    userId: 'u1',
    jobId: 'j1',
    companyName: 'Sample Labs',
    roleTitle: 'Backend Intern',
    status: 'applied',
    appliedAt: '2026-03-05T10:00:00Z',
    updatedAt: '2026-03-05T10:00:00Z',
    ...overrides,
  };
}

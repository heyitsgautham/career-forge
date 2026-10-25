import type { Job } from '@/lib/api';

/** A synthetic job posting. Override only the fields a test cares about. */
export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    jobId: 'j1',
    title: 'Backend Intern',
    company: 'Sample Labs',
    matchScore: 82,
    url: 'https://jobs.example.com/j1',
    location: 'Bengaluru',
    source: 'naukri',
    category: 'SDE',
    requiredSkills: ['Python', 'SQL'],
    createdAt: '2026-03-09T08:00:00Z',
    ...overrides,
  };
}

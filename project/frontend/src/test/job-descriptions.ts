import type { JobDescription } from '@/components/dashboard/jobs/types';

/** A synthetic saved job description. */
export function makeJobDescription(overrides: Partial<JobDescription> = {}): JobDescription {
  return {
    id: 'jd1',
    title: 'Backend Intern',
    company: 'Sample Labs',
    raw_text: 'Build REST APIs in Python and write tests for them.',
    required_skills: ['Python', 'FastAPI'],
    preferred_skills: ['Docker'],
    keywords: ['REST'],
    is_analyzed: true,
    created_at: '2026-03-01T00:00:00Z',
    ...overrides,
  };
}

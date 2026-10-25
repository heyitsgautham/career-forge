import { describe, expect, it } from 'vitest';
import { filterJobs, pageCount, pageSlice } from '../filter-jobs';
import { makeJob } from '@/test/fixtures';

const JOBS = [
  makeJob({ jobId: 'a', title: 'Backend Intern', company: 'Sample Labs', source: 'naukri' }),
  makeJob({
    jobId: 'b',
    title: 'ML Engineer',
    company: 'Demo Corp',
    source: 'LinkedIn',
    category: 'AI/ML',
    location: 'Chennai',
    requiredSkills: ['PyTorch'],
  }),
  makeJob({
    jobId: 'c',
    title: 'Frontend Developer',
    company: 'Example Web',
    source: 'unstop',
    category: undefined,
    location: undefined,
    requiredSkills: ['React', 'Web performance'],
  }),
];
const ALL = { source: 'All', category: 'All', query: '' } as const;
const ids = (jobs: { jobId: string }[]) => jobs.map((j) => j.jobId);

describe('filterJobs', () => {
  it('returns every job when no filter is set', () => {
    expect(ids(filterJobs(JOBS, ALL))).toEqual(['a', 'b', 'c']);
  });

  it('matches the source without regard to case', () => {
    expect(ids(filterJobs(JOBS, { ...ALL, source: 'linkedin' }))).toEqual(['b']);
  });

  it('matches a category against the category, the title or the skills', () => {
    expect(ids(filterJobs(JOBS, { ...ALL, category: 'AI/ML' }))).toEqual(['b']);
    expect(ids(filterJobs(JOBS, { ...ALL, category: 'Web' }))).toEqual(['c']);
    expect(ids(filterJobs(JOBS, { ...ALL, category: 'SDE' }))).toEqual(['a']);
  });

  it('searches the title, company and location', () => {
    expect(ids(filterJobs(JOBS, { ...ALL, query: 'demo' }))).toEqual(['b']);
    expect(ids(filterJobs(JOBS, { ...ALL, query: 'CHENNAI' }))).toEqual(['b']);
    expect(ids(filterJobs(JOBS, { ...ALL, query: 'developer' }))).toEqual(['c']);
  });

  it('ignores a whitespace-only search', () => {
    expect(filterJobs(JOBS, { ...ALL, query: '   ' })).toHaveLength(3);
  });

  it('combines every filter', () => {
    expect(filterJobs(JOBS, { source: 'naukri', category: 'AI/ML', query: '' })).toEqual([]);
  });
});

describe('pagination', () => {
  it('always has at least one page', () => {
    expect(pageCount(0)).toBe(1);
    expect(pageCount(25)).toBe(1);
    expect(pageCount(26)).toBe(2);
    expect(pageCount(5, 2)).toBe(3);
  });

  it('slices one zero-based page', () => {
    const items = [1, 2, 3, 4, 5];
    expect(pageSlice(items, 0, 2)).toEqual([1, 2]);
    expect(pageSlice(items, 2, 2)).toEqual([5]);
    expect(pageSlice(items, 3, 2)).toEqual([]);
  });
});

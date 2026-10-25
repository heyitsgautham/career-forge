import { describe, expect, it } from 'vitest';
import { tailoredResumeMap } from '../tailored-resumes';

describe('tailoredResumeMap', () => {
  it('maps each job to its tailored resume and skips standard ones', () => {
    const resumes = [
      { id: 'r1', type: 'tailored', job_id: 'j1' },
      { id: 'r2', type: 'standard' },
      { id: 'r3', type: 'tailored' },
    ];
    expect(tailoredResumeMap(resumes, {})).toEqual({ j1: 'r1' });
  });

  it('keeps a fresh resume while it still exists in the list', () => {
    const resumes = [{ id: 'r9', type: 'standard' }];
    expect(tailoredResumeMap(resumes, { j2: 'r9' })).toEqual({ j2: 'r9' });
  });

  it('drops a fresh resume that was deleted', () => {
    const resumes = [{ id: 'r1', type: 'standard' }];
    expect(tailoredResumeMap(resumes, { j2: 'gone' })).toEqual({});
  });

  it('trusts fresh resumes before the resume list has loaded', () => {
    expect(tailoredResumeMap([], { j2: 'r9' })).toEqual({ j2: 'r9' });
  });

  it('lets a fresh resume replace an older one for the same job', () => {
    const resumes = [
      { id: 'old', type: 'tailored', job_id: 'j1' },
      { id: 'new', type: 'tailored', job_id: 'other' },
    ];
    expect(tailoredResumeMap(resumes, { j1: 'new' })).toEqual({ j1: 'new', other: 'new' });
  });
});

import type { AxiosAdapter } from 'axios';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import api, { jobMatchApi, projectsApi, resumesApi, templatesApi } from '@/lib/api';
import { ApiResponseError } from '@/lib/api/schemas';

let body: unknown;
const fakeAdapter: AxiosAdapter = async (config) => ({
  data: body,
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
});
const originalAdapter = api.defaults.adapter;

beforeEach(() => {
  api.defaults.adapter = fakeAdapter;
});
afterEach(() => {
  api.defaults.adapter = originalAdapter;
});

const PROJECT = {
  id: 'p1',
  title: 'job-scout',
  description: 'Ranks postings',
  technologies: ['Python'],
  highlights: [],
  url: null,
  demo_url: null,
  source_type: 'github',
  is_verified: false,
};

describe('validated responses', () => {
  it('passes a well-formed project list through, extra fields included', async () => {
    body = [PROJECT];
    const res = await projectsApi.list();
    expect(res.data).toEqual([PROJECT]);
    expect(res.status).toBe(200);
  });

  it('rejects a project list with a missing title and names the field', async () => {
    body = [{ ...PROJECT, title: undefined }];
    const error = await projectsApi.list().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiResponseError);
    expect((error as Error).message).toBe(
      'Unexpected response from /api/projects at 0.title: Invalid input: expected string, received undefined'
    );
  });

  it('rejects an error page served where a list belongs', async () => {
    body = '<html>502 Bad Gateway</html>';
    await expect(projectsApi.list()).rejects.toThrow(/Unexpected response from \/api\/projects/);
  });

  it('accepts the template list, which omits latex_content', async () => {
    body = [
      {
        id: 'system-base-template',
        name: 'Base Resume Template',
        description: null,
        category: 'professional',
        is_system: true,
        is_ats_tested: true,
        use_count: 12,
        preview_image_path: null,
      },
    ];
    await expect(templatesApi.list()).resolves.toMatchObject({ data: body });
  });

  it('requires latex_content when fetching one template', async () => {
    body = { id: 't1', name: 'Mine', is_system: false };
    await expect(templatesApi.get('t1')).rejects.toThrow(/at latex_content/);
  });

  it('rejects a job whose skills arrive as a string instead of a list', async () => {
    body = [{ jobId: 'j1', title: 'Intern', company: 'Sample Labs', requiredSkills: 'Python' }];
    await expect(jobMatchApi.list()).rejects.toThrow(/at 0\.requiredSkills/);
  });

  it('accepts jobs with null optional fields, as DynamoDB returns them', async () => {
    body = [
      {
        jobId: 'j1',
        title: 'Intern',
        company: 'Sample Labs',
        matchScore: null,
        url: null,
        matchBreakdown: null,
        requiredSkills: [],
      },
    ];
    await expect(jobMatchApi.list()).resolves.toMatchObject({ data: body });
  });

  it('requires an id, name and status on every resume', async () => {
    body = [{ id: 'r1', name: 'Backend resume', status: 'compiled', created_at: '2026-03-01' }];
    await expect(resumesApi.list()).resolves.toMatchObject({ data: body });

    body = [{ id: 'r1', name: 'Backend resume' }];
    await expect(resumesApi.list()).rejects.toThrow(/at 0\.status/);
  });
});

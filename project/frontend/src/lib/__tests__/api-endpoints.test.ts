import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import api, {
  applicationsApi,
  authApi,
  githubApi,
  jobMatchApi,
  jobsApi,
  projectRoadmapApi,
  projectsApi,
  resumesApi,
  roadmapApi,
  skillGapApi,
  tailorApi,
  templatesApi,
  userApi,
} from '@/lib/api';

let sent: InternalAxiosRequestConfig[] = [];
const fakeAdapter: AxiosAdapter = async (config) => {
  sent.push(config);
  return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
};
const originalAdapter = api.defaults.adapter;

beforeEach(() => {
  sent = [];
  api.defaults.adapter = fakeAdapter;
});
afterEach(() => {
  api.defaults.adapter = originalAdapter;
});

/** The method, path, body and query of the one request a call made. */
async function request(call: () => Promise<unknown>) {
  await call();
  expect(sent).toHaveLength(1);
  const [config] = sent;
  return {
    method: config.method?.toUpperCase(),
    url: config.url,
    body: typeof config.data === 'string' ? JSON.parse(config.data) : config.data,
    params: config.params,
  };
}

// Each row pins the request the backend route expects. A typo in a path or a
// renamed field shows up here instead of as a 404 or 422 in the browser.
const CASES: Array<[string, () => Promise<unknown>, Record<string, unknown>]> = [
  [
    'login',
    () => authApi.login('a@example.com', 'pw'),
    { method: 'POST', url: '/api/auth/login', body: { email: 'a@example.com', password: 'pw' } },
  ],
  ['profile', () => userApi.getProfile(), { method: 'GET', url: '/api/auth/profile' }],
  [
    'github status',
    () => userApi.getGithubStatus(),
    { method: 'GET', url: '/api/auth/github/status' },
  ],
  [
    'linkedin import',
    () => userApi.importLinkedInProfile('https://linkedin.com/in/a'),
    {
      method: 'POST',
      url: '/api/auth/linkedin/import-profile',
      body: { linkedin_url: 'https://linkedin.com/in/a' },
    },
  ],
  [
    'linkedin import without url',
    () => userApi.importLinkedInProfile(),
    { method: 'POST', url: '/api/auth/linkedin/import-profile', body: {} },
  ],
  ['projects', () => projectsApi.list().catch(() => {}), { method: 'GET', url: '/api/projects' }],
  [
    'create project',
    () => projectsApi.create({ title: 'x', description: 'y' }),
    { method: 'POST', url: '/api/projects', body: { title: 'x', description: 'y' } },
  ],
  ['delete project', () => projectsApi.delete('p1'), { method: 'DELETE', url: '/api/projects/p1' }],
  [
    'delete all projects',
    () => projectsApi.deleteAll(),
    { method: 'DELETE', url: '/api/projects/all' },
  ],
  [
    'import repos',
    () => projectsApi.importGithub(['a/b']),
    { method: 'POST', url: '/api/projects/ingest/github', body: { full_names: ['a/b'] } },
  ],
  [
    'user repos',
    () => projectsApi.listGithubUserRepos(),
    { method: 'GET', url: '/api/projects/github/user-repos' },
  ],
  [
    'sync repos',
    () => githubApi.sync(true),
    { method: 'POST', url: '/api/github/ingest', params: { include_forks: true, mode: 'sync' } },
  ],
  [
    'ingest status',
    () => githubApi.getIngestStatus(),
    { method: 'GET', url: '/api/github/ingest-status' },
  ],
  [
    'github projects',
    () => githubApi.listProjects(),
    { method: 'GET', url: '/api/github/projects' },
  ],
  ['job descriptions', () => jobsApi.list(), { method: 'GET', url: '/api/jobs' }],
  ['analyze job', () => jobsApi.analyze('jd1'), { method: 'POST', url: '/api/jobs/jd1/analyze' }],
  ['job stats', () => jobMatchApi.stats(), { method: 'GET', url: '/api/jobs/stats' }],
  [
    'scheduler',
    () => jobMatchApi.schedulerStatus(),
    { method: 'GET', url: '/api/jobs/scheduler/status' },
  ],
  [
    'track job',
    () => jobMatchApi.track('j1', 'applied'),
    { method: 'POST', url: '/api/jobs/scout/j1/track', body: { status: 'applied' } },
  ],
  ['tracking', () => jobMatchApi.getTracking(), { method: 'GET', url: '/api/jobs/tracking' }],
  [
    'tailor',
    () => tailorApi.generate('j1'),
    { method: 'POST', url: '/api/resumes/tailor', body: { jobId: 'j1' } },
  ],
  [
    'applications',
    () => applicationsApi.list('u1'),
    { method: 'GET', url: '/api/applications/user/u1' },
  ],
  [
    'update application',
    () => applicationsApi.update('a1', { status: 'offered' }),
    { method: 'PATCH', url: '/api/applications/a1', body: { status: 'offered' } },
  ],
  [
    'delete application',
    () => applicationsApi.delete('a1'),
    { method: 'DELETE', url: '/api/applications/a1' },
  ],
  [
    'templates',
    () => templatesApi.get('t1').catch(() => {}),
    { method: 'GET', url: '/api/templates/t1' },
  ],
  [
    'delete template',
    () => templatesApi.delete('t1'),
    { method: 'DELETE', url: '/api/templates/t1' },
  ],
  [
    'generate resume',
    () => resumesApi.generateFromSummaries('Backend intern'),
    { method: 'POST', url: '/api/resumes/generate', body: { jd: 'Backend intern' } },
  ],
  [
    'generate base resume',
    () => resumesApi.generateFromSummaries(),
    { method: 'POST', url: '/api/resumes/generate', body: { jd: null } },
  ],
  ['compile', () => resumesApi.compile('r1'), { method: 'POST', url: '/api/resumes/r1/compile' }],
  [
    'compile edited latex',
    () => resumesApi.compileWithContent('r1', '\\x'),
    { method: 'POST', url: '/api/resumes/r1/compile', body: { latex_content: '\\x' } },
  ],
  [
    'save latex',
    () => resumesApi.saveLaTeX('r1', '\\x'),
    { method: 'PUT', url: '/api/resumes/r1/latex', body: { latex_content: '\\x' } },
  ],
  ['pdf url', () => resumesApi.getPdfUrl('r1'), { method: 'GET', url: '/api/resumes/r1/pdf-url' }],
  [
    'pdf download url',
    () => resumesApi.getPdfDownloadUrl('r1'),
    { method: 'GET', url: '/api/resumes/r1/pdf-url?download=true' },
  ],
  ['roles', () => skillGapApi.getRoles(), { method: 'GET', url: '/api/skill-gap/roles' }],
  [
    'analyse',
    () => skillGapApi.analyse('backend'),
    { method: 'POST', url: '/api/skill-gap/analyse', body: { roleId: 'backend' } },
  ],
  [
    'learning roadmap',
    () => roadmapApi.generate('backend', 'rep1'),
    {
      method: 'POST',
      url: '/api/skill-gap/roadmap/generate',
      body: { roleId: 'backend', reportId: 'rep1' },
    },
  ],
  [
    'week done',
    () => roadmapApi.markComplete('rm1', 2),
    { method: 'PATCH', url: '/api/skill-gap/roadmap/rm1/milestone/2' },
  ],
  [
    'suggest projects',
    () => projectRoadmapApi.suggest('Web'),
    { method: 'POST', url: '/api/project-roadmap/suggest', body: { domain: 'Web' } },
  ],
  [
    'project roadmaps',
    () => projectRoadmapApi.list(),
    { method: 'GET', url: '/api/project-roadmap/list' },
  ],
  [
    'day done',
    () => projectRoadmapApi.markDayComplete('pr1', 3),
    { method: 'PATCH', url: '/api/project-roadmap/pr1/day/3/complete' },
  ],
  [
    'unlock days',
    () => projectRoadmapApi.unlockAll('pr1'),
    { method: 'PATCH', url: '/api/project-roadmap/pr1/unlock-all' },
  ],
  [
    'delete roadmap',
    () => projectRoadmapApi.delete('pr1'),
    { method: 'DELETE', url: '/api/project-roadmap/pr1' },
  ],
];

describe('API client requests', () => {
  it.each(CASES)('%s', async (_name, call, expected) => {
    expect(await request(call)).toMatchObject(expected);
  });
});

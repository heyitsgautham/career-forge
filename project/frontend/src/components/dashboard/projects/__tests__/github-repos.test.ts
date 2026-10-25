import { describe, expect, it } from 'vitest';
import { filterRepos, parseGithubRepoUrl, type GithubRepo } from '../github-repos';

const repo = (overrides: Partial<GithubRepo>): GithubRepo => ({
  full_name: 'asha-example/job-scout',
  name: 'job-scout',
  html_url: 'https://github.com/asha-example/job-scout',
  stars: 0,
  forks: 0,
  is_private: false,
  is_fork: false,
  ...overrides,
});

const REPOS = [
  repo({ name: 'job-scout', full_name: 'asha-example/job-scout', language: 'Python' }),
  repo({
    name: 'notes',
    full_name: 'asha-example/notes',
    is_private: true,
    description: 'Offline markdown',
  }),
  repo({ name: 'latex-lint', full_name: 'asha-example/latex-lint', language: 'TypeScript' }),
];
const names = (repos: GithubRepo[]) => repos.map((r) => r.name);

describe('filterRepos', () => {
  it('filters by visibility', () => {
    expect(names(filterRepos(REPOS, '', 'all'))).toEqual(['job-scout', 'notes', 'latex-lint']);
    expect(names(filterRepos(REPOS, '', 'private'))).toEqual(['notes']);
    expect(names(filterRepos(REPOS, '', 'public'))).toEqual(['job-scout', 'latex-lint']);
  });

  it('searches name, description and language without regard to case', () => {
    expect(names(filterRepos(REPOS, 'MARKDOWN', 'all'))).toEqual(['notes']);
    expect(names(filterRepos(REPOS, 'typescript', 'all'))).toEqual(['latex-lint']);
    expect(names(filterRepos(REPOS, '  scout ', 'all'))).toEqual(['job-scout']);
  });

  it('combines search and visibility', () => {
    expect(filterRepos(REPOS, 'notes', 'public')).toEqual([]);
  });
});

describe('parseGithubRepoUrl', () => {
  it('reads owner and name from a repository URL', () => {
    expect(parseGithubRepoUrl('https://github.com/asha-example/job-scout')).toBe(
      'asha-example/job-scout'
    );
    expect(parseGithubRepoUrl('https://github.com/asha-example/job-scout.git')).toBe(
      'asha-example/job-scout'
    );
    expect(parseGithubRepoUrl('github.com/asha-example/job-scout/tree/main/src')).toBe(
      'asha-example/job-scout'
    );
  });

  it('rejects URLs without an owner and a name', () => {
    expect(parseGithubRepoUrl('https://github.com/asha-example')).toBeNull();
    expect(parseGithubRepoUrl('https://gitlab.com/asha-example/job-scout')).toBeNull();
    expect(parseGithubRepoUrl('')).toBeNull();
  });
});

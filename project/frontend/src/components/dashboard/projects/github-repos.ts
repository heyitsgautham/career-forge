/** A repository from GET /api/projects/github/user-repos. */
export interface GithubRepo {
  full_name: string;
  name: string;
  description?: string;
  html_url: string;
  stars: number;
  forks: number;
  language?: string;
  is_private: boolean;
  is_fork: boolean;
}

export type Visibility = 'all' | 'public' | 'private';

/** Repositories matching the visibility filter and a case-insensitive search. */
export function filterRepos(repos: GithubRepo[], query: string, visibility: Visibility) {
  const q = query.trim().toLowerCase();
  return repos.filter((repo) => {
    if (visibility === 'public' && repo.is_private) return false;
    if (visibility === 'private' && !repo.is_private) return false;
    if (!q) return true;
    return (
      repo.full_name.toLowerCase().includes(q) ||
      repo.name.toLowerCase().includes(q) ||
      repo.description?.toLowerCase().includes(q) ||
      repo.language?.toLowerCase().includes(q)
    );
  });
}

/** The owner/name pair in a GitHub repository URL, or null when the URL has none. */
export function parseGithubRepoUrl(url: string): string | null {
  const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)/);
  if (!match) return null;
  return `${match[1]}/${match[2].replace('.git', '')}`;
}

/**
 * Centralized React Query key definitions and cache timing constants.
 * Import these instead of hardcoding staleTime / gcTime in each component.
 */

/* ─── Cache durations (ms) ───────────────────────────────────────────────── */
const SECONDS = 1_000;
const MINUTES = 60 * SECONDS;

export const CACHE = {
  /** Templates almost never change */
  templates: { staleTime: 30 * MINUTES, gcTime: 60 * MINUTES },

  /** Projects / GitHub repos — synced manually */
  projects: { staleTime: 5 * MINUTES, gcTime: 30 * MINUTES },

  /** Resumes list — changes after generation */
  resumes: { staleTime: 2 * MINUTES, gcTime: 15 * MINUTES },

  /** Single resume — actively edited */
  resume: { staleTime: 5 * MINUTES, gcTime: 30 * MINUTES },

  /** Job descriptions — moderate churn */
  jobs: { staleTime: 2 * MINUTES, gcTime: 15 * MINUTES },

  /** Job Scout — polling-like, keep short */
  jobScout: { staleTime: 30 * SECONDS, gcTime: 10 * MINUTES },

  /** Skill gap & roadmap — computed, rarely re-run */
  skillGap: { staleTime: 10 * MINUTES, gcTime: 30 * MINUTES },

  /** User profile — rarely changes mid-session */
  userProfile: { staleTime: 10 * MINUTES, gcTime: 30 * MINUTES },
} as const;

/* ─── Query keys ─────────────────────────────────────────────────────────── */
export const QUERY_KEYS = {
  templates: ['templates'] as const,
  template: (id: string) => ['template', id] as const,

  projects: ['projects'] as const,
  githubReposCount: ['github-repos-count'] as const,
  githubUserRepos: ['github-user-repos'] as const,

  resumes: ['resumes'] as const,
  resume: (id: string) => ['resume', id] as const,

  jobs: ['jobs'] as const,

  jobScoutMatches: ['job-scout-matches'] as const,
  jobScoutStats: ['job-scout-stats'] as const,

  userProfile: ['user-profile'] as const,
  githubStatus: ['github-status'] as const,
} as const;

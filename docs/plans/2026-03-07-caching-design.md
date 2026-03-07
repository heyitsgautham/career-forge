# Caching Design — CareerForge Frontend + Backend

**Date:** 2026-03-07  
**Status:** Approved  
**Goals:** Speed perception, reduce API calls, offline resilience

## Architecture

4-phase layered caching: React Query tuning → persistent cache → HTTP headers → prefetching.

## Phase 1: Smart Stale Times

Set `staleTime` and `gcTime` per data type based on mutation frequency:

| Query Key | staleTime | gcTime | Rationale |
|-----------|-----------|--------|-----------|
| `templates` / `template-*` | 30 min | 60 min | Almost never changes |
| `projects` / `github-repos-count` / `github-user-repos` | 5 min | 30 min | GitHub syncs are manual |
| `resumes` | 2 min | 15 min | Changes after generation |
| `resume-*` (single) | 5 min | 30 min | Edited actively |
| `jobs` | 2 min | 15 min | User adds/removes |
| `job-scout-matches` / `job-scout-stats` | 30 sec (keep) | 10 min | Polling-like |
| `skill-gap-*` / `roadmap-*` | 10 min | 30 min | Computed, rarely re-run |

Default `gcTime` bumped from 5 min (React Query default) to 15 min.

## Phase 2: Persistent Cache (IndexedDB)

- Add `@tanstack/react-query-persist-client` + `idb-keyval` for IndexedDB adapter
- Wrap `QueryClientProvider` with `PersistQueryClientProvider`
- On load: hydrate from IndexedDB → show stale data instantly → revalidate in background
- Cache buster version string for deploy-time invalidation

## Phase 3: Backend Cache-Control Headers

FastAPI middleware that sets `Cache-Control` based on route patterns:

| Route Pattern | Header |
|--------------|--------|
| `GET /api/templates*` | `private, max-age=1800, stale-while-revalidate=3600` |
| `GET /api/projects*` | `private, max-age=120, stale-while-revalidate=300` |
| `GET /api/resumes` (list) | `private, max-age=60` |
| `GET /api/resumes/{id}` | `private, max-age=300` |
| `GET /api/users/profile` | `private, max-age=600` |
| `GET /api/skill-gap*` | `private, max-age=600` |
| `GET /api/jobs*` | `private, max-age=120` |
| `GET /api/job-scout*` | `no-cache` |
| All POST/PUT/DELETE | `no-store` |

All user-specific endpoints use `private` to prevent CDN caching of personal data.

## Phase 4: Route Prefetching

- Dashboard layout prefetches all tab data on mount via `queryClient.prefetchQuery()`
- Sidebar hover prefetches the hovered tab's data
- Existing optimistic update patterns extended where missing

## Not Doing

- **Service Worker:** Persistent React Query cache gives 90% benefit at 10% complexity
- **ISR/SSR:** All pages are authenticated; no public SEO pages need it
- **CDN caching:** Deferred until CloudFront production deployment

## Files Changed

**Frontend:**
- `src/app/providers.tsx` — QueryClient config, persistent cache setup
- `src/lib/query-keys.ts` — Centralized query key + cache config constants (new)
- `src/components/dashboard/resumes-list.tsx` — staleTime/gcTime
- `src/components/dashboard/projects-list.tsx` — staleTime/gcTime
- `src/components/dashboard/templates-list.tsx` — staleTime/gcTime
- `src/components/dashboard/jobs-list.tsx` — staleTime/gcTime
- `src/components/dashboard/job-scout-shell.tsx` — staleTime/gcTime
- `src/app/dashboard/page.tsx` — user profile → React Query, prefetch on mount + hover
- `package.json` — new deps

**Backend:**
- `app/core/cache_middleware.py` — Cache-Control header middleware (new)
- `app/main.py` — register middleware

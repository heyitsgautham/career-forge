import { useCallback, useEffect } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { jobMatchApi, projectsApi, resumesApi, skillGapApi } from '@/lib/api';

interface TabQuery {
  queryKey: QueryKey;
  queryFn: () => Promise<unknown>;
  staleTime: number;
}

/** The query each tab opens with, so hovering its sidebar entry can load it early. */
export const TAB_QUERIES: Record<string, TabQuery> = {
  resumes: {
    queryKey: ['resumes'],
    queryFn: () => resumesApi.list().then((r) => r.data),
    staleTime: 2 * 60 * 1000,
  },
  projects: {
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  },
  'skill-gap': {
    queryKey: ['skill-gap-roles'],
    queryFn: () => skillGapApi.getRoles().then((r) => r.data.roles || []),
    staleTime: 60 * 60 * 1000,
  },
  'job-scout': {
    queryKey: ['jobs', 'matches'],
    queryFn: () => jobMatchApi.list().then((r) => r.data),
    staleTime: 30_000,
  },
};

/** Tabs whose data loads as soon as the dashboard opens. */
const PREFETCH_ON_MOUNT = ['resumes', 'projects', 'skill-gap'];

/**
 * Loads the common tabs' data when the dashboard mounts and returns a
 * function that loads any other tab's data, for the sidebar's hover handler.
 */
export function usePrefetchTabs() {
  const queryClient = useQueryClient();

  const prefetchTab = useCallback(
    (tab: string) => {
      const query = TAB_QUERIES[tab];
      if (query) void queryClient.prefetchQuery(query);
    },
    [queryClient]
  );

  useEffect(() => {
    PREFETCH_ON_MOUNT.forEach(prefetchTab);
  }, [prefetchTab]);

  return prefetchTab;
}

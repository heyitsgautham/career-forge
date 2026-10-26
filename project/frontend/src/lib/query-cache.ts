import type { QueryClient } from '@tanstack/react-query';
import type { Persister } from '@tanstack/react-query-persist-client';
import { del, get, set } from 'idb-keyval';

/**
 * Bump this when deploying breaking data-shape changes.
 * Old caches with a different buster are automatically discarded.
 */
export const CACHE_BUSTER = 'v1';

/** IndexedDB key that holds the persisted React Query cache. */
export const QUERY_CACHE_KEY = `careerforge-rq-cache-${CACHE_BUSTER}`;

/** IndexedDB-backed persister for the React Query cache. */
export function createIDBPersister(): Persister {
  return {
    persistClient: async (client) => {
      await set(QUERY_CACHE_KEY, client);
    },
    restoreClient: async () => {
      return await get(QUERY_CACHE_KEY);
    },
    removeClient: async () => {
      await del(QUERY_CACHE_KEY);
    },
  };
}

/**
 * Forgets every cached response, in memory and in IndexedDB.
 *
 * Call it whenever the signed-in user changes. Otherwise the next person to
 * sign in on the same browser sees the previous user's name, email and data
 * until each query goes stale.
 */
export async function clearCachedData(queryClient?: QueryClient): Promise<void> {
  queryClient?.clear();
  try {
    await del(QUERY_CACHE_KEY);
  } catch {
    // IndexedDB can be unavailable, for example in private windows; nothing was persisted then.
  }
}

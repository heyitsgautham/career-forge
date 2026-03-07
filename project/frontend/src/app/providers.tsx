'use client';

import { QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import type { Persister } from '@tanstack/react-query-persist-client';
import { useState } from 'react';
import { get, set, del } from 'idb-keyval';

/**
 * Bump this when deploying breaking data-shape changes.
 * Old caches with a different buster are automatically discarded.
 */
const CACHE_BUSTER = 'v1';

/** IndexedDB-backed persister for React Query cache */
function createIDBPersister(): Persister {
  const idbKey = `careerforge-rq-cache-${CACHE_BUSTER}`;
  return {
    persistClient: async (client) => {
      await set(idbKey, client);
    },
    restoreClient: async () => {
      return await get(idbKey);
    },
    removeClient: async () => {
      await del(idbKey);
    },
  };
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 2 * 60 * 1000,   // 2 min default (overridden per-query)
            gcTime: 15 * 60 * 1000,     // 15 min garbage collection
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const [persister] = useState(() => createIDBPersister());

  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 24 * 60 * 60 * 1000,  // discard cache older than 24 hours
        buster: CACHE_BUSTER,
      }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}

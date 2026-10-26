'use client';

import { QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { useState } from 'react';
import { CACHE_BUSTER, createIDBPersister } from '@/lib/query-cache';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 2 * 60 * 1000, // 2 min default (overridden per-query)
            gcTime: 15 * 60 * 1000, // 15 min garbage collection
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
        maxAge: 24 * 60 * 60 * 1000, // discard cache older than 24 hours
        buster: CACHE_BUSTER,
      }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}

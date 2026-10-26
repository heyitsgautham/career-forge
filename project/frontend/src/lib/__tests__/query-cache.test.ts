import { QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const idb = vi.hoisted(() => {
  const store = new Map<string, unknown>();
  return {
    store,
    get: vi.fn(async (k: string) => store.get(k)),
    set: vi.fn(async (k: string, v: unknown) => void store.set(k, v)),
    del: vi.fn(async (k: string) => void store.delete(k)),
  };
});
vi.mock('idb-keyval', () => idb);

import { QUERY_CACHE_KEY, clearCachedData, createIDBPersister } from '@/lib/query-cache';

beforeEach(() => {
  idb.store.clear();
  vi.clearAllMocks();
});

describe('createIDBPersister', () => {
  it('saves, restores and removes the cache under one versioned key', async () => {
    const persister = createIDBPersister();
    const snapshot = { timestamp: 1, buster: 'v1', clientState: { queries: [], mutations: [] } };
    await persister.persistClient(snapshot);
    expect(idb.store.get(QUERY_CACHE_KEY)).toBe(snapshot);
    expect(await persister.restoreClient()).toBe(snapshot);
    await persister.removeClient();
    expect(idb.store.has(QUERY_CACHE_KEY)).toBe(false);
  });
});

describe('clearCachedData', () => {
  it('empties the in-memory cache and deletes the persisted copy', async () => {
    const client = new QueryClient();
    client.setQueryData(['user-profile'], { name: 'Asha Example' });
    idb.store.set(QUERY_CACHE_KEY, { old: true });

    await clearCachedData(client);

    expect(client.getQueryData(['user-profile'])).toBeUndefined();
    expect(idb.store.has(QUERY_CACHE_KEY)).toBe(false);
  });

  it('still clears memory when IndexedDB is unavailable', async () => {
    idb.del.mockRejectedValueOnce(new Error('no indexedDB'));
    const client = new QueryClient();
    client.setQueryData(['projects'], []);
    await expect(clearCachedData(client)).resolves.toBeUndefined();
    expect(client.getQueryData(['projects'])).toBeUndefined();
  });
});

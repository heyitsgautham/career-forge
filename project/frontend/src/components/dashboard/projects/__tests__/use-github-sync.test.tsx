import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ githubApi: { sync: vi.fn(), getIngestStatus: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { SYNC_POLL_MS, useGithubSync } from '../use-github-sync';

function renderSync() {
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...renderHook(() => useGithubSync(), { wrapper }), invalidate };
}

const status = (s: string, summary: unknown = null) => ({ data: { status: s, summary } });

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  api.githubApi.sync.mockResolvedValue({});
});
afterEach(() => vi.useRealTimers());

describe('useGithubSync', () => {
  it('polls until the sync is done, then refreshes projects and reports the count', async () => {
    api.githubApi.getIngestStatus
      .mockResolvedValueOnce(status('in_progress'))
      .mockResolvedValueOnce(status('done', { processed: 3, failed: 0 }));
    const { result, invalidate } = renderSync();

    await act(() => result.current.startSync());
    expect(result.current.syncing).toBe(true);
    expect(result.current.syncStatus).toBe('in_progress');

    await act(() => vi.advanceTimersByTimeAsync(SYNC_POLL_MS));
    expect(result.current.syncing).toBe(false);
    expect(result.current.syncSummary).toEqual({ processed: 3, failed: 0 });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['projects'] });
    expect(toast).toHaveBeenCalledWith({
      title: 'Sync complete',
      description: '3 existing projects refreshed.',
    });

    await act(() => vi.advanceTimersByTimeAsync(SYNC_POLL_MS * 3));
    expect(api.githubApi.getIngestStatus).toHaveBeenCalledTimes(2);
  });

  it('uses the singular for one refreshed project', async () => {
    api.githubApi.getIngestStatus.mockResolvedValue(status('completed', { processed: 1 }));
    const { result } = renderSync();
    await act(() => result.current.startSync());
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: '1 existing project refreshed.' })
    );
  });

  it('stops and warns when the sync fails', async () => {
    api.githubApi.getIngestStatus.mockResolvedValue(status('failed'));
    const { result } = renderSync();
    await act(() => result.current.startSync());
    expect(result.current.syncing).toBe(false);
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Sync failed' }));
  });

  it('keeps polling when the start request fails because a sync is already running', async () => {
    api.githubApi.sync.mockRejectedValue(new Error('409'));
    api.githubApi.getIngestStatus.mockResolvedValue(status('in_progress'));
    const { result } = renderSync();
    await act(() => result.current.startSync());
    await act(() => vi.advanceTimersByTimeAsync(SYNC_POLL_MS * 2));
    expect(api.githubApi.getIngestStatus).toHaveBeenCalledTimes(3);
    expect(result.current.syncing).toBe(true);
  });

  it('gives up quietly when the status endpoint errors', async () => {
    api.githubApi.getIngestStatus.mockRejectedValue(new Error('network'));
    const { result } = renderSync();
    await act(() => result.current.startSync());
    expect(result.current.syncing).toBe(false);
    await act(() => vi.advanceTimersByTimeAsync(SYNC_POLL_MS * 2));
    expect(api.githubApi.getIngestStatus).toHaveBeenCalledTimes(1);
    expect(toast).not.toHaveBeenCalled();
  });

  it('stops polling on unmount', async () => {
    api.githubApi.getIngestStatus.mockResolvedValue(status('in_progress'));
    const { result, unmount } = renderSync();
    await act(() => result.current.startSync());
    unmount();
    await vi.advanceTimersByTimeAsync(SYNC_POLL_MS * 3);
    expect(api.githubApi.getIngestStatus).toHaveBeenCalledTimes(1);
  });
});

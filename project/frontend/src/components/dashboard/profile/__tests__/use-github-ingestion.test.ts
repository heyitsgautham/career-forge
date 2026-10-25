import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  githubApi: { listProjects: vi.fn(), getIngestStatus: vi.fn(), ingest: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { INGEST_POLL_MS, MAX_POLLS, useGithubIngestion } from '../use-github-ingestion';

const status = (s: string, summary: unknown = null) => ({ data: { status: s, summary } });
const PROJECTS = [{ projectId: 'p1', name: 'job-scout' }];

async function mount(onProfileStale = vi.fn().mockResolvedValue(undefined)) {
  const hook = renderHook(() => useGithubIngestion(onProfileStale));
  await act(() => vi.advanceTimersByTimeAsync(0));
  return { ...hook, onProfileStale };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  api.githubApi.listProjects.mockResolvedValue({ data: PROJECTS });
  api.githubApi.getIngestStatus.mockResolvedValue(status('done', { processed: 3 }));
});
afterEach(() => vi.useRealTimers());

describe('useGithubIngestion', () => {
  it('loads the last status and the projects on mount without starting a sync', async () => {
    const { result } = await mount();
    expect(result.current.projects).toEqual(PROJECTS);
    expect(result.current.ingestionStatus).toBe('done');
    expect(result.current.ingesting).toBe(false);
    expect(api.githubApi.ingest).not.toHaveBeenCalled();
  });

  it('resumes polling when a sync was already running', async () => {
    api.githubApi.getIngestStatus
      .mockResolvedValueOnce(status('in_progress'))
      .mockResolvedValueOnce(status('in_progress'))
      .mockResolvedValue(status('done', { processed: 4 }));
    const { result, onProfileStale } = await mount();
    expect(result.current.ingesting).toBe(true);

    await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS));
    expect(result.current.ingesting).toBe(false);
    expect(onProfileStale).toHaveBeenCalledOnce();
    expect(toast).toHaveBeenCalledWith({
      title: 'Import Complete',
      description: '4 projects imported.',
    });
  });

  it('refreshes synchronously when the API finishes the ingest inline', async () => {
    api.githubApi.ingest.mockResolvedValue({});
    const { result, onProfileStale } = await mount();
    await act(() => result.current.refreshRepos());
    expect(api.githubApi.ingest).toHaveBeenCalledWith(false);
    expect(onProfileStale).toHaveBeenCalledOnce();
    expect(result.current.ingestionStatus).toBe('done');
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Sync complete' }));
  });

  it('falls back to polling and reports a failed import', async () => {
    api.githubApi.ingest.mockRejectedValue(new Error('202'));
    api.githubApi.getIngestStatus
      .mockResolvedValueOnce(status('none'))
      .mockResolvedValue(status('failed'));
    const { result } = await mount();
    await act(() => result.current.refreshRepos());
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(result.current.ingesting).toBe(false);
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Import Failed' }));
  });

  it('reports a stale import as timed out', async () => {
    api.githubApi.ingest.mockRejectedValue(new Error('202'));
    api.githubApi.getIngestStatus
      .mockResolvedValueOnce(status('none'))
      .mockResolvedValue(status('stale'));
    const { result } = await mount();
    await act(() => result.current.refreshRepos());
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        description: 'The previous import did not complete. Please try again.',
      })
    );
  });

  it('gives up after two minutes of polling', async () => {
    api.githubApi.ingest.mockRejectedValue(new Error('202'));
    api.githubApi.getIngestStatus
      .mockResolvedValueOnce(status('none'))
      .mockResolvedValue(status('in_progress'));
    const { result } = await mount();
    await act(() => result.current.refreshRepos());
    await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS * MAX_POLLS));
    expect(result.current.ingesting).toBe(false);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'The import is taking too long. Please try again.' })
    );
  });
});

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ projectsApi: { importGithub: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { REVEAL_STAGGER_MS, SIMULATED_STEP_MS, useProjectImport } from '../use-project-import';

function renderImport() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useProjectImport(), { wrapper });
}

const statuses = (items: { status: string }[]) => items.map((i) => i.status);

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

describe('useProjectImport', () => {
  it('queues every repository with the first one processing', async () => {
    api.projectsApi.importGithub.mockReturnValue(new Promise(() => {}));
    const { result } = renderImport();

    act(() => result.current.startImport(['asha/one', 'asha/two', 'asha/three']));
    await act(() => vi.advanceTimersByTimeAsync(0));

    expect(result.current.importProgress).toEqual([
      { name: 'one', fullName: 'asha/one', status: 'processing' },
      { name: 'two', fullName: 'asha/two', status: 'queued' },
      { name: 'three', fullName: 'asha/three', status: 'queued' },
    ]);
    expect(api.projectsApi.importGithub).toHaveBeenCalledWith([
      'asha/one',
      'asha/two',
      'asha/three',
    ]);
  });

  it('moves the processing marker one repository per step while the API works', async () => {
    api.projectsApi.importGithub.mockReturnValue(new Promise(() => {}));
    const { result } = renderImport();
    act(() => result.current.startImport(['a/1', 'a/2', 'a/3']));

    // Regression: the state updater read the step counter after it had already
    // moved on, so the first step marked two repositories as processing.
    await act(() => vi.advanceTimersByTimeAsync(SIMULATED_STEP_MS));
    expect(statuses(result.current.importProgress)).toEqual(['processing', 'processing', 'queued']);
    await act(() => vi.advanceTimersByTimeAsync(SIMULATED_STEP_MS * 3));
    expect(statuses(result.current.importProgress)).toEqual([
      'processing',
      'processing',
      'processing',
    ]);
  });

  it('reveals each result in turn, toasts, then clears the skeletons', async () => {
    api.projectsApi.importGithub.mockResolvedValue({
      data: {
        results: [
          { full_name: 'a/1', status: 'success' },
          { full_name: 'a/2', status: 'error', error: 'empty repo' },
        ],
      },
    });
    const { result } = renderImport();
    act(() => result.current.startImport(['a/1', 'a/2']));

    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(statuses(result.current.importProgress)).toEqual(['done', 'queued']);

    await act(() => vi.advanceTimersByTimeAsync(REVEAL_STAGGER_MS));
    expect(statuses(result.current.importProgress)).toEqual(['done', 'failed']);

    await act(() => vi.advanceTimersByTimeAsync(REVEAL_STAGGER_MS));
    expect(toast).toHaveBeenCalledWith({
      title: '1 imported, 1 failed',
      description: 'Failed: a/2',
    });

    await act(() => vi.advanceTimersByTimeAsync(3500));
    expect(result.current.importProgress).toEqual([]);
  });

  it('matches results without a name to the next unfinished repository', async () => {
    api.projectsApi.importGithub.mockResolvedValue({ data: { results: [{ status: 'success' }] } });
    const { result } = renderImport();
    act(() => result.current.startImport(['a/1']));
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(statuses(result.current.importProgress)).toEqual(['done']);
  });

  it('marks everything failed and explains why when the request fails', async () => {
    api.projectsApi.importGithub.mockRejectedValue({
      response: { data: { detail: 'GitHub token expired' } },
    });
    const { result } = renderImport();
    act(() => result.current.startImport(['a/1', 'a/2']));

    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(statuses(result.current.importProgress)).toEqual(['failed', 'failed']);
    expect(toast).toHaveBeenCalledWith({
      title: 'Failed to import repositories',
      description: 'GitHub token expired',
      variant: 'destructive',
    });

    await act(() => vi.advanceTimersByTimeAsync(SIMULATED_STEP_MS));
    expect(statuses(result.current.importProgress)).toEqual(['failed', 'failed']);

    await act(() => vi.advanceTimersByTimeAsync(4000));
    expect(result.current.importProgress).toEqual([]);
  });
});

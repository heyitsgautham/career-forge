import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SUGGESTION, makeRoadmap } from '@/test/roadmaps';

const api = vi.hoisted(() => ({
  projectRoadmapApi: {
    list: vi.fn(),
    suggest: vi.fn(),
    plan: vi.fn(),
    get: vi.fn(),
    markDayComplete: vi.fn(),
    unlockAll: vi.fn(),
    delete: vi.fn(),
  },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { useProjectRoadmap } from '../use-project-roadmap';

function renderRoadmap() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useProjectRoadmap(), { wrapper });
}

const fail = (detail: string) => ({ response: { data: { detail } } });

beforeEach(() => {
  vi.clearAllMocks();
  api.projectRoadmapApi.list.mockResolvedValue({ data: { roadmaps: [makeRoadmap(2)] } });
});

describe('useProjectRoadmap', () => {
  it('loads saved roadmaps as history', async () => {
    const { result } = renderRoadmap();
    await waitFor(() => expect(result.current.history).toHaveLength(1));
    expect(result.current.step).toBe('form');
  });

  it('asks for a domain before suggesting', async () => {
    const { result } = renderRoadmap();
    await act(() => result.current.suggest('   '));
    expect(api.projectRoadmapApi.suggest).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Enter a domain' }));
  });

  it('moves to the picker once suggestions arrive', async () => {
    api.projectRoadmapApi.suggest.mockResolvedValue({
      data: { domain: 'Backend Development', projects: [SUGGESTION] },
    });
    const { result } = renderRoadmap();
    await act(() => result.current.suggest(' Backend Development '));
    expect(api.projectRoadmapApi.suggest).toHaveBeenCalledWith('Backend Development');
    expect(result.current.step).toBe('pick');
    expect(result.current.suggestions?.projects).toEqual([SUGGESTION]);
    expect(result.current.suggesting).toBe(false);
  });

  it('explains a failed suggestion', async () => {
    api.projectRoadmapApi.suggest.mockRejectedValue(fail('Bedrock throttled'));
    const { result } = renderRoadmap();
    await act(() => result.current.suggest('Web'));
    expect(result.current.step).toBe('form');
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Failed to get suggestions',
        description: 'Bedrock throttled',
      })
    );
  });

  it('plans the picked project and opens its path', async () => {
    api.projectRoadmapApi.suggest.mockResolvedValue({
      data: { domain: 'Backend Development', projects: [SUGGESTION] },
    });
    api.projectRoadmapApi.plan.mockResolvedValue({ data: makeRoadmap() });
    const { result } = renderRoadmap();
    await act(() => result.current.suggest('Backend Development'));
    await act(() => result.current.pick(SUGGESTION));

    expect(api.projectRoadmapApi.plan).toHaveBeenCalledWith({
      domain: 'Backend Development',
      projectTitle: 'Job board API',
      projectDescription: 'A REST API for postings',
      techStack: ['Python', 'FastAPI'],
    });
    expect(result.current.step).toBe('path');
    expect(result.current.activeRoadmap?.projectRoadmapId).toBe('pr1');
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Roadmap ready!' }));
  });

  it('stays on the picker when planning fails', async () => {
    api.projectRoadmapApi.suggest.mockResolvedValue({
      data: { domain: 'Web', projects: [SUGGESTION] },
    });
    api.projectRoadmapApi.plan.mockRejectedValue(fail('Too many requests'));
    const { result } = renderRoadmap();
    await act(() => result.current.suggest('Web'));
    await act(() => result.current.pick(SUGGESTION));
    expect(result.current.step).toBe('pick');
    expect(result.current.planning).toBe(false);
  });

  it('completes a day and refreshes the open day', async () => {
    api.projectRoadmapApi.get.mockResolvedValue({ data: makeRoadmap(0) });
    api.projectRoadmapApi.markDayComplete.mockResolvedValue({ data: makeRoadmap(1) });
    const { result } = renderRoadmap();
    await act(() => result.current.loadRoadmap('pr1'));
    expect(result.current.step).toBe('path');

    await act(() => result.current.completeDay(1));

    expect(api.projectRoadmapApi.markDayComplete).toHaveBeenCalledWith('pr1', 1);
    expect(result.current.selectedDay?.completedAt).toBeTruthy();
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Day 1 complete!' }));
  });

  it('reports a day that could not be completed', async () => {
    api.projectRoadmapApi.get.mockResolvedValue({ data: makeRoadmap(0) });
    api.projectRoadmapApi.markDayComplete.mockRejectedValue(fail('day 1 is not yet completed'));
    const { result } = renderRoadmap();
    await act(() => result.current.loadRoadmap('pr1'));
    await act(() => result.current.completeDay(2));
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Failed to update',
        description: 'day 1 is not yet completed',
      })
    );
    expect(result.current.completing).toBe(false);
  });

  it('warns when a saved roadmap will not load', async () => {
    api.projectRoadmapApi.get.mockRejectedValue(new Error('404'));
    const { result } = renderRoadmap();
    await act(() => result.current.loadRoadmap('gone'));
    expect(result.current.step).toBe('form');
    expect(toast).toHaveBeenCalledWith({ title: 'Failed to load roadmap', variant: 'destructive' });
  });

  it('unlocks every day', async () => {
    api.projectRoadmapApi.get.mockResolvedValue({ data: makeRoadmap(0) });
    api.projectRoadmapApi.unlockAll.mockResolvedValue({
      data: makeRoadmap(0, { unlockedAll: true }),
    });
    const { result } = renderRoadmap();
    await act(() => result.current.loadRoadmap('pr1'));
    await act(() => result.current.unlockAll());
    expect(result.current.activeRoadmap?.unlockedAll).toBe(true);
    expect(result.current.unlocking).toBe(false);
  });

  it('closes the open roadmap when it is deleted', async () => {
    api.projectRoadmapApi.get.mockResolvedValue({ data: makeRoadmap(0) });
    api.projectRoadmapApi.delete.mockResolvedValue({ data: { deleted: true } });
    const { result } = renderRoadmap();
    await act(() => result.current.loadRoadmap('pr1'));
    await act(() => result.current.deleteRoadmap('pr1'));
    expect(result.current.step).toBe('form');
    expect(result.current.activeRoadmap).toBeNull();
    expect(toast).toHaveBeenCalledWith({ title: 'Roadmap deleted' });
  });

  it('keeps the roadmap and explains a failed delete', async () => {
    api.projectRoadmapApi.delete.mockRejectedValue(fail('Not yours'));
    const { result } = renderRoadmap();
    await act(() => result.current.deleteRoadmap('pr9'));
    expect(result.current.deleting).toBeNull();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Failed to delete', description: 'Not yours' })
    );
  });

  it('goes back to the form from an open roadmap', async () => {
    api.projectRoadmapApi.get.mockResolvedValue({ data: makeRoadmap(0) });
    const { result } = renderRoadmap();
    await act(() => result.current.loadRoadmap('pr1'));
    act(() => result.current.closeRoadmap());
    expect(result.current.step).toBe('form');
    expect(result.current.activeRoadmap).toBeNull();
  });
});

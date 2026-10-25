import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  projectsApi: { delete: vi.fn(), deleteAll: vi.fn(), list: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { useProjectDeletes } from '../use-project-deletes';

const PROJECTS = [
  { id: 'p1', title: 'job-scout' },
  { id: 'p2', title: 'notes-app' },
];

function renderDeletes() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  client.setQueryData(['projects'], PROJECTS);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...renderHook(() => useProjectDeletes(), { wrapper }), client };
}

beforeEach(() => vi.clearAllMocks());

describe('useProjectDeletes', () => {
  it('removes one project from the cache before the API answers', async () => {
    let finish: (v: unknown) => void = () => {};
    api.projectsApi.delete.mockReturnValue(new Promise((r) => (finish = r)));
    const { result, client } = renderDeletes();

    act(() => result.current.deleteProject('p1'));

    await waitFor(() => expect(client.getQueryData(['projects'])).toEqual([PROJECTS[1]]));
    expect(api.projectsApi.delete).toHaveBeenCalledWith('p1');
    await act(async () => finish({}));
  });

  it('puts the project back and warns when the delete fails', async () => {
    api.projectsApi.delete.mockRejectedValue(new Error('500'));
    const { result, client } = renderDeletes();

    act(() => result.current.deleteProject('p1'));

    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Failed to delete project',
        variant: 'destructive',
      })
    );
    expect(client.getQueryData(['projects'])).toEqual(PROJECTS);
  });

  it('empties the cache on clear-all and reports the server message', async () => {
    api.projectsApi.deleteAll.mockResolvedValue({ data: { message: 'Deleted 2 projects' } });
    const { result, client } = renderDeletes();

    act(() => result.current.clearAll());

    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'All projects cleared',
        description: 'Deleted 2 projects',
      })
    );
    expect(client.getQueryData(['projects'])).toEqual([]);
  });

  it('restores every project when clear-all fails', async () => {
    api.projectsApi.deleteAll.mockRejectedValue(new Error('500'));
    const { result, client } = renderDeletes();

    act(() => result.current.clearAll());

    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Failed to clear projects',
        variant: 'destructive',
      })
    );
    expect(client.getQueryData(['projects'])).toEqual(PROJECTS);
    expect(result.current.clearing).toBe(false);
  });
});

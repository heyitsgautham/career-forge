import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  resumesApi: { list: vi.fn() },
  projectsApi: { list: vi.fn() },
  skillGapApi: { getRoles: vi.fn() },
  jobMatchApi: { list: vi.fn() },
}));
vi.mock('@/lib/api', () => api);

import { usePrefetchTabs } from '@/components/dashboard/tab-prefetch';

function renderPrefetch() {
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...renderHook(() => usePrefetchTabs(), { wrapper }), client };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.resumesApi.list.mockResolvedValue({ data: [{ id: 'r1' }] });
  api.projectsApi.list.mockResolvedValue({ data: [] });
  api.skillGapApi.getRoles.mockResolvedValue({ data: { roles: [{ roleId: 'backend' }] } });
  api.jobMatchApi.list.mockResolvedValue({ data: [{ jobId: 'j1' }] });
});

describe('usePrefetchTabs', () => {
  it('loads resumes, projects and skill-gap roles when the dashboard opens', async () => {
    const { client } = renderPrefetch();
    await waitFor(() =>
      expect(client.getQueryData(['skill-gap-roles'])).toEqual([{ roleId: 'backend' }])
    );
    expect(client.getQueryData(['resumes'])).toEqual([{ id: 'r1' }]);
    expect(api.jobMatchApi.list).not.toHaveBeenCalled();
  });

  it('loads a tab on hover and ignores tabs without a query', async () => {
    const { result } = renderPrefetch();
    act(() => {
      result.current('job-scout');
      result.current('profile');
    });
    await waitFor(() => expect(api.jobMatchApi.list).toHaveBeenCalledOnce());
  });
});

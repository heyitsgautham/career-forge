import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TOKEN_U1, makeApplication } from '@/test/applications';

const api = vi.hoisted(() => ({
  applicationsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  jobMatchApi: { list: vi.fn(), track: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { useApplications } from '../use-applications';

function renderApps(onCreated = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...renderHook(() => useApplications(onCreated), { wrapper }), client, onCreated };
}

const APPS = [
  makeApplication({ applicationId: 'a1', jobId: 'j1' }),
  makeApplication({ applicationId: 'a2', jobId: 'manual-1', status: 'interviewing' }),
];

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', TOKEN_U1);
  api.applicationsApi.list.mockResolvedValue({ data: APPS });
  api.jobMatchApi.list.mockResolvedValue({ data: [] });
  api.jobMatchApi.track.mockResolvedValue({});
  api.applicationsApi.update.mockResolvedValue({});
});
afterEach(() => localStorage.clear());

describe('useApplications', () => {
  it("loads the signed-in user's applications", async () => {
    const { result } = renderApps();
    await waitFor(() => expect(result.current.applications).toHaveLength(2));
    expect(api.applicationsApi.list).toHaveBeenCalledWith('u1');
  });

  it('skips the request when nobody is signed in', async () => {
    localStorage.clear();
    const { result } = renderApps();
    await waitFor(() => expect(api.jobMatchApi.list).toHaveBeenCalled());
    expect(api.applicationsApi.list).not.toHaveBeenCalled();
    expect(result.current.applications).toEqual([]);
  });

  it('moves an application at once and mirrors the status into Job Scout', async () => {
    const { result, client } = renderApps();
    await waitFor(() => expect(result.current.applications).toHaveLength(2));

    act(() => result.current.moveApplication('a1', 'offered'));

    expect(client.getQueryData<typeof APPS>(['applications', 'u1'])?.[0].status).toBe('offered');
    await waitFor(() =>
      expect(api.applicationsApi.update).toHaveBeenCalledWith('a1', { status: 'offered' })
    );
    expect(api.jobMatchApi.track).toHaveBeenCalledWith('j1', 'offered');
  });

  it('does not sync hand-entered applications to Job Scout', async () => {
    const { result } = renderApps();
    await waitFor(() => expect(result.current.applications).toHaveLength(2));
    act(() => result.current.moveApplication('a2', 'rejected'));
    await waitFor(() => expect(api.applicationsApi.update).toHaveBeenCalled());
    expect(api.jobMatchApi.track).not.toHaveBeenCalled();
  });

  it('refetches and warns when a move fails', async () => {
    api.applicationsApi.update.mockRejectedValue({ response: { data: { detail: 'Locked' } } });
    const { result } = renderApps();
    await waitFor(() => expect(result.current.applications).toHaveLength(2));
    act(() => result.current.moveApplication('a1', 'offered'));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to update status', description: 'Locked' })
      )
    );
    await waitFor(() => expect(api.applicationsApi.list).toHaveBeenCalledTimes(2));
  });

  it('creates an application and calls back', async () => {
    api.applicationsApi.create.mockResolvedValue({});
    const { result, onCreated } = renderApps();
    const data = {
      jobId: 'manual-2',
      companyName: 'Demo Corp',
      roleTitle: 'ML Intern',
      notes: '',
      url: '',
    };
    act(() => result.current.createApplication(data));
    await waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
    expect(api.applicationsApi.create).toHaveBeenCalledWith(data);
    expect(toast).toHaveBeenCalledWith({ title: 'Application added!' });
  });

  it('keeps the form open and explains a failed create', async () => {
    api.applicationsApi.create.mockRejectedValue({ response: { data: { detail: 'Duplicate' } } });
    const { result, onCreated } = renderApps();
    act(() =>
      result.current.createApplication({
        jobId: 'j1',
        companyName: 'x',
        roleTitle: 'y',
        notes: '',
        url: '',
      })
    );
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(expect.objectContaining({ description: 'Duplicate' }))
    );
    expect(onCreated).not.toHaveBeenCalled();
  });

  it('removes an application', async () => {
    api.applicationsApi.delete.mockResolvedValue({});
    const { result } = renderApps();
    act(() => result.current.removeApplication('a1'));
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Application removed' }));
    expect(api.applicationsApi.delete).toHaveBeenCalledWith('a1');
  });
});

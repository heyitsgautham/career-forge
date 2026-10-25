import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { makeJob } from '@/test/fixtures';

const api = vi.hoisted(() => ({
  jobMatchApi: {
    list: vi.fn(),
    stats: vi.fn(),
    schedulerStatus: vi.fn(),
    getTracking: vi.fn(),
    track: vi.fn(),
  },
  resumesApi: { list: vi.fn() },
  tailorApi: { generate: vi.fn() },
  applicationsApi: { list: vi.fn(), update: vi.fn(), create: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { useJobScoutData } from '../use-job-scout-data';

const TOKEN = `h.${btoa(JSON.stringify({ sub: 'u1' }))}.s`;

function renderData() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useJobScoutData(), { wrapper });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', TOKEN);
  api.jobMatchApi.list.mockResolvedValue({ data: [makeJob({ jobId: 'j1' })] });
  api.jobMatchApi.stats.mockResolvedValue({ data: { totalJobs: 1 } });
  api.jobMatchApi.schedulerStatus.mockResolvedValue({ data: { nextRunTime: null } });
  api.jobMatchApi.getTracking.mockResolvedValue({ data: {} });
  api.jobMatchApi.track.mockResolvedValue({});
  api.resumesApi.list.mockResolvedValue({
    data: [{ id: 'r1', type: 'tailored', job_id: 'j0' }],
  });
  api.applicationsApi.list.mockResolvedValue({ data: [] });
  api.applicationsApi.create.mockResolvedValue({});
  api.applicationsApi.update.mockResolvedValue({});
});
afterEach(() => localStorage.clear());

describe('useJobScoutData', () => {
  it('loads jobs, stats and the tailored resume map', async () => {
    const { result } = renderData();
    await waitFor(() => expect(result.current.jobs).toHaveLength(1));
    await waitFor(() => expect(result.current.tailoredResumes).toEqual({ j0: 'r1' }));
    expect(result.current.stats).toEqual({ totalJobs: 1 });
    expect(api.applicationsApi.list).toHaveBeenCalledWith('u1');
  });

  it('creates an application when a job first reaches a Kanban status', async () => {
    const { result } = renderData();
    await waitFor(() => expect(result.current.jobs).toHaveLength(1));

    act(() => result.current.track('j1', 'applied'));

    await waitFor(() => expect(api.applicationsApi.create).toHaveBeenCalled());
    expect(api.jobMatchApi.track).toHaveBeenCalledWith('j1', 'applied');
    expect(api.applicationsApi.create).toHaveBeenCalledWith({
      jobId: 'j1',
      companyName: 'Sample Labs',
      roleTitle: 'Backend Intern',
      url: 'https://jobs.example.com/j1',
      status: 'applied',
    });
  });

  it('updates the existing application instead of creating a second one', async () => {
    api.applicationsApi.list.mockResolvedValue({
      data: [{ applicationId: 'a1', jobId: 'j1', status: 'applied' }],
    });
    const { result } = renderData();
    await waitFor(() => expect(api.applicationsApi.list).toHaveBeenCalled());
    await waitFor(() => expect(result.current.jobs).toHaveLength(1));

    act(() => result.current.track('j1', 'interviewing'));

    await waitFor(() =>
      expect(api.applicationsApi.update).toHaveBeenCalledWith('a1', { status: 'interviewing' })
    );
    expect(api.applicationsApi.create).not.toHaveBeenCalled();
  });

  it('keeps statuses outside the Kanban board out of the pipeline', async () => {
    const { result } = renderData();
    act(() => result.current.track('j1', 'saved'));
    await waitFor(() => expect(api.jobMatchApi.track).toHaveBeenCalledWith('j1', 'saved'));
    expect(api.applicationsApi.create).not.toHaveBeenCalled();
    expect(api.applicationsApi.update).not.toHaveBeenCalled();
  });

  it('swallows a pipeline sync failure because the status itself saved', async () => {
    api.applicationsApi.create.mockRejectedValue(new Error('down'));
    const { result } = renderData();
    await waitFor(() => expect(result.current.jobs).toHaveLength(1));
    act(() => result.current.track('j1', 'offered'));
    await waitFor(() => expect(api.applicationsApi.create).toHaveBeenCalled());
    expect(toast).not.toHaveBeenCalled();
  });

  it('warns when the status itself fails to save', async () => {
    api.jobMatchApi.track.mockRejectedValue(new Error('500'));
    const { result } = renderData();
    act(() => result.current.track('j1', 'applied'));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Failed to update status',
        variant: 'destructive',
      })
    );
  });

  it('tracks the tailoring job and records the new resume', async () => {
    let finish: (value: unknown) => void = () => {};
    api.tailorApi.generate.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const { result } = renderData();
    await waitFor(() => expect(result.current.tailoredResumes).toEqual({ j0: 'r1' }));

    act(() => result.current.tailor('j1'));
    await waitFor(() => expect(result.current.tailoringJobId).toBe('j1'));

    api.resumesApi.list.mockResolvedValue({
      data: [
        { id: 'r1', type: 'tailored', job_id: 'j0' },
        { id: 'r2', type: 'tailored', job_id: 'j1' },
      ],
    });
    await act(async () =>
      finish({ data: { jobId: 'j1', resumeId: 'r2', matchKeywords: ['python', 'sql'] } })
    );

    await waitFor(() => expect(result.current.tailoringJobId).toBeNull());
    expect(result.current.tailoredResumes.j1).toBe('r2');
    expect(toast).toHaveBeenCalledWith({
      title: 'Tailored resume generated!',
      description: 'Matched 2 keywords. Click "Editor" to refine.',
    });
  });

  it('warns when the tailored PDF did not compile', async () => {
    api.tailorApi.generate.mockResolvedValue({
      data: { jobId: 'j1', resumeId: 'r2', compilationError: 'Undefined control sequence' },
    });
    const { result } = renderData();
    act(() => result.current.tailor('j1'));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Resume tailored but PDF compilation failed' })
      )
    );
  });

  it('clears the spinner and warns when tailoring fails', async () => {
    api.tailorApi.generate.mockRejectedValue(new Error('bedrock down'));
    const { result } = renderData();
    act(() => result.current.tailor('j1'));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Failed to generate tailored resume',
        variant: 'destructive',
      })
    );
    expect(result.current.tailoringJobId).toBeNull();
  });
});

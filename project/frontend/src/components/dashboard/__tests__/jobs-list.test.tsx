import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { makeJobDescription } from '@/test/job-descriptions';

const api = vi.hoisted(() => ({
  jobsApi: { list: vi.fn(), delete: vi.fn(), analyze: vi.fn(), create: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { JobsList } from '@/components/dashboard/jobs-list';

const JOBS = [
  makeJobDescription({ id: 'jd1', title: 'Backend Intern', is_analyzed: false }),
  makeJobDescription({ id: 'jd2', title: 'Data Intern', is_analyzed: true }),
];

beforeEach(() => {
  vi.clearAllMocks();
  api.jobsApi.list.mockResolvedValue({ data: JOBS });
});

describe('JobsList', () => {
  it('invites the user to add a job when there are none', async () => {
    api.jobsApi.list.mockResolvedValue({ data: [] });
    const { user } = renderWithQuery(<JobsList />);
    await user.click(await screen.findByRole('button', { name: /Add Job Description/ }));
    expect(screen.getByLabelText('Job Title *')).toBeInTheDocument();
  });

  it('analyzes a job and refetches the list', async () => {
    api.jobsApi.analyze.mockResolvedValue({});
    const { user } = renderWithQuery(<JobsList />);
    await user.click(await screen.findByRole('button', { name: /Analyze/ }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Job description analyzed' }));
    expect(api.jobsApi.analyze).toHaveBeenCalledWith('jd1');
    expect(api.jobsApi.list).toHaveBeenCalledTimes(2);
  });

  it('explains a failed analysis', async () => {
    api.jobsApi.analyze.mockRejectedValue({ response: { data: { detail: 'Bedrock throttled' } } });
    const { user } = renderWithQuery(<JobsList />);
    await user.click(await screen.findByRole('button', { name: /Analyze/ }));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Analysis failed', description: 'Bedrock throttled' })
      )
    );
  });

  it('deletes a job', async () => {
    api.jobsApi.delete.mockResolvedValue({});
    const { user } = renderWithQuery(<JobsList />);
    await screen.findByText('Data Intern');
    const card = screen.getByText('Data Intern').closest('.rounded-xl, [class*="border-l-4"]')!;
    const buttons = card.querySelectorAll('button');
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(api.jobsApi.delete).toHaveBeenCalledWith('jd2'));
    expect(toast).toHaveBeenCalledWith({ title: 'Job description deleted' });
  });

  it('opens the full description from a card', async () => {
    const { user } = renderWithQuery(<JobsList />);
    await user.click(await screen.findByText('Data Intern'));
    expect(screen.getByRole('heading', { name: 'Data Intern', level: 2 })).toBeInTheDocument();
  });
});

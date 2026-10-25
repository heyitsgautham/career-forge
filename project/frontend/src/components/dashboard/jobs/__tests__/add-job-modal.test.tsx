import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({ jobsApi: { create: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { AddJobModal } from '../add-job-modal';

beforeEach(() => vi.clearAllMocks());

describe('AddJobModal', () => {
  it('needs a title and a description before it submits', async () => {
    const { user } = renderWithQuery(<AddJobModal onClose={() => {}} />);
    const submit = screen.getByRole('button', { name: 'Add Job Description' });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText('Job Title *'), 'Backend Intern');
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText('Job Description *'), 'Build APIs');
    expect(submit).toBeEnabled();
  });

  it('creates the job, leaving out an empty URL, then closes', async () => {
    api.jobsApi.create.mockResolvedValue({ data: {} });
    const onClose = vi.fn();
    const { user } = renderWithQuery(<AddJobModal onClose={onClose} />);

    await user.type(screen.getByLabelText('Job Title *'), 'Backend Intern');
    await user.type(screen.getByLabelText('Company'), 'Sample Labs');
    await user.type(screen.getByLabelText('Job Description *'), 'Build APIs');
    await user.click(screen.getByRole('button', { name: 'Add Job Description' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(api.jobsApi.create).toHaveBeenCalledWith({
      title: 'Backend Intern',
      company: 'Sample Labs',
      raw_text: 'Build APIs',
      url: undefined,
    });
    expect(toast).toHaveBeenCalledWith({ title: 'Job description added' });
  });

  it('keeps the form open and explains a failure', async () => {
    api.jobsApi.create.mockRejectedValue({ response: { data: { detail: 'Title too long' } } });
    const onClose = vi.fn();
    const { user } = renderWithQuery(<AddJobModal onClose={onClose} />);

    await user.type(screen.getByLabelText('Job Title *'), 'T');
    await user.type(screen.getByLabelText('Job Description *'), 'D');
    await user.type(screen.getByLabelText('Job URL (optional)'), 'https://jobs.example.com/1');
    await user.click(screen.getByRole('button', { name: 'Add Job Description' }));

    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to add job description',
          description: 'Title too long',
        })
      )
    );
    expect(api.jobsApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ url: 'https://jobs.example.com/1' })
    );
    expect(onClose).not.toHaveBeenCalled();
  });
});

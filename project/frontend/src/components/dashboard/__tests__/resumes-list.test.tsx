import { screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { makeResume } from '@/test/resumes';

const api = vi.hoisted(() => ({
  resumesApi: {
    list: vi.fn(),
    delete: vi.fn(),
    generateFromSummaries: vi.fn(),
  },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { ResumesList } from '@/components/dashboard/resumes-list';

const RESUMES = [
  makeResume({ id: 'r1', name: 'Backend resume' }),
  makeResume({
    id: 'r2',
    name: 'Tailored for Sample Labs',
    status: 'generated',
    pdf_path: undefined,
  }),
];

beforeEach(() => {
  vi.clearAllMocks();
  api.resumesApi.list.mockResolvedValue({ data: RESUMES });
  api.resumesApi.delete.mockResolvedValue({});
});
afterEach(() => vi.restoreAllMocks());

describe('ResumesList', () => {
  it('counts resumes and lists each one', async () => {
    renderWithQuery(<ResumesList />);
    expect(await screen.findByText('2 resumes generated')).toBeInTheDocument();
    expect(screen.getByText('Tailored for Sample Labs')).toBeInTheDocument();
  });

  it('shows the empty state and opens the generator from it', async () => {
    api.resumesApi.list.mockResolvedValue({ data: [] });
    const { user } = renderWithQuery(<ResumesList />);
    await user.click(await screen.findByRole('button', { name: /Generate Your First Resume/ }));
    expect(screen.getByLabelText(/Job Description/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delete All/ })).not.toBeInTheDocument();
  });

  it('deletes every resume after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { user } = renderWithQuery(<ResumesList />);
    await user.click(await screen.findByRole('button', { name: /Delete All/ }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Deleted 2 resumes' }));
    expect(api.resumesApi.delete).toHaveBeenCalledWith('r1');
    expect(api.resumesApi.delete).toHaveBeenCalledWith('r2');
  });

  it('keeps everything when the user cancels delete-all', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { user } = renderWithQuery(<ResumesList />);
    await user.click(await screen.findByRole('button', { name: /Delete All/ }));
    expect(api.resumesApi.delete).not.toHaveBeenCalled();
  });

  it('warns when some deletes fail', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.resumesApi.delete.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error('500'));
    const { user } = renderWithQuery(<ResumesList />);
    await user.click(await screen.findByRole('button', { name: /Delete All/ }));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Some resumes could not be deleted',
        variant: 'destructive',
      })
    );
  });

  it('deletes a single resume', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { user } = renderWithQuery(<ResumesList />);
    await screen.findByText('Backend resume');
    const row = screen.getByText('Backend resume').closest('.group') as HTMLElement;
    const buttons = row.querySelectorAll('button');
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Resume deleted' }));
    expect(api.resumesApi.delete).toHaveBeenCalledWith('r1');
  });
});

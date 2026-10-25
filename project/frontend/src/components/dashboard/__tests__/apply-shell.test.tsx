import { screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { TOKEN_U1, makeApplication } from '@/test/applications';

const api = vi.hoisted(() => ({
  applicationsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  jobMatchApi: { list: vi.fn(), track: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { ApplyTrackShell } from '@/components/dashboard/apply-shell';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', TOKEN_U1);
  api.jobMatchApi.list.mockResolvedValue({ data: [] });
});
afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('ApplyTrackShell', () => {
  it('puts each application in its column', async () => {
    api.applicationsApi.list.mockResolvedValue({
      data: [
        makeApplication({ applicationId: 'a1', roleTitle: 'Backend Intern' }),
        makeApplication({ applicationId: 'a2', roleTitle: 'ML Intern', status: 'interviewing' }),
      ],
    });
    renderWithQuery(<ApplyTrackShell />);
    await screen.findByText('ML Intern');
    const interviewing = screen
      .getByText('Interviewing', { selector: 'span' })
      .closest('.flex-1') as HTMLElement;
    expect(within(interviewing).getByText('ML Intern')).toBeInTheDocument();
    expect(within(interviewing).queryByText('Backend Intern')).not.toBeInTheDocument();
  });

  it('shows the empty state and adds an application by hand', async () => {
    api.applicationsApi.list.mockResolvedValue({ data: [] });
    api.applicationsApi.create.mockResolvedValue({});
    const { user } = renderWithQuery(<ApplyTrackShell />);
    expect(await screen.findByText(/Your application tracker is empty/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Add application' }));
    await user.type(screen.getByPlaceholderText('e.g. Stripe'), 'Sample Labs');
    await user.type(screen.getByPlaceholderText('e.g. Backend SDE'), 'Backend Intern');
    await user.click(screen.getByRole('button', { name: /^Add Application$/ }));

    await vi.waitFor(() => expect(api.applicationsApi.create).toHaveBeenCalled());
    await vi.waitFor(() =>
      expect(screen.queryByPlaceholderText('e.g. Stripe')).not.toBeInTheDocument()
    );
  });

  it('opens an empty form after an application was added', async () => {
    // Regression: the form kept the last entry and asked to discard it on close.
    api.applicationsApi.list.mockResolvedValue({ data: [] });
    api.applicationsApi.create.mockResolvedValue({});
    const confirm = vi.spyOn(window, 'confirm');
    const { user } = renderWithQuery(<ApplyTrackShell />);
    await screen.findByText(/Your application tracker is empty/);

    await user.click(screen.getByRole('button', { name: 'Add application' }));
    await user.type(screen.getByPlaceholderText('e.g. Stripe'), 'Sample Labs');
    await user.type(screen.getByPlaceholderText('e.g. Backend SDE'), 'Backend Intern');
    await user.click(screen.getByRole('button', { name: /^Add Application$/ }));
    await vi.waitFor(() =>
      expect(screen.queryByPlaceholderText('e.g. Stripe')).not.toBeInTheDocument()
    );

    await user.click(screen.getByRole('button', { name: 'Add application' }));
    expect(screen.getByPlaceholderText('e.g. Stripe')).toHaveValue('');
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(confirm).not.toHaveBeenCalled();
  });

  it('tells the user when removing an application fails', async () => {
    api.applicationsApi.list.mockResolvedValue({ data: [makeApplication()] });
    api.applicationsApi.delete.mockRejectedValue({ response: { data: { detail: 'Not found' } } });
    const { user } = renderWithQuery(<ApplyTrackShell />);
    await user.click(await screen.findByRole('button', { name: 'Delete application' }));
    await vi.waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Failed to remove application',
        description: 'Not found',
        variant: 'destructive',
      })
    );
  });
});

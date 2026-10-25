import { screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { TOKEN_U1, makeApplication } from '@/test/applications';

const api = vi.hoisted(() => ({
  applicationsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  jobMatchApi: { list: vi.fn(), track: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

import { ApplyTrackShell } from '@/components/dashboard/apply-shell';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', TOKEN_U1);
  api.jobMatchApi.list.mockResolvedValue({ data: [] });
});
afterEach(() => localStorage.clear());

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
});

import { screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
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
  authApi: { linkedinImport: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

import { JobScoutShell } from '@/components/dashboard/job-scout-shell';

const JOBS = [
  makeJob({ jobId: 'j1', title: 'Backend Intern', company: 'Sample Labs' }),
  makeJob({ jobId: 'j2', title: 'ML Intern', company: 'Demo Corp', category: 'AI/ML' }),
  ...Array.from({ length: 30 }, (_, i) =>
    makeJob({
      jobId: `x${i}`,
      title: `Support Engineer ${i}`,
      company: 'Filler Co',
      category: 'Ops',
    })
  ),
];

beforeEach(() => {
  vi.clearAllMocks();
  api.jobMatchApi.list.mockResolvedValue({ data: JOBS });
  api.jobMatchApi.stats.mockResolvedValue({
    data: { totalJobs: 32, analyzedJobs: 30, newToday: 4 },
  });
  api.jobMatchApi.schedulerStatus.mockResolvedValue({
    data: { nextRunTime: null, lastScrape: { status: 'success', message: 'Found 32 jobs' } },
  });
  api.jobMatchApi.getTracking.mockResolvedValue({ data: {} });
  api.resumesApi.list.mockResolvedValue({ data: [] });
});
afterEach(() => localStorage.clear());

describe('JobScoutShell', () => {
  it('shows the stats, the scrape banner and the first page of jobs', async () => {
    renderWithQuery(<JobScoutShell />);

    expect(await screen.findByRole('button', { name: 'Backend Intern' })).toBeInTheDocument();
    expect(screen.getByText('32')).toBeInTheDocument();
    expect(screen.getByText('30 analyzed')).toBeInTheDocument();
    expect(screen.getByText('Found 32 jobs')).toBeInTheDocument();
    expect(screen.getByText('32 jobs · Page 1 of 2')).toBeInTheDocument();
  });

  it('filters by category, remembers it, and returns to page one', async () => {
    const { user } = renderWithQuery(<JobScoutShell />);
    await screen.findByRole('button', { name: 'Backend Intern' });

    await user.click(screen.getByLabelText('Next page'));
    expect(screen.getByText('32 jobs · Page 2 of 2')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'AI/ML' }));

    expect(screen.getByRole('button', { name: 'ML Intern' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Backend Intern' })).not.toBeInTheDocument();
    expect(screen.queryByText(/Page \d of/)).not.toBeInTheDocument();
    expect(localStorage.getItem('jobScout_category')).toBe('AI/ML');
  });

  it('restores the remembered category on mount', async () => {
    localStorage.setItem('jobScout_category', 'AI/ML');
    renderWithQuery(<JobScoutShell />);
    expect(await screen.findByRole('button', { name: 'ML Intern' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Backend Intern' })).not.toBeInTheDocument();
  });

  it('searches by company and reports when nothing matches', async () => {
    const { user } = renderWithQuery(<JobScoutShell />);
    await screen.findByRole('button', { name: 'Backend Intern' });

    await user.type(screen.getByPlaceholderText('Search jobs…'), 'demo');
    expect(screen.getAllByRole('row')).toHaveLength(2);

    await user.type(screen.getByPlaceholderText('Search jobs…'), 'zzz');
    expect(screen.getByText('No jobs match the current filters.')).toBeInTheDocument();
  });

  it('opens the job detail modal from a title', async () => {
    const { user } = renderWithQuery(<JobScoutShell />);
    await user.click(await screen.findByRole('button', { name: 'ML Intern' }));
    const dialogHeading = screen.getAllByText('ML Intern').find((el) => el.tagName === 'H2');
    expect(dialogHeading).toBeDefined();
    expect(
      within(dialogHeading!.closest('div')!.parentElement!).getByText('Demo Corp')
    ).toBeVisible();
  });
});

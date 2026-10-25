import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { makeJob } from '@/test/fixtures';

const api = vi.hoisted(() => ({ userApi: { importLinkedInProfile: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { JobDetailModal } from '../job-detail-modal';
import { LinkedInImportModal } from '../linkedin-import-modal';
import { RichDescription } from '../rich-description';
import { StatCard } from '../stat-card';
import { useCountdown } from '../use-countdown';
import { Briefcase } from 'lucide-react';

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.useRealTimers());

describe('RichDescription', () => {
  it('turns markdown-ish text into headings, bullets and bold runs', () => {
    const { container } = render(
      <RichDescription
        text={[
          '**About the role**',
          'Build **REST** APIs in Python.',
          '',
          '* Write tests',
          '- Ship C\\+\\+ tools',
          'Remote friendly',
        ].join('\n')}
      />
    );
    expect(screen.getByText('About the role').tagName).toBe('P');
    expect(screen.getByText('REST').tagName).toBe('STRONG');
    expect(container.querySelectorAll('li')).toHaveLength(2);
    expect(screen.getByText('Ship C++ tools')).toBeInTheDocument();
    expect(screen.getByText('Remote friendly')).toBeInTheDocument();
  });
});

describe('StatCard', () => {
  it('shows its title, value and subtitle', () => {
    render(<StatCard title="Total Jobs" value={32} subtitle="30 analyzed" icon={Briefcase} />);
    expect(screen.getByText('Total Jobs')).toBeInTheDocument();
    expect(screen.getByText('32')).toBeInTheDocument();
    expect(screen.getByText('30 analyzed')).toBeInTheDocument();
  });
});

describe('useCountdown', () => {
  it('counts down to the target and then says it is scraping', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-10T09:00:00Z'));
    const { result } = renderHook(() => useCountdown('2026-03-10T09:01:05Z'));
    expect(result.current).toBe('1m 05s');
    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current).toBe('0m 05s');
    act(() => vi.advanceTimersByTime(6_000));
    expect(result.current).toBe('Scraping now…');
  });

  it('shows a dash without a target', () => {
    const { result } = renderHook(() => useCountdown(null));
    expect(result.current).toBe('—');
  });
});

describe('JobDetailModal', () => {
  const job = makeJob({
    salary: '₹20,000 / month',
    jobType: 'Internship',
    description: 'Build **APIs**',
    missingSkills: ['Go'],
    preferredSkills: ['Docker'],
    atsKeywords: ['REST'],
  });

  it('shows the job and wires tracking, tailoring and close', async () => {
    const handlers = { onClose: vi.fn(), onTrack: vi.fn(), onTailor: vi.fn() };
    render(<JobDetailModal job={job} trackingStatus="pending" {...handlers} />);

    expect(screen.getByRole('heading', { name: 'Backend Intern' })).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByText('Go')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /View Posting/ })).toHaveAttribute('href', job.url);

    await userEvent.selectOptions(screen.getByRole('combobox'), 'applied');
    await userEvent.click(screen.getByRole('button', { name: /Tailor Resume/ }));
    await userEvent.click(document.querySelector('.fixed.inset-0') as Element);

    expect(handlers.onTrack).toHaveBeenCalledWith('applied');
    expect(handlers.onTailor).toHaveBeenCalledOnce();
    expect(handlers.onClose).toHaveBeenCalledOnce();
  });

  it('leaves out the score and link when the job has none', () => {
    render(
      <JobDetailModal
        job={makeJob({ matchScore: null, url: null })}
        trackingStatus="pending"
        onClose={() => {}}
        onTrack={() => {}}
        onTailor={() => {}}
      />
    );
    expect(screen.queryByText('Match Score')).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});

describe('LinkedInImportModal', () => {
  it('imports the profile and lists what came in', async () => {
    api.userApi.importLinkedInProfile.mockResolvedValue({
      data: {
        imported: {
          name: 'Asha Example',
          headline: 'Backend developer',
          summary: true,
          education_added: 1,
          certifications_added: 2,
        },
      },
    });
    const onClose = vi.fn();
    const { user } = renderWithQuery(<LinkedInImportModal onClose={onClose} />);

    await user.type(
      screen.getByPlaceholderText('https://www.linkedin.com/in/your-username'),
      'https://www.linkedin.com/in/asha-example'
    );
    await user.click(screen.getByRole('button', { name: 'Import' }));

    expect(await screen.findByText('Import complete!')).toBeInTheDocument();
    expect(api.userApi.importLinkedInProfile).toHaveBeenCalledWith(
      'https://www.linkedin.com/in/asha-example'
    );
    expect(toast).toHaveBeenCalledWith({
      title: 'LinkedIn profile imported!',
      description:
        'Name: Asha Example · Headline · Summary · 1 education entries · 2 certifications',
    });
    await user.click(screen.getByRole('button', { name: 'Done' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('needs a URL and explains a failed import', async () => {
    api.userApi.importLinkedInProfile.mockRejectedValue({
      response: { data: { detail: 'LinkedIn blocked the scraper' } },
    });
    const { user } = renderWithQuery(<LinkedInImportModal onClose={() => {}} />);
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled();
    await user.type(screen.getByRole('textbox'), 'https://www.linkedin.com/in/x');
    await user.click(screen.getByRole('button', { name: 'Import' }));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'LinkedIn blocked the scraper' })
      )
    );
  });
});

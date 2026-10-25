import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScrapeStatusBanner } from '../scrape-status-banner';

const scrape = (status: string | null, message = 'Found 3 jobs') => ({
  timestamp: '2026-03-10T09:00:00Z',
  total_jobs: 3,
  new_jobs: 1,
  status,
  message,
});

describe('ScrapeStatusBanner', () => {
  it('reports a successful scrape with its message', () => {
    render(<ScrapeStatusBanner lastScrape={scrape('success')} />);
    expect(screen.getByText('Last Scrape Completed')).toBeInTheDocument();
    expect(screen.getByText('Found 3 jobs')).toBeInTheDocument();
  });

  it('reports any other status as a failure', () => {
    render(<ScrapeStatusBanner lastScrape={scrape('error', 'Naukri timed out')} />);
    expect(screen.getByText('Last Scrape Failed')).toBeInTheDocument();
    expect(screen.getByText('Naukri timed out')).toBeInTheDocument();
  });

  it.each([undefined, null, scrape(null)])('renders nothing without a status (%#)', (value) => {
    const { container } = render(<ScrapeStatusBanner lastScrape={value} />);
    expect(container).toBeEmptyDOMElement();
  });
});

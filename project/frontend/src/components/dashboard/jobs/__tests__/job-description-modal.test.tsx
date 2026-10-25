import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobDescriptionModal } from '../job-description-modal';
import { makeJobDescription } from '@/test/job-descriptions';

describe('JobDescriptionModal', () => {
  it('shows the full text, every skill list and the source link', async () => {
    const onClose = vi.fn();
    render(
      <JobDescriptionModal
        job={makeJobDescription({ source_url: 'https://jobs.example.com/1' })}
        onClose={onClose}
      />
    );
    expect(screen.getByText('Build REST APIs in Python and write tests for them.')).toBeVisible();
    expect(screen.getByText('FastAPI')).toBeInTheDocument();
    expect(screen.getByText('Docker')).toBeInTheDocument();
    expect(screen.getByText('REST')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', 'https://jobs.example.com/1');

    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('leaves out empty sections', () => {
    render(
      <JobDescriptionModal
        job={makeJobDescription({ required_skills: [], preferred_skills: [], keywords: [] })}
        onClose={() => {}}
      />
    );
    expect(screen.queryByText('Required Skills')).not.toBeInTheDocument();
    expect(screen.queryByText('Preferred Skills')).not.toBeInTheDocument();
    expect(screen.queryByText('Keywords')).not.toBeInTheDocument();
    expect(screen.queryByText('Source URL')).not.toBeInTheDocument();
  });
});

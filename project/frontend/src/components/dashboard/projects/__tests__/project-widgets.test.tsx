import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ClearAllDialog } from '../clear-all-dialog';
import { ImportGithubButton } from '../import-github-button';
import { ProjectCard } from '../project-card';
import { ProjectDetailsModal } from '../project-details-modal';
import { SyncBanner } from '../sync-banner';
import type { Project } from '../types';

const PROJECT: Project = {
  id: 'p1',
  title: 'job-scout',
  description: 'Ranks internship postings',
  technologies: ['Python', 'FastAPI', 'AWS', 'Docker', 'Redis', 'Celery', 'Postgres'],
  highlights: ['Scores 500 postings a day'],
  url: 'https://github.com/asha-example/job-scout',
  source_type: 'github',
  is_private: true,
  start_date: '2025-01',
  created_at: '2025-01-01',
};

describe('ClearAllDialog', () => {
  it('states how many projects go and wires both buttons', async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(<ClearAllDialog count={4} onCancel={onCancel} onConfirm={onConfirm} />);

    expect(screen.getByText(/permanently delete all 4 projects/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await userEvent.click(screen.getByRole('button', { name: 'Yes, Clear All' }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

describe('ImportGithubButton', () => {
  it('shows the repository count only when there are repositories', () => {
    const { rerender } = render(
      <ImportGithubButton repoCount={7} className="" onClick={() => {}} />
    );
    expect(screen.getByRole('button')).toHaveTextContent('Import from GitHub7');

    rerender(<ImportGithubButton repoCount={0} className="" onClick={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/^Import from GitHub$/);

    rerender(<ImportGithubButton repoCount={undefined} className="" onClick={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/^Import from GitHub$/);
  });
});

describe('ProjectCard', () => {
  it('shows five technologies and counts the rest', () => {
    render(<ProjectCard project={PROJECT} onShowDetails={() => {}} onDelete={() => {}} />);
    expect(screen.getByText('Redis')).toBeInTheDocument();
    expect(screen.queryByText('Celery')).not.toBeInTheDocument();
    expect(screen.getByText('+2')).toBeInTheDocument();
    expect(screen.getByText('2025-01 - Present')).toBeInTheDocument();
    expect(screen.getByTitle('Private repository')).toBeInTheDocument();
  });

  it('marks public GitHub repositories and leaves manual projects unmarked', () => {
    const { rerender } = render(
      <ProjectCard
        project={{ ...PROJECT, is_private: false }}
        onShowDetails={() => {}}
        onDelete={() => {}}
      />
    );
    expect(screen.getByTitle('Public repository')).toBeInTheDocument();

    rerender(
      <ProjectCard
        project={{ ...PROJECT, source_type: 'manual', url: undefined }}
        onShowDetails={() => {}}
        onDelete={() => {}}
      />
    );
    expect(screen.queryByTitle(/repository/)).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('opens details and deletes from its buttons', async () => {
    const onShowDetails = vi.fn();
    const onDelete = vi.fn();
    render(<ProjectCard project={PROJECT} onShowDetails={onShowDetails} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole('button', { name: 'Show Details' }));
    await userEvent.click(screen.getAllByRole('button').at(-1)!);
    expect(onShowDetails).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledOnce();
  });
});

describe('ProjectDetailsModal', () => {
  it('lists every technology, highlight, the link and the timeline', async () => {
    const onClose = vi.fn();
    render(<ProjectDetailsModal project={{ ...PROJECT, end_date: '2025-06' }} onClose={onClose} />);
    expect(screen.getByText('Celery')).toBeInTheDocument();
    expect(screen.getByText('Scores 500 postings a day')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', PROJECT.url);
    expect(screen.getByText('2025-01 - 2025-06')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('skips empty sections', () => {
    render(
      <ProjectDetailsModal
        project={{ ...PROJECT, technologies: [], highlights: [], url: undefined, start_date: '' }}
        onClose={() => {}}
      />
    );
    expect(screen.queryByText('Technologies')).not.toBeInTheDocument();
    expect(screen.queryByText('Key Highlights')).not.toBeInTheDocument();
    expect(screen.queryByText('Project URL')).not.toBeInTheDocument();
    expect(screen.queryByText('Timeline')).not.toBeInTheDocument();
  });
});

describe('SyncBanner', () => {
  const props = {
    syncing: false,
    syncStatus: 'none',
    syncSummary: null,
    onSyncAll: vi.fn(),
    showClearAll: true,
    clearing: false,
    onClearAll: vi.fn(),
  };

  it('starts a sync and asks to clear all', async () => {
    render(<SyncBanner {...props} />);
    await userEvent.click(screen.getByRole('button', { name: /Sync Existing/ }));
    await userEvent.click(screen.getByRole('button', { name: /Clear All/ }));
    expect(props.onSyncAll).toHaveBeenCalledOnce();
    expect(props.onClearAll).toHaveBeenCalledOnce();
  });

  it('disables the sync button while syncing and explains the wait', () => {
    render(<SyncBanner {...props} syncing syncStatus="in_progress" />);
    expect(screen.getByRole('button', { name: /Syncing/ })).toBeDisabled();
    expect(screen.getByText('Importing…')).toBeInTheDocument();
    expect(screen.getByText(/takes ~1–2 min/)).toBeInTheDocument();
  });

  it('shows the pending and failed badges', () => {
    const { rerender } = render(<SyncBanner {...props} syncStatus="pending" />);
    expect(screen.getByText('Pending…')).toBeInTheDocument();
    rerender(<SyncBanner {...props} syncStatus="failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('summarises a finished sync with its failures', () => {
    render(
      <SyncBanner
        {...props}
        syncStatus="done"
        syncSummary={{ processed: 5, failed: 2, lastRunAt: '2026-03-10T09:00:00Z' }}
      />
    );
    expect(screen.getByText('5 imported')).toBeInTheDocument();
    expect(screen.getByText(/Last synced .* · 2 failed/)).toBeInTheDocument();
  });

  it('hides clear-all when there is nothing to clear and labels it while clearing', () => {
    const { rerender } = render(<SyncBanner {...props} showClearAll={false} />);
    expect(screen.queryByRole('button', { name: /Clear All/ })).not.toBeInTheDocument();
    rerender(<SyncBanner {...props} clearing />);
    expect(screen.getByRole('button', { name: /Clearing/ })).toBeDisabled();
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({ projectsApi: { create: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { AddProjectModal } from '../add-project-modal';
import { ImportProgressBanner, ImportSkeletonCard } from '../import-progress';

beforeEach(() => vi.clearAllMocks());

describe('AddProjectModal', () => {
  it('splits technologies on commas and highlights on lines', async () => {
    api.projectsApi.create.mockResolvedValue({});
    const onClose = vi.fn();
    const { user } = renderWithQuery(<AddProjectModal onClose={onClose} />);

    await user.type(screen.getByLabelText('Project Title *'), 'job-scout');
    await user.type(screen.getByLabelText('Description *'), 'Ranks postings');
    await user.type(screen.getByLabelText('Technologies (comma-separated)'), 'Python, , FastAPI');
    await user.type(
      screen.getByPlaceholderText(/auto-generate/),
      'Scores 500 a day{Enter}{Enter}Has tests'
    );
    await user.click(screen.getByRole('button', { name: /Add Project|Create/ }));

    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(api.projectsApi.create).toHaveBeenCalledWith({
      title: 'job-scout',
      description: 'Ranks postings',
      technologies: ['Python', 'FastAPI'],
      highlights: ['Scores 500 a day', 'Has tests'],
      url: undefined,
    });
  });

  it('explains a failed create', async () => {
    api.projectsApi.create.mockRejectedValue({ response: { data: { detail: 'Duplicate title' } } });
    const { user } = renderWithQuery(<AddProjectModal onClose={() => {}} />);
    await user.type(screen.getByLabelText('Project Title *'), 'x');
    await user.type(screen.getByLabelText('Description *'), 'y');
    await user.click(screen.getByRole('button', { name: /Add Project|Create/ }));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Duplicate title' })
      )
    );
  });
});

describe('ImportProgressBanner', () => {
  it('counts processing and queued repositories while importing', () => {
    render(
      <ImportProgressBanner
        importProgress={[
          { name: 'a', fullName: 'x/a', status: 'done' },
          { name: 'b', fullName: 'x/b', status: 'processing' },
          { name: 'c', fullName: 'x/c', status: 'queued' },
        ]}
      />
    );
    expect(screen.getByText('Importing 3 repositories…')).toBeInTheDocument();
    expect(screen.getByText('Analyzing b…')).toBeInTheDocument();
  });

  it('summarises a finished import with its failures', () => {
    render(
      <ImportProgressBanner
        importProgress={[
          { name: 'a', fullName: 'x/a', status: 'done' },
          { name: 'b', fullName: 'x/b', status: 'failed' },
        ]}
      />
    );
    expect(screen.getByText('Import completed with 1 failure')).toBeInTheDocument();
    expect(screen.getByText('1 succeeded, 1 failed')).toBeInTheDocument();
  });

  it('celebrates a clean import', () => {
    render(
      <ImportProgressBanner importProgress={[{ name: 'a', fullName: 'x/a', status: 'done' }]} />
    );
    expect(screen.getByText('Successfully imported 1 project')).toBeInTheDocument();
  });
});

describe('ImportSkeletonCard', () => {
  it.each(['queued', 'processing', 'done', 'failed'] as const)('renders the %s state', (status) => {
    render(<ImportSkeletonCard item={{ name: 'job-scout', fullName: 'x/job-scout', status }} />);
    expect(screen.getByText('job-scout')).toBeInTheDocument();
  });
});

import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({ projectsApi: { listGithubUserRepos: vi.fn() } }));
vi.mock('@/lib/api', () => api);

import { GithubImportModal } from '../github-import-modal';

const REPOS = [
  {
    full_name: 'asha/job-scout',
    name: 'job-scout',
    html_url: '',
    stars: 4,
    forks: 0,
    language: 'Python',
    is_private: false,
    is_fork: false,
  },
  {
    full_name: 'asha/notes',
    name: 'notes',
    html_url: '',
    stars: 0,
    forks: 0,
    is_private: true,
    is_fork: false,
  },
  {
    full_name: 'asha/old',
    name: 'old',
    html_url: '',
    stars: 0,
    forks: 0,
    is_private: false,
    is_fork: false,
  },
];

function renderModal(imported: string[] = ['old']) {
  const props = { onClose: vi.fn(), onStartImport: vi.fn() };
  const view = renderWithQuery(
    <GithubImportModal {...props} importedRepoNames={new Set(imported)} />
  );
  return { ...view, ...props };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.projectsApi.listGithubUserRepos.mockResolvedValue({ data: REPOS });
});

describe('GithubImportModal', () => {
  it('imports the selected repositories', async () => {
    const { user, onStartImport } = renderModal();
    await user.click(await screen.findByText('asha/job-scout'));
    await user.click(screen.getByText('asha/notes'));
    await user.click(screen.getByRole('button', { name: 'Import 2 Repositories' }));
    expect(onStartImport).toHaveBeenCalledWith(['asha/job-scout', 'asha/notes']);
  });

  it('selects every repository not imported yet, then clears them', async () => {
    const { user } = renderModal();
    await screen.findByText('asha/job-scout');
    await user.click(screen.getByRole('button', { name: 'Select All' }));
    expect(screen.getByRole('button', { name: 'Import 2 Repositories' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Deselect All' }));
    expect(screen.getByRole('button', { name: 'Import Repository' })).toBeDisabled();
  });

  it('filters to private repositories', async () => {
    const { user } = renderModal();
    await screen.findByText('asha/job-scout');
    await user.click(screen.getByRole('button', { name: /Private/ }));
    expect(screen.queryByText('asha/job-scout')).not.toBeInTheDocument();
    expect(screen.getByText('asha/notes')).toBeInTheDocument();
  });

  it('imports a single repository by URL', async () => {
    const { user, onStartImport } = renderModal();
    await user.click(screen.getByRole('button', { name: /Import by URL/ }));
    await user.type(
      screen.getByLabelText('GitHub Repository URL'),
      'https://github.com/asha/job-scout.git'
    );
    await user.click(screen.getByRole('button', { name: 'Import Repository' }));
    expect(onStartImport).toHaveBeenCalledWith(['asha/job-scout']);
  });

  it('keeps Import disabled until the URL names a repository', async () => {
    const { user } = renderModal();
    await user.click(screen.getByRole('button', { name: /Import by URL/ }));
    await user.type(screen.getByLabelText('GitHub Repository URL'), 'https://github.com/asha');
    expect(screen.getByRole('button', { name: 'Import Repository' })).toBeDisabled();
    await user.type(screen.getByLabelText('GitHub Repository URL'), '/job-scout');
    expect(screen.getByRole('button', { name: 'Import Repository' })).toBeEnabled();
  });

  it('explains when GitHub is not connected and offers the URL route', async () => {
    api.projectsApi.listGithubUserRepos.mockRejectedValue({
      response: { data: { detail: 'GitHub token expired' } },
    });
    const { user } = renderModal();
    expect(await screen.findByText('GitHub token expired')).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: /URL/ }).at(-1)!);
    expect(screen.getByLabelText('GitHub Repository URL')).toBeInTheDocument();
  });

  it('closes from Cancel', async () => {
    const { user, onClose } = renderModal();
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

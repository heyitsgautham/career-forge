import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  projectsApi: {
    list: vi.fn(),
    listGithubUserRepos: vi.fn(),
    delete: vi.fn(),
    deleteAll: vi.fn(),
    importGithub: vi.fn(),
    create: vi.fn(),
  },
  githubApi: { getIngestStatus: vi.fn(), sync: vi.fn() },
}));
vi.mock('@/lib/api', () => api);

const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { ProjectsList } from '@/components/dashboard/projects-list';

// Synthetic projects only.
const PROJECTS = [
  {
    id: 'p1',
    title: 'job-scout',
    description: 'Ranks internship postings by skill match',
    technologies: ['Python', 'FastAPI', 'AWS', 'Docker', 'Redis', 'Celery', 'Postgres'],
    highlights: ['Scores 500 postings a day'],
    url: 'https://github.com/asha-example/job-scout',
    source_type: 'github',
    is_private: true,
    start_date: '2025-01',
    created_at: '2025-01-01',
  },
  {
    id: 'p2',
    title: 'notes-app',
    description: 'Offline-first markdown notes',
    technologies: ['React'],
    highlights: [],
    source_type: 'manual',
    created_at: '2025-02-01',
  },
];

function renderList(): { user: ReturnType<typeof userEvent.setup> } {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  render(<ProjectsList />, { wrapper });
  return { user: userEvent.setup() };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.projectsApi.list.mockResolvedValue({ data: PROJECTS });
  api.projectsApi.listGithubUserRepos.mockResolvedValue({ data: [{}, {}, {}] });
  api.projectsApi.delete.mockResolvedValue({ data: {} });
  api.projectsApi.deleteAll.mockResolvedValue({ data: { message: 'Deleted 2 projects' } });
});

describe('ProjectsList', () => {
  it('shows the empty state when there are no projects', async () => {
    api.projectsApi.list.mockResolvedValue({ data: [] });
    renderList();
    expect(await screen.findByText('No projects yet')).toBeInTheDocument();
  });

  it('renders a card per project with at most five technology badges', async () => {
    renderList();
    expect(await screen.findByText('job-scout')).toBeInTheDocument();
    expect(screen.getByText('notes-app')).toBeInTheDocument();
    expect(screen.getByText('Docker')).toBeInTheDocument();
    expect(screen.queryByText('Celery')).not.toBeInTheDocument();
    expect(screen.getByText('+2')).toBeInTheDocument();
    expect(screen.getByTitle('Private repository')).toBeInTheDocument();
    expect(screen.getByText(/2025-01 - Present/)).toBeInTheDocument();
  });

  it('shows the GitHub repo count on the import button', async () => {
    renderList();
    const button = await screen.findByRole('button', { name: /Import from GitHub/ });
    await waitFor(() => expect(within(button).getByText('3')).toBeInTheDocument());
  });

  it('opens the details modal for a project', async () => {
    const { user } = renderList();
    await screen.findByText('job-scout');
    await user.click(screen.getAllByRole('button', { name: 'Show Details' })[0]);
    expect(screen.getByRole('heading', { level: 2, name: 'job-scout' })).toBeInTheDocument();
    expect(screen.getByText('Scores 500 postings a day')).toBeInTheDocument();
  });

  it('removes a project from the grid as soon as delete is clicked', async () => {
    let resolveDelete: (value: unknown) => void = () => {};
    api.projectsApi.delete.mockReturnValue(new Promise((resolve) => (resolveDelete = resolve)));
    const { user } = renderList();
    const card = (await screen.findByText('notes-app')).closest('.border-l-4') as HTMLElement;
    const buttons = within(card).getAllByRole('button');
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(screen.queryByText('notes-app')).not.toBeInTheDocument());
    expect(api.projectsApi.delete).toHaveBeenCalledWith('p2');
    resolveDelete({ data: {} });
  });

  it('restores the project and shows an error when delete fails', async () => {
    api.projectsApi.delete.mockRejectedValue(new Error('boom'));
    const { user } = renderList();
    const card = (await screen.findByText('notes-app')).closest('.border-l-4') as HTMLElement;
    const buttons = within(card).getAllByRole('button');
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Failed to delete project',
        variant: 'destructive',
      })
    );
    expect(await screen.findByText('notes-app')).toBeInTheDocument();
  });
});

import { act, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const nav = vi.hoisted(() => ({
  params: new URLSearchParams(),
  router: { push: vi.fn(), replace: vi.fn() },
}));
vi.mock('next/navigation', () => ({
  useRouter: () => nav.router,
  useSearchParams: () => nav.params,
}));

const api = vi.hoisted(() => ({
  userApi: {
    getProfile: vi.fn(),
    getGithubStatus: vi.fn(),
  },
  authApi: { githubInstall: vi.fn() },
  projectsApi: { list: vi.fn() },
  resumesApi: { list: vi.fn() },
  jobMatchApi: { list: vi.fn() },
  skillGapApi: { getRoles: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

// Each tab has its own tests; here they only need to show which one is mounted.
const stub = vi.hoisted(() => (name: string) => {
  const Stub = () => <div data-testid="tab">{name}</div>;
  Stub.displayName = `Stub(${name})`;
  return Stub;
});
vi.mock('@/components/dashboard/projects-list', () => ({ ProjectsList: stub('projects') }));
vi.mock('@/components/dashboard/jobs-list', () => ({ JobsList: stub('jobs') }));
vi.mock('@/components/dashboard/resumes-list', () => ({ ResumesList: stub('resumes') }));
vi.mock('@/components/dashboard/templates-list', () => ({ TemplatesList: stub('templates') }));
vi.mock('@/components/dashboard/profile-view', () => ({ ProfileView: stub('profile') }));
vi.mock('@/components/dashboard/skill-gap-shell', () => ({ SkillGapShell: stub('skill-gap') }));
vi.mock('@/components/dashboard/job-scout-shell', () => ({ JobScoutShell: stub('job-scout') }));
vi.mock('@/components/dashboard/apply-shell', () => ({ ApplyTrackShell: stub('apply') }));
vi.mock('@/components/dashboard/project-roadmap-shell', () => ({
  ProjectRoadmapShell: stub('roadmap'),
}));
vi.mock('@/components/dashboard/settings-modal', () => ({
  SettingsModal: ({ onLogout }: { onLogout: () => void }) => (
    <button onClick={onLogout}>settings-logout</button>
  ),
}));

const cache = vi.hoisted(() => ({ clearCachedData: vi.fn() }));
vi.mock('@/lib/query-cache', () => cache);

import DashboardPage from '@/app/dashboard/page';

const visibleTab = () =>
  screen.getAllByTestId('tab').find((el) => !el.closest('.hidden'))?.textContent;

beforeEach(() => {
  vi.clearAllMocks();
  nav.params = new URLSearchParams();
  localStorage.setItem('token', 'jwt');
  window.history.replaceState(null, '', '/dashboard');
  api.userApi.getProfile.mockResolvedValue({
    data: { name: 'Asha Example', email: 'asha@example.com' },
  });
  api.userApi.getGithubStatus.mockResolvedValue({
    data: { connected: true, username: 'asha-example' },
  });
  for (const fn of [api.projectsApi.list, api.resumesApi.list, api.jobMatchApi.list]) {
    fn.mockResolvedValue({ data: [] });
  }
  api.skillGapApi.getRoles.mockResolvedValue({ data: { roles: [] } });
});
afterEach(() => localStorage.clear());

describe('DashboardPage', () => {
  it('opens on the resumes tab and shows the signed-in user', async () => {
    renderWithQuery(<DashboardPage />);
    expect(await screen.findByText('Asha Example')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Resumes');
    expect(visibleTab()).toBe('resumes');
    expect(await screen.findByText('@asha-example')).toBeInTheDocument();
  });

  it('restores a hidden tab from the URL', async () => {
    nav.params = new URLSearchParams('tab=templates');
    renderWithQuery(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Templates')
    );
    expect(visibleTab()).toBe('templates');
  });

  it('switches tabs from the sidebar and records the tab in the URL', async () => {
    const { user } = renderWithQuery(<DashboardPage />);
    await user.click(screen.getByRole('button', { name: 'Skill Gap' }));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Skill Gap');
    expect(window.location.search).toBe('?tab=skill-gap');
    expect(screen.getByRole('button', { name: 'Skill Gap' })).toHaveAttribute(
      'aria-current',
      'page'
    );
  });

  it('keeps the projects tab mounted while hidden', async () => {
    const { user } = renderWithQuery(<DashboardPage />);
    await user.click(screen.getByRole('button', { name: 'Projects' }));
    await user.click(screen.getByRole('button', { name: 'Roadmap' }));
    expect(screen.getByText('projects').closest('.hidden')).not.toBeNull();
  });

  it('keeps the header at full height on long tabs', () => {
    // Regression: as a flex item the sticky header shrank to 45px once the tab content overflowed.
    renderWithQuery(<DashboardPage />);
    expect(screen.getByRole('banner')).toHaveClass('h-14', 'shrink-0');
  });

  it('logs out from the sidebar', async () => {
    const { user } = renderWithQuery(<DashboardPage />);
    await user.click(screen.getByRole('button', { name: 'Logout' }));
    expect(localStorage.getItem('token')).toBeNull();
    expect(nav.router.push).toHaveBeenCalledWith('/login');
    expect(cache.clearCachedData).toHaveBeenCalledOnce();
  });

  it('sends a visitor without a token to the login page', () => {
    localStorage.clear();
    renderWithQuery(<DashboardPage />);
    expect(nav.router.push).toHaveBeenCalledWith('/login');
  });

  it('stores the token from a GitHub OAuth callback', async () => {
    nav.params = new URLSearchParams('github=connected&token=fresh-jwt');
    renderWithQuery(<DashboardPage />);
    await waitFor(() => expect(localStorage.getItem('token')).toBe('fresh-jwt'));
    expect(cache.clearCachedData).toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'GitHub connected!' }));
    expect(nav.router.replace).toHaveBeenCalledWith('/dashboard');
  });

  it('reports an OAuth error from the callback', async () => {
    nav.params = new URLSearchParams('error=access_denied');
    renderWithQuery(<DashboardPage />);
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Connection failed', description: 'Error: access denied' })
      )
    );
  });

  it('offers to connect GitHub when it is not linked, and collapses the sidebar', async () => {
    api.userApi.getGithubStatus.mockResolvedValue({ data: { connected: false } });
    const { user } = renderWithQuery(<DashboardPage />);
    await user.click(await screen.findByRole('button', { name: /Connect GitHub/ }));
    expect(api.authApi.githubInstall).toHaveBeenCalledOnce();

    await user.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument();
  });

  it('opens settings, whose logout also signs out', async () => {
    const { user } = renderWithQuery(<DashboardPage />);
    await user.click(screen.getByRole('button', { name: 'Settings' }));
    await act(() => user.click(screen.getByRole('button', { name: 'settings-logout' })));
    expect(nav.router.push).toHaveBeenCalledWith('/login');
  });
});

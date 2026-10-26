import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Synthetic profile only.
const PROFILE = {
  id: 'u1',
  email: 'asha@example.com',
  name: 'Asha Example',
  headline: 'Backend developer',
  experience: [
    { title: 'Intern', company: 'Sample Labs', dates: '2025', highlights: ['Built APIs'] },
  ],
  education: [],
  skills: ['Python', 'React'],
  certifications: [],
  achievements: ['Won a hackathon'],
};

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
  listProjects: vi.fn(),
  getIngestStatus: vi.fn(),
  ingest: vi.fn(),
  toast: vi.fn(),
}));
vi.mock('@/lib/api', () => ({
  default: { get: mocks.get, put: mocks.put, post: mocks.post },
  githubApi: {
    listProjects: mocks.listProjects,
    getIngestStatus: mocks.getIngestStatus,
    ingest: mocks.ingest,
  },
}));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: mocks.toast }) }));

import { ProfileView } from '@/components/dashboard/profile-view';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.get.mockResolvedValue({ data: PROFILE });
  mocks.put.mockImplementation(async (_url: string, body: object) => ({
    data: { ...PROFILE, ...body },
  }));
  mocks.listProjects.mockResolvedValue({
    data: [
      {
        projectId: 'p1',
        name: 'job-scout',
        oneLiner: 'Ranks postings',
        technologies: ['Python', 'AWS'],
      },
    ],
  });
  mocks.getIngestStatus.mockResolvedValue({ data: { status: 'none', summary: null } });
});

describe('ProfileView', () => {
  it('loads the profile into the form sections', async () => {
    render(<ProfileView />);
    expect(await screen.findByDisplayValue('Asha Example')).toBeInTheDocument();
    expect(screen.getByDisplayValue('asha@example.com')).toBeDisabled();
    expect(screen.getByDisplayValue('Backend developer')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Sample Labs')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Won a hackathon')).toBeInTheDocument();
    expect(await screen.findByText('job-scout')).toBeInTheDocument();
  });

  it('saves edited fields through PUT /api/auth/profile', async () => {
    const user = userEvent.setup();
    render(<ProfileView />);
    const name = await screen.findByLabelText('Full Name');
    await user.clear(name);
    await user.type(name, 'Asha E.');
    await user.click(screen.getAllByRole('button', { name: 'Save Changes' })[0]);

    await waitFor(() => expect(mocks.put).toHaveBeenCalledTimes(1));
    const [url, body] = mocks.put.mock.calls[0];
    expect(url).toBe('/api/auth/profile');
    expect(body).toMatchObject({
      name: 'Asha E.',
      headline: 'Backend developer',
      skills: ['Python', 'React'],
    });
  });

  it('shows an error toast when saving fails', async () => {
    mocks.put.mockRejectedValue(new Error('500'));
    const user = userEvent.setup();
    render(<ProfileView />);
    await screen.findByDisplayValue('Asha Example');
    await user.click(screen.getAllByRole('button', { name: 'Save Changes' })[0]);
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ variant: 'destructive' }))
    );
  });

  it('imports from the stored LinkedIn URL and reloads the profile', async () => {
    mocks.get.mockResolvedValue({
      data: { ...PROFILE, linkedin_url: 'https://www.linkedin.com/in/asha-example' },
    });
    mocks.post.mockResolvedValue({ data: { success: true, imported: { headline: true } } });
    const user = userEvent.setup();
    render(<ProfileView />);
    await user.click(await screen.findByRole('button', { name: /Import from LinkedIn/ }));

    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith({
        title: 'Import Complete!',
        description: 'Imported: headline',
      })
    );
    expect(mocks.post).toHaveBeenCalledWith('/api/auth/linkedin/import-profile', {
      linkedin_url: 'https://www.linkedin.com/in/asha-example',
    });
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });

  it('asks for a LinkedIn URL when none is stored', async () => {
    mocks.post.mockRejectedValue({ response: { data: { detail: 'Login wall' } } });
    const user = userEvent.setup();
    render(<ProfileView />);
    await user.click(await screen.findByRole('button', { name: /Import from LinkedIn/ }));

    const box = screen.getByPlaceholderText('https://linkedin.com/in/your-profile');
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled();
    await user.type(box, 'https://linkedin.com/in/asha{Enter}');

    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Import Failed', description: 'Login wall' })
      )
    );
    expect(screen.queryByPlaceholderText('https://linkedin.com/in/your-profile')).toBeNull();
  });

  it('closes the URL prompt on Cancel', async () => {
    const user = userEvent.setup();
    render(<ProfileView />);
    await user.click(await screen.findByRole('button', { name: /Import from LinkedIn/ }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByPlaceholderText('https://linkedin.com/in/your-profile')).toBeNull();
  });

  it('tells the user when there is no profile yet', async () => {
    mocks.get.mockResolvedValue({ data: null });
    render(<ProfileView />);
    expect(await screen.findByText('No profile data found')).toBeInTheDocument();
  });
});

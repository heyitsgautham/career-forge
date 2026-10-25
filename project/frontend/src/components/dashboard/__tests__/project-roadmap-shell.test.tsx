import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { SUGGESTION, makeRoadmap } from '@/test/roadmaps';

const api = vi.hoisted(() => ({
  projectRoadmapApi: {
    list: vi.fn(),
    suggest: vi.fn(),
    plan: vi.fn(),
    get: vi.fn(),
    markDayComplete: vi.fn(),
    unlockAll: vi.fn(),
    delete: vi.fn(),
  },
}));
vi.mock('@/lib/api', () => api);
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

import { ProjectRoadmapShell } from '@/components/dashboard/project-roadmap-shell';

beforeEach(() => {
  vi.clearAllMocks();
  api.projectRoadmapApi.list.mockResolvedValue({ data: { roadmaps: [] } });
});

describe('ProjectRoadmapShell', () => {
  it('walks from a domain to a plan and opens a day', async () => {
    api.projectRoadmapApi.suggest.mockResolvedValue({
      data: { domain: 'Backend Development', projects: [SUGGESTION] },
    });
    api.projectRoadmapApi.plan.mockResolvedValue({ data: makeRoadmap(0) });
    const { user } = renderWithQuery(<ProjectRoadmapShell />);

    await user.click(screen.getByRole('button', { name: 'Backend Development' }));
    await user.click(screen.getByRole('button', { name: /Suggest 3 Projects/ }));
    await user.click(await screen.findByText('Job board API'));
    await user.click(await screen.findByRole('heading', { name: 'Day 1 build' }));

    expect(screen.getByRole('button', { name: /Mark Day 1 Complete/ })).toBeInTheDocument();
    expect(api.projectRoadmapApi.suggest).toHaveBeenCalledWith('Backend Development');
  });

  it('reopens a saved roadmap from the history', async () => {
    api.projectRoadmapApi.list.mockResolvedValue({ data: { roadmaps: [makeRoadmap(3)] } });
    api.projectRoadmapApi.get.mockResolvedValue({ data: makeRoadmap(3) });
    const { user } = renderWithQuery(<ProjectRoadmapShell />);

    await user.click(await screen.findByText('Job board API'));

    expect(await screen.findByRole('heading', { name: 'Day 4 build' })).toBeInTheDocument();
    expect(api.projectRoadmapApi.get).toHaveBeenCalledWith('pr1');
  });
});

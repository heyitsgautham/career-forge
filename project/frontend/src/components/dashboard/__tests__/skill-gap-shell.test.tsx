import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { ROLES, makeLearningRoadmap, makeReport } from '@/test/skill-gap';

const api = vi.hoisted(() => ({
  skillGapApi: { getRoles: vi.fn(), analyse: vi.fn() },
  roadmapApi: { generate: vi.fn(), markComplete: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock('recharts', async (importOriginal) => {
  const original = await importOriginal<typeof import('recharts')>();
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  };
});

import { SkillGapShell } from '@/components/dashboard/skill-gap-shell';

beforeEach(() => {
  vi.clearAllMocks();
  api.skillGapApi.getRoles.mockResolvedValue({ data: { roles: ROLES } });
});

describe('SkillGapShell', () => {
  it('needs a role before it analyses', async () => {
    renderWithQuery(<SkillGapShell />);
    await screen.findByText('Backend Engineer');
    expect(screen.getByRole('button', { name: 'Run Skill Gap Analysis' })).toBeDisabled();
  });

  it('analyses the chosen role, then builds its roadmap', async () => {
    api.skillGapApi.analyse.mockResolvedValue({ data: makeReport() });
    api.roadmapApi.generate.mockResolvedValue({ data: makeLearningRoadmap() });
    const { user } = renderWithQuery(<SkillGapShell />);

    await user.click(await screen.findByText('Backend Engineer'));
    await user.click(screen.getByRole('button', { name: 'Run Skill Gap Analysis' }));
    expect(await screen.findByText('62%')).toBeInTheDocument();
    expect(api.skillGapApi.analyse).toHaveBeenCalledWith('backend');

    await user.click(screen.getByRole('button', { name: /Generate Learning Roadmap/ }));
    expect(await screen.findByText('Week 1: Queue worker 1')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Generate Learning Roadmap/ })
    ).not.toBeInTheDocument();
  });

  it('builds the roadmap for the analysed role even after another role is picked', async () => {
    // Regression: the roadmap request paired the newly picked role with the old report.
    api.skillGapApi.analyse.mockResolvedValue({ data: makeReport() });
    api.roadmapApi.generate.mockResolvedValue({ data: makeLearningRoadmap() });
    const { user } = renderWithQuery(<SkillGapShell />);

    await user.click(await screen.findByText('Backend Engineer'));
    await user.click(screen.getByRole('button', { name: 'Run Skill Gap Analysis' }));
    await screen.findByText('62%');
    await user.click(screen.getByText('ML Engineer'));
    await user.click(screen.getByRole('button', { name: /Generate Learning Roadmap/ }));

    expect(api.roadmapApi.generate).toHaveBeenCalledWith('backend', 'rep1');
  });
});

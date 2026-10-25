import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ROLES, makeLearningRoadmap, makeReport } from '@/test/skill-gap';

const api = vi.hoisted(() => ({
  skillGapApi: { getRoles: vi.fn(), analyse: vi.fn() },
  roadmapApi: { generate: vi.fn(), markComplete: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { useSkillGap } from '../use-skill-gap';

function renderSkillGap() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useSkillGap(), { wrapper });
}

beforeEach(() => {
  vi.clearAllMocks();
  api.skillGapApi.getRoles.mockResolvedValue({ data: { roles: ROLES } });
});

describe('useSkillGap', () => {
  it('loads the roles', async () => {
    const { result } = renderSkillGap();
    await waitFor(() => expect(result.current.roles).toHaveLength(2));
    expect(result.current.loadingRoles).toBe(false);
  });

  it('does nothing until a role is chosen', async () => {
    const { result } = renderSkillGap();
    await act(() => result.current.analyse(null));
    expect(api.skillGapApi.analyse).not.toHaveBeenCalled();
  });

  it('stores the report and announces the fit', async () => {
    api.skillGapApi.analyse.mockResolvedValue({ data: makeReport() });
    const { result } = renderSkillGap();
    await act(() => result.current.analyse('backend'));
    expect(result.current.report?.reportId).toBe('rep1');
    expect(result.current.analysing).toBe(false);
    expect(toast).toHaveBeenCalledWith({
      title: 'Analysis complete!',
      description: 'Overall fit: 62%',
    });
  });

  it('says so when the analysis returns no report', async () => {
    api.skillGapApi.analyse.mockResolvedValue({ data: { report: null } });
    const { result } = renderSkillGap();
    await act(() => result.current.analyse('backend'));
    expect(result.current.report).toBeNull();
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'No results' }));
  });

  it('explains a failed analysis', async () => {
    api.skillGapApi.analyse.mockRejectedValue({ response: { data: { detail: 'No projects' } } });
    const { result } = renderSkillGap();
    await act(() => result.current.analyse('backend'));
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Analysis failed', description: 'No projects' })
    );
  });

  it('builds a roadmap from the report and marks weeks complete', async () => {
    api.skillGapApi.analyse.mockResolvedValue({ data: makeReport() });
    api.roadmapApi.generate.mockResolvedValue({ data: makeLearningRoadmap(0) });
    api.roadmapApi.markComplete.mockResolvedValue({ data: makeLearningRoadmap(1) });
    const { result } = renderSkillGap();
    await act(() => result.current.analyse('backend'));
    await act(() => result.current.generateRoadmap());

    expect(api.roadmapApi.generate).toHaveBeenCalledWith('backend', 'rep1');
    expect(result.current.roadmap?.roadmapId).toBe('rm1');
    expect(result.current.roadmapOpen).toBe(true);

    await act(() => result.current.markWeekComplete(1));
    expect(api.roadmapApi.markComplete).toHaveBeenCalledWith('rm1', 1);
    expect(result.current.roadmap?.completedWeeks).toBe(1);
    expect(toast).toHaveBeenCalledWith({ title: 'Week 1 completed!' });

    act(() => result.current.toggleRoadmap());
    expect(result.current.roadmapOpen).toBe(false);
  });

  it('reports roadmap and milestone failures', async () => {
    api.skillGapApi.analyse.mockResolvedValue({ data: makeReport() });
    api.roadmapApi.generate
      .mockRejectedValueOnce({ response: { data: { detail: 'Bedrock down' } } })
      .mockResolvedValueOnce({ data: makeLearningRoadmap(0) });
    api.roadmapApi.markComplete.mockRejectedValue(new Error('500'));
    const { result } = renderSkillGap();
    await act(() => result.current.analyse('backend'));

    await act(() => result.current.generateRoadmap());
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Roadmap generation failed', description: 'Bedrock down' })
    );

    await act(() => result.current.generateRoadmap());
    await act(() => result.current.markWeekComplete(2));
    expect(toast).toHaveBeenCalledWith({
      title: 'Failed to update milestone',
      variant: 'destructive',
    });
  });
});

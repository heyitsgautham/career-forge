import type { ProjectRoadmap, ProjectSuggestion, RoadmapDay } from '@/lib/api';

export function makeDay(day: number, overrides: Partial<RoadmapDay> = {}): RoadmapDay {
  return {
    day,
    title: `Day ${day} build`,
    description: `Work for day ${day}`,
    tasks: [`Task ${day}a`, `Task ${day}b`],
    techDetails: 'FastAPI routers',
    architecture: 'API in front of a queue',
    resources: [{ title: 'FastAPI docs', url: 'https://fastapi.tiangolo.com' }],
    estimatedHours: 3,
    completedAt: null,
    ...overrides,
  };
}

/** A synthetic seven-day roadmap with the first `completed` days done. */
export function makeRoadmap(
  completed = 0,
  overrides: Partial<ProjectRoadmap> = {}
): ProjectRoadmap {
  const days = Array.from({ length: 7 }, (_, i) =>
    makeDay(i + 1, i < completed ? { completedAt: '2026-03-0' + (i + 1) } : {})
  );
  return {
    projectRoadmapId: 'pr1',
    domain: 'Backend Development',
    projectTitle: 'Job board API',
    projectDescription: 'A REST API for postings',
    techStack: ['Python', 'FastAPI'],
    totalHours: 21,
    days,
    completedDays: completed,
    totalDays: 7,
    unlockedAll: false,
    createdAt: '2026-03-01T00:00:00Z',
    ...overrides,
  };
}

export const SUGGESTION: ProjectSuggestion = {
  id: 1,
  title: 'Job board API',
  difficulty: 'medium',
  description: 'A REST API for postings',
  techStack: ['Python', 'FastAPI'],
  keySkills: ['REST'],
  estimatedHours: 21,
};

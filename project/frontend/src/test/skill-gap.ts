import type { Roadmap, Role, SkillGapReport } from '@/lib/api';

export const ROLES: Role[] = [
  {
    roleId: 'backend',
    role: 'Backend Engineer',
    icon: 'Server',
    description: 'APIs',
    skillDomains: [],
  },
  { roleId: 'ml', role: 'ML Engineer', icon: 'Unknown', description: 'Models', skillDomains: [] },
];

export function makeReport(overrides: Partial<SkillGapReport> = {}): SkillGapReport {
  return {
    reportId: 'rep1',
    userId: 'u1',
    roleId: 'backend',
    roleName: 'Backend Engineer',
    userScores: {},
    benchmarkScores: {},
    gaps: [
      {
        domain: 'Distributed Systems and Messaging',
        userScore: 40,
        requiredScore: 80,
        gap: 40,
        priority: 'high',
      },
      {
        domain: 'APIs',
        userScore: 75,
        requiredScore: 80,
        gap: 5,
        priority: 'low',
      },
    ],
    overallFitPercent: 62,
    projectCount: 3,
    createdAt: '2026-03-01T00:00:00Z',
    ...overrides,
  };
}

export function makeLearningRoadmap(completedWeeks = 0): Roadmap {
  return {
    roadmapId: 'rm1',
    roleId: 'backend',
    roleName: 'Backend Engineer',
    weeks: [1, 2].map((week) => ({
      week,
      projectTitle: `Queue worker ${week}`,
      description: `Build part ${week}`,
      techStack: ['Python'],
      estimatedHours: 6,
      resources: [{ title: 'Docs', url: 'https://docs.example.com' }],
      completedAt: week <= completedWeeks ? '2026-03-02' : null,
    })),
    completedWeeks,
    totalWeeks: 2,
    createdAt: '2026-03-01T00:00:00Z',
  };
}

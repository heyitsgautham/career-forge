// ─── Type Interfaces ──────────────────────────────────────────────────────────

export interface User {
  userId: string;
  username: string;
  email: string;
  avatarUrl: string;
  name?: string;
  githubToken?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  website?: string;
  experience?: Array<{
    title: string;
    company: string;
    location?: string;
    start_date: string;
    end_date?: string;
    highlights: string[];
  }>;
  education?: Array<{
    degree: string;
    school: string;
    location?: string;
    graduation_date: string;
    gpa?: string;
  }>;
  certifications?: string[];
  skills?: string[];
}

export interface Project {
  projectId: string;
  id?: string;
  name: string;
  title?: string;
  description: string;
  skills: string[];
  technologies?: string[];
  repoUrl: string;
  url?: string;
  highlights?: string[];
  start_date?: string;
  end_date?: string;
}

export interface Resume {
  resumeId: string;
  id?: string;
  name?: string;
  pdfUrl: string;
  texUrl: string;
  createdAt: string;
  jobDescriptionId?: string;
  jobId?: string;
  type?: string;
  status?: string;
}

export interface SkillGap {
  domain: string;
  userScore: number;
  requiredScore: number;
  gap: number;
  priority: 'high' | 'medium' | 'low';
}

export interface SkillGapReport {
  reportId: string;
  userId: string;
  roleId: string;
  roleName: string;
  userScores: Record<string, number>;
  benchmarkScores: Record<string, number>;
  gaps: SkillGap[];
  overallFitPercent: number;
  projectCount: number;
  createdAt: string;
  report?: null; // present when no report found
}

export type { Job } from './schemas';

export interface Application {
  applicationId: string;
  userId: string;
  jobId: string;
  companyName: string;
  roleTitle: string;
  status: 'saved' | 'applied' | 'viewed' | 'interviewing' | 'offered' | 'rejected';
  appliedAt: string;
  updatedAt: string;
  resumeId?: string;
  notes?: string;
  url?: string;
}

export interface RoadmapWeek {
  week: number;
  projectTitle: string;
  description?: string;
  techStack: string[];
  estimatedHours: number;
  resources: Array<{ title: string; url: string }>;
  completedAt?: string | null;
}

export interface Roadmap {
  roadmapId: string;
  userId?: string;
  roleId: string;
  roleName: string;
  reportId?: string;
  overallFitPercent?: number;
  weeks: RoadmapWeek[];
  completedWeeks: number;
  totalWeeks: number;
  createdAt: string;
}

// ─── Skill Gap API ────────────────────────────────────────────────────────────

export interface Role {
  roleId: string;
  role: string;
  icon: string;
  description: string;
  skillDomains: string[];
}

// ─── New interfaces for Job Scout v2 ──────────────────────────────────────────

export interface SchedulerStatus {
  running: boolean;
  nextRunTime: string | null;
  lastScrape: {
    timestamp: string | null;
    total_jobs: number;
    new_jobs: number;
    status: string | null;
    message: string | null;
  } | null;
}

export interface TrackingStatuses {
  [jobId: string]: { status: string; notes: string };
}

export interface BlacklistedCompany {
  companyName: string;
  addedBy?: string;
  createdAt?: string;
}

// ─── Applications API (M5) ─────────────────────────────────────────────────

export interface TailorResponse {
  resumeId: string;
  pdfUrl: string | null;
  texUrl: string | null;
  jobId: string;
  matchKeywords: string[];
  diffSummary: {
    skillsReordered?: boolean;
    projectsChanged?: string[];
    keywordsInjected?: string[];
    bulletsRewritten?: number;
    sectionsModified?: string[];
  };
  compilationError?: string | null;
}

export interface ApplicationStats {
  total: number;
  saved: number;
  applied: number;
  viewed: number;
  interviewing: number;
  offered: number;
  rejected: number;
}

// ─── Project Roadmap API ──────────────────────────────────────────────────────

export interface ProjectSuggestion {
  id: number;
  title: string;
  difficulty: 'medium' | 'hard';
  description: string;
  techStack: string[];
  keySkills: string[];
  estimatedHours: number;
}

export interface SuggestResponse {
  domain: string;
  projects: ProjectSuggestion[];
}

export interface RoadmapDay {
  day: number;
  title: string;
  description: string;
  tasks: string[];
  techDetails: string;
  architecture: string;
  resources: Array<{ title: string; url: string }>;
  estimatedHours: number;
  completedAt?: string | null;
}

export interface ProjectRoadmap {
  projectRoadmapId: string;
  userId?: string;
  domain: string;
  projectTitle: string;
  projectDescription: string;
  techStack: string[];
  totalHours: number;
  days: RoadmapDay[];
  completedDays: number;
  totalDays: number;
  unlockedAll?: boolean;
  createdAt: string;
}

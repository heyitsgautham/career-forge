import { FileText, FolderGit2, Map, Search, Send, Target } from 'lucide-react';

/** Tabs shown in the dashboard sidebar, in display order. */
export const TABS = [
  { key: 'resumes', label: 'Resumes', icon: FileText },
  { key: 'projects', label: 'Projects', icon: FolderGit2 },
  { key: 'roadmap', label: 'Roadmap', icon: Map },
  { key: 'skill-gap', label: 'Skill Gap', icon: Target },
  { key: 'job-scout', label: 'Job Scout', icon: Search },
  { key: 'apply', label: 'Apply & Track', icon: Send },
] as const;

/** Tabs removed from the sidebar that stay reachable through `?tab=`. */
export const HIDDEN_TABS = ['jobs', 'templates'] as const;

export type TabKey = (typeof TABS)[number]['key'] | (typeof HIDDEN_TABS)[number] | 'profile';

const TAB_KEYS: readonly string[] = [...TABS.map((t) => t.key), ...HIDDEN_TABS, 'profile'];

/** Returns the tab named by a `?tab=` value, or null when it names no tab. */
export function parseTab(value: string | null | undefined): TabKey | null {
  return value && TAB_KEYS.includes(value) ? (value as TabKey) : null;
}

export const TAB_TITLES: Record<TabKey, string> = {
  resumes: 'Resumes',
  projects: 'Projects',
  roadmap: 'Project Roadmap',
  jobs: 'Jobs',
  templates: 'Templates',
  'skill-gap': 'Skill Gap',
  'job-scout': 'Job Scout',
  apply: 'Apply & Track',
  profile: 'Profile',
};

export const TAB_DESCRIPTIONS: Record<TabKey, string> = {
  resumes: 'Generate and manage your LaTeX resumes',
  projects: 'Your imported projects and repositories',
  roadmap: 'AI-generated project-based learning paths',
  jobs: 'Job descriptions to tailor resumes to',
  templates: 'LaTeX templates for your resumes',
  'skill-gap': 'AI-powered gap analysis against target roles',
  'job-scout': 'Matched jobs ranked by fit',
  apply: 'Generate tailored resumes and track applications',
  profile: 'View and edit your profile information',
};

// ── Category filter labels ───────────────────────────────────────────────────

export const CATEGORIES = [
  'All',
  'SDE',
  'AI/ML',
  'Data',
  'Web',
  'Mobile',
  'DevOps',
  'Security',
  'Embedded',
  'Blockchain',
  'Research',
  'Database',
  'GenAI',
] as const;

export const TRACKING_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offered', label: 'Offered' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'ignored', label: 'Ignored' },
];

export const TRACKING_COLORS: Record<string, string> = {
  pending: 'bg-muted text-muted-foreground',
  saved: 'bg-primary/10 text-primary',
  applied: 'bg-[hsl(var(--accent))]/10 text-[hsl(var(--accent))]',
  interviewing: 'bg-primary/10 text-primary',
  offered: 'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]',
  rejected: 'bg-destructive/10 text-destructive',
  ignored: 'bg-muted text-muted-foreground',
};

export const ROWS_PER_PAGE = 25;

// Statuses that exist in the Apply & Track Kanban pipeline
export const KANBAN_STATUSES = new Set(['applied', 'interviewing', 'offered', 'rejected']);

// ── Source filter options ────────────────────────────────────────────────────

export const SOURCES = ['All', 'naukri', 'linkedin', 'indeed', 'unstop'] as const;

export type SourceFilter = (typeof SOURCES)[number];

// ── Month names for posted dates ────────────────────────────────────────────

export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

// ── Source logo/favicon ──────────────────────────────────────────────────────

export const SOURCE_ICONS: Record<string, string> = {
  linkedin:    '/icons/linkedin.jpg',
  indeed:      '/icons/indeed-copy.jpeg',
  naukri:      '/icons/naukri.png',
  unstop:      '/icons/unstop.jpg',
  internshala: '/icons/internshala.jpeg',
};

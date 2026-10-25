/* ─── Domain suggestions for quick-pick ──────────────────────────────────── */
export const DOMAIN_CHIPS = [
  'Web Development',
  'Backend Development',
  'Mobile Development',
  'Machine Learning',
  'Data Engineering',
  'DevOps & Cloud',
  'Blockchain',
  'Game Development',
  'Cybersecurity',
  'AI / LLM Apps',
  'System Design',
  'Embedded Systems',
];

/* ─── Day theme colours (cycle through a spectrum) ───────────────────────── */
export const DAY_COLORS = [
  {
    ring: 'ring-blue-400',
    bg: 'bg-blue-500',
    bgLight: 'bg-blue-50 dark:bg-blue-950/40',
    text: 'text-blue-600 dark:text-blue-400',
    glow: 'shadow-blue-400/40',
  },
  {
    ring: 'ring-violet-400',
    bg: 'bg-violet-500',
    bgLight: 'bg-violet-50 dark:bg-violet-950/40',
    text: 'text-violet-600 dark:text-violet-400',
    glow: 'shadow-violet-400/40',
  },
  {
    ring: 'ring-amber-400',
    bg: 'bg-amber-500',
    bgLight: 'bg-amber-50 dark:bg-amber-950/40',
    text: 'text-amber-600 dark:text-amber-400',
    glow: 'shadow-amber-400/40',
  },
  {
    ring: 'ring-emerald-400',
    bg: 'bg-emerald-500',
    bgLight: 'bg-emerald-50 dark:bg-emerald-950/40',
    text: 'text-emerald-600 dark:text-emerald-400',
    glow: 'shadow-emerald-400/40',
  },
  {
    ring: 'ring-rose-400',
    bg: 'bg-rose-500',
    bgLight: 'bg-rose-50 dark:bg-rose-950/40',
    text: 'text-rose-600 dark:text-rose-400',
    glow: 'shadow-rose-400/40',
  },
  {
    ring: 'ring-cyan-400',
    bg: 'bg-cyan-500',
    bgLight: 'bg-cyan-50 dark:bg-cyan-950/40',
    text: 'text-cyan-600 dark:text-cyan-400',
    glow: 'shadow-cyan-400/40',
  },
  {
    ring: 'ring-orange-400',
    bg: 'bg-orange-500',
    bgLight: 'bg-orange-50 dark:bg-orange-950/40',
    text: 'text-orange-600 dark:text-orange-400',
    glow: 'shadow-orange-400/40',
  },
];

/** Whole-number percentage of days done. A roadmap with no days counts as 0%. */
export function progressPercent(completed: number, total: number): number {
  return total > 0 ? Math.round((completed / total) * 100) : 0;
}

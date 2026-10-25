import { Send, CheckCircle2, XCircle, PhoneCall } from 'lucide-react';
import type { Application } from '@/lib/api';

/* ─── Constants ──────────────────────────────────────────────────────────── */

export const COLUMNS = [
  { key: 'applied', label: 'Applied', icon: Send, color: 'text-primary', bg: 'bg-primary/10' },
  {
    key: 'interviewing',
    label: 'Interviewing',
    icon: PhoneCall,
    color: 'text-[hsl(var(--accent))]',
    bg: 'bg-[hsl(var(--accent))]/10',
  },
  {
    key: 'offered',
    label: 'Offer',
    icon: CheckCircle2,
    color: 'text-[hsl(var(--success))]',
    bg: 'bg-[hsl(var(--success))]/10',
  },
  {
    key: 'rejected',
    label: 'Rejected',
    icon: XCircle,
    color: 'text-destructive',
    bg: 'bg-destructive/10',
  },
] as const;

/* ─── Helpers ────────────────────────────────────────────────────────────── */

/**
 * Buckets applications into the Kanban columns. Statuses without a column of
 * their own, such as saved and viewed, land in Applied.
 */
export function groupByColumn(applications: Application[]): Record<string, Application[]> {
  const grouped: Record<string, Application[]> = {};
  for (const col of COLUMNS) {
    grouped[col.key] = [];
  }
  for (const app of applications) {
    (grouped[app.status] ?? grouped.applied).push(app);
  }
  return grouped;
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso.slice(0, 10);
  }
}

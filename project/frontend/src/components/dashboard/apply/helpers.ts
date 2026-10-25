import { Send, CheckCircle2, XCircle, PhoneCall } from 'lucide-react';

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

export function getUserId(): string {
  if (typeof window === 'undefined') return '';
  try {
    const token = localStorage.getItem('token');
    if (!token) return '';
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub || '';
  } catch {
    return '';
  }
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

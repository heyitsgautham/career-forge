import { MONTHS } from './constants';

// ── Rich markdown description renderer ───────────────────────────────────────

export function unescapeMarkdown(text: string): string {
  return text.replace(/\\([\-&#+_~`>|{}\[\]()!])/g, '$1');
}

// ── Relative time formatter ──────────────────────────────────────────────────

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function ordinalSuffix(d: number) {
  if (d >= 11 && d <= 13) return 'th';
  return ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th'][d % 10];
}

export function formatPostedDate(
  datePosted: string | undefined | null,
  createdAt: string | undefined | null,
): string {
  // Prefer createdAt (has time); fall back to datePosted
  const src = createdAt || datePosted;
  if (!src || src === 'nan') return '—';
  const d = new Date(src);
  if (isNaN(d.getTime())) return datePosted && datePosted !== 'nan' ? datePosted : '—';
  const day = d.getDate();
  const month = MONTHS[d.getMonth()];
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${day}${ordinalSuffix(day)} ${month}, ${hh}:${mm}`;
}

// ── Current user id from the stored JWT ─────────────────────────────────────

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

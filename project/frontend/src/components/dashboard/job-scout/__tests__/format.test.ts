import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatPostedDate, getUserId, ordinalSuffix, timeAgo, unescapeMarkdown } from '../format';

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
});

describe('unescapeMarkdown', () => {
  it('drops backslashes before markdown punctuation', () => {
    expect(unescapeMarkdown('C\\+\\+ \\& node\\_js \\[remote\\]')).toBe('C++ & node_js [remote]');
  });

  it('leaves other backslashes alone', () => {
    expect(unescapeMarkdown('path\\to')).toBe('path\\to');
  });
});

describe('timeAgo', () => {
  it('buckets elapsed time into minutes, hours and days', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-10T12:00:00Z'));
    expect(timeAgo(null)).toBe('—');
    expect(timeAgo('2026-03-10T11:59:30Z')).toBe('just now');
    expect(timeAgo('2026-03-10T11:15:00Z')).toBe('45m ago');
    expect(timeAgo('2026-03-10T07:00:00Z')).toBe('5h ago');
    expect(timeAgo('2026-03-07T12:00:00Z')).toBe('3d ago');
  });
});

describe('ordinalSuffix', () => {
  it.each([
    [1, 'st'],
    [2, 'nd'],
    [3, 'rd'],
    [4, 'th'],
    [11, 'th'],
    [12, 'th'],
    [13, 'th'],
    [21, 'st'],
    [22, 'nd'],
    [23, 'rd'],
    [30, 'th'],
  ])('%i -> %s', (day, suffix) => {
    expect(ordinalSuffix(day)).toBe(suffix);
  });
});

describe('formatPostedDate', () => {
  it('prefers createdAt and prints day, month and time', () => {
    const created = new Date(2026, 2, 2, 9, 5);
    expect(formatPostedDate('2026-01-01', created.toISOString())).toBe('2nd March, 09:05');
  });

  it('falls back to datePosted when createdAt is missing', () => {
    expect(formatPostedDate(new Date(2026, 0, 21, 18, 30).toISOString(), null)).toBe(
      '21st January, 18:30'
    );
  });

  it('returns the raw text for unparseable dates and a dash for empty ones', () => {
    expect(formatPostedDate('3 days ago', null)).toBe('3 days ago');
    expect(formatPostedDate('nan', null)).toBe('—');
    expect(formatPostedDate(null, null)).toBe('—');
  });
});

describe('getUserId', () => {
  const tokenFor = (payload: object) => `header.${btoa(JSON.stringify(payload))}.sig`;

  it('reads sub from the stored JWT', () => {
    localStorage.setItem('token', tokenFor({ sub: 'user-42' }));
    expect(getUserId()).toBe('user-42');
  });

  it('returns an empty string without a token or with a broken one', () => {
    expect(getUserId()).toBe('');
    localStorage.setItem('token', 'garbage');
    expect(getUserId()).toBe('');
  });
});

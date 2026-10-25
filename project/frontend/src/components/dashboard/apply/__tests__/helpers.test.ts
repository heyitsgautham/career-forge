import { describe, expect, it } from 'vitest';
import { COLUMNS, formatDate, groupByColumn } from '../helpers';
import { makeApplication } from '@/test/applications';

describe('groupByColumn', () => {
  it('gives every column a list, empty or not', () => {
    expect(Object.keys(groupByColumn([]))).toEqual(COLUMNS.map((c) => c.key));
  });

  it('files applications by status and sends saved and viewed to Applied', () => {
    const grouped = groupByColumn([
      makeApplication({ applicationId: 'a1', status: 'interviewing' }),
      makeApplication({ applicationId: 'a2', status: 'saved' }),
      makeApplication({ applicationId: 'a3', status: 'viewed' }),
      makeApplication({ applicationId: 'a4', status: 'rejected' }),
    ]);
    expect(grouped.interviewing.map((a) => a.applicationId)).toEqual(['a1']);
    expect(grouped.applied.map((a) => a.applicationId)).toEqual(['a2', 'a3']);
    expect(grouped.rejected.map((a) => a.applicationId)).toEqual(['a4']);
    expect(grouped.offered).toEqual([]);
  });
});

describe('formatDate', () => {
  it('shows month and day', () => {
    expect(formatDate('2026-03-05T10:00:00Z')).toBe('Mar 5');
  });
});

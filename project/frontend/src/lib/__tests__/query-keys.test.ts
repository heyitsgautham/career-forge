import { describe, expect, it } from 'vitest';
import { CACHE, QUERY_KEYS } from '@/lib/query-keys';

describe('query keys', () => {
  it('builds per-id keys', () => {
    expect(QUERY_KEYS.resume('r1')).toEqual(['resume', 'r1']);
    expect(QUERY_KEYS.template('t1')).toEqual(['template', 't1']);
  });

  it('never garbage-collects data before it goes stale', () => {
    for (const timing of Object.values(CACHE)) {
      expect(timing.gcTime).toBeGreaterThanOrEqual(timing.staleTime);
    }
  });
});

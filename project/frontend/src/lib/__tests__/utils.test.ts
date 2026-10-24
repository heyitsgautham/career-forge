import { describe, expect, it } from 'vitest';
import { cn } from '@/lib/utils';

describe('cn', () => {
  it('joins truthy class names', () => {
    expect(cn('px-2', false && 'hidden', undefined, 'text-sm')).toBe('px-2 text-sm');
  });

  it('lets later Tailwind classes override conflicting earlier ones', () => {
    expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4');
  });
});

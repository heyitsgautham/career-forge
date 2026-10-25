import { afterEach, describe, expect, it } from 'vitest';
import { currentUserId } from '@/lib/session';

const base64url = (text: string) =>
  btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const tokenFor = (payload: object) => `header.${base64url(JSON.stringify(payload))}.sig`;

afterEach(() => localStorage.clear());

describe('currentUserId', () => {
  it('reads sub from the stored JWT', () => {
    localStorage.setItem('token', tokenFor({ sub: 'user-42', exp: 4102444800 }));
    expect(currentUserId()).toBe('user-42');
  });

  it('decodes payloads that use the base64url alphabet', () => {
    // "?>~" encodes to characters only base64url uses.
    const payload = { sub: 'u1', note: '?>~?>~' };
    const token = tokenFor(payload);
    expect(token).toMatch(/[-_]/);
    localStorage.setItem('token', token);
    expect(currentUserId()).toBe('u1');
  });

  it('returns an empty string without a token, with a broken one, or without sub', () => {
    expect(currentUserId()).toBe('');
    localStorage.setItem('token', 'garbage');
    expect(currentUserId()).toBe('');
    localStorage.setItem('token', tokenFor({ exp: 1 }));
    expect(currentUserId()).toBe('');
    localStorage.setItem('token', tokenFor({ sub: 42 }));
    expect(currentUserId()).toBe('');
  });
});

import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { vi } from 'vitest';
import api, { authApi } from '@/lib/api';

const cache = vi.hoisted(() => ({ clearCachedData: vi.fn() }));
vi.mock('@/lib/query-cache', () => cache);

let sent: InternalAxiosRequestConfig[] = [];
let nextStatus = 200;

const fakeAdapter: AxiosAdapter = async (config) => {
  sent.push(config);
  const response = { data: { ok: true }, status: nextStatus, statusText: '', headers: {}, config };
  if (nextStatus >= 400) {
    const error = Object.assign(new Error(`HTTP ${nextStatus}`), {
      response,
      config,
      isAxiosError: true,
    });
    throw error;
  }
  return response;
};

const originalAdapter = api.defaults.adapter;
const originalLocation = window.location;

beforeEach(() => {
  sent = [];
  nextStatus = 200;
  api.defaults.adapter = fakeAdapter;
  localStorage.clear();
  Object.defineProperty(window, 'location', { configurable: true, value: { href: '/dashboard' } });
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
  Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
});

describe('api client', () => {
  it('sends the stored token as a bearer header', async () => {
    localStorage.setItem('token', 'jwt-123');
    await authApi.getProfile();
    expect(sent[0].headers.Authorization).toBe('Bearer jwt-123');
  });

  it('omits the auth header when no token is stored', async () => {
    await authApi.getProfile();
    expect(sent[0].headers.Authorization).toBeUndefined();
  });

  it('disables browser caching on GET requests only', async () => {
    await authApi.getProfile();
    await authApi.login('a@example.com', 'pw');
    expect(sent[0].headers['Cache-Control']).toBe('no-cache');
    expect(sent[1].headers['Cache-Control']).toBeUndefined();
  });

  it('posts register payloads with the backend field names', async () => {
    await authApi.register('a@example.com', 'pw', 'Asha Example');
    expect(sent[0].url).toBe('/api/auth/register');
    expect(JSON.parse(sent[0].data)).toEqual({
      email: 'a@example.com',
      password: 'pw',
      full_name: 'Asha Example',
    });
  });

  it('clears the token and sends the user to login on a 401', async () => {
    localStorage.setItem('token', 'expired');
    nextStatus = 401;
    await expect(authApi.getProfile()).rejects.toThrow('HTTP 401');
    expect(localStorage.getItem('token')).toBeNull();
    expect(window.location.href).toBe('/login');
    expect(cache.clearCachedData).toHaveBeenCalled();
  });

  it('keeps the session on other errors', async () => {
    localStorage.setItem('token', 'valid');
    nextStatus = 500;
    await expect(authApi.getProfile()).rejects.toThrow('HTTP 500');
    expect(localStorage.getItem('token')).toBe('valid');
    expect(window.location.href).toBe('/dashboard');
  });
});

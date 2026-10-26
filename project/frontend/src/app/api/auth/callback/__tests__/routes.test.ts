// @vitest-environment node
import { NextRequest } from 'next/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET as cognito } from '../cognito/route';
import { GET as github } from '../github/route';
import { GET as linkedin } from '../linkedin/route';

const req = (path: string) => new NextRequest(`https://app.example.com${path}`);
const location = (res: Response) => res.headers.get('location');
let fetchMock: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  fetchMock = vi.spyOn(globalThis, 'fetch');
  vi.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

const ok = (body: object) => new Response(JSON.stringify(body), { status: 200 });

describe('GitHub OAuth callback', () => {
  it('exchanges the code and installation id for a session token', async () => {
    fetchMock.mockResolvedValue(ok({ access_token: 'jwt' }));
    const res = await github(
      req('/api/auth/callback/github?code=c1&installation_id=42&state=old-jwt')
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/auth\/github\/callback$/);
    expect(JSON.parse(String(init?.body))).toEqual({
      code: 'c1',
      installation_id: 42,
      link_token: 'old-jwt',
    });
    expect(location(res)).toContain('/dashboard?github=connected');
    expect(location(res)).toContain('jwt');
  });

  it.each([
    ['?error=access_denied', 'github_auth_failed'],
    ['', 'no_code'],
  ])('sends %j back to the dashboard with an error', async (query, error) => {
    const res = await github(req(`/api/auth/callback/github${query}`));
    expect(location(res)).toBe(`https://app.example.com/dashboard?error=${error}`);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('reports a refused exchange and a network failure', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{"detail":"bad code"}', { status: 400 }));
    expect(location(await github(req('/api/auth/callback/github?code=c1')))).toBe(
      'https://app.example.com/dashboard?error=token_exchange_failed'
    );
    fetchMock.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    expect(location(await github(req('/api/auth/callback/github?code=c1')))).toBe(
      'https://app.example.com/dashboard?error=callback_failed'
    );
  });
});

describe('Cognito callback', () => {
  it('exchanges the code and opens the dashboard', async () => {
    fetchMock.mockResolvedValue(ok({ access_token: 'jwt' }));
    const res = await cognito(req('/api/auth/callback/cognito?code=c2'));
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ code: 'c2' });
    expect(location(res)).toContain('/dashboard?google=connected');
  });

  it.each([
    ['?error=denied', 'cognito_auth_failed'],
    ['', 'no_code'],
  ])('sends %j back to login with an error', async (query, error) => {
    const res = await cognito(req(`/api/auth/callback/cognito${query}`));
    expect(location(res)).toBe(`https://app.example.com/login?error=${error}`);
  });

  it('reports a refused exchange', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 401 }));
    expect(location(await cognito(req('/api/auth/callback/cognito?code=c2')))).toBe(
      'https://app.example.com/login?error=token_exchange_failed'
    );
  });
});

describe('LinkedIn callback', () => {
  it('hands the code to the client page', async () => {
    const res = await linkedin(req('/api/auth/callback/linkedin?code=li-1'));
    expect(location(res)).toBe('https://app.example.com/dashboard/linkedin-callback?code=li-1');
  });

  it('passes errors through, encoded', async () => {
    const res = await linkedin(req('/api/auth/callback/linkedin?error=user%20cancelled'));
    expect(location(res)).toBe('https://app.example.com/dashboard?error=user%20cancelled');
    expect(location(await linkedin(req('/api/auth/callback/linkedin')))).toBe(
      'https://app.example.com/dashboard?error=no_code'
    );
  });
});

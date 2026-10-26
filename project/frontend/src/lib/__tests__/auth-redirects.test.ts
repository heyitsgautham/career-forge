import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi, resumesApi } from '@/lib/api';

const originalLocation = window.location;
let errors: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  Object.defineProperty(window, 'location', { configurable: true, value: { href: '/login' } });
  errors = vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://app.example.com/');
});
afterEach(() => {
  Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('OAuth redirects', () => {
  it('sends GitHub sign-in to the OAuth page with the app callback', () => {
    vi.stubEnv('NEXT_PUBLIC_GITHUB_CLIENT_ID', 'gh-client');
    authApi.githubLogin();
    const url = new URL(window.location.href);
    expect(url.origin + url.pathname).toBe('https://github.com/login/oauth/authorize');
    expect(url.searchParams.get('client_id')).toBe('gh-client');
    expect(url.searchParams.get('redirect_uri')).toBe(
      'https://app.example.com/api/auth/callback/github'
    );
    expect(url.searchParams.get('scope')).toBe('read:user user:email repo');
  });

  it('passes the session token as state when installing the GitHub App', () => {
    vi.stubEnv('NEXT_PUBLIC_GITHUB_APP_SLUG', 'careerforge');
    localStorage.setItem('token', 'jwt.with/odd=chars');
    authApi.githubInstall();
    expect(window.location.href).toBe(
      'https://github.com/apps/careerforge/installations/new?state=jwt.with%2Fodd%3Dchars'
    );
  });

  it('installs without state when nobody is signed in', () => {
    vi.stubEnv('NEXT_PUBLIC_GITHUB_APP_SLUG', 'careerforge');
    authApi.githubInstall();
    expect(window.location.href).toBe('https://github.com/apps/careerforge/installations/new');
  });

  it('sends Google sign-in through the Cognito hosted UI', () => {
    vi.stubEnv('NEXT_PUBLIC_COGNITO_DOMAIN', 'auth.example.com');
    vi.stubEnv('NEXT_PUBLIC_COGNITO_CLIENT_ID', 'cog-client');
    authApi.cognitoGoogleLogin();
    const url = new URL(window.location.href);
    expect(url.host).toBe('auth.example.com');
    expect(url.searchParams.get('identity_provider')).toBe('Google');
    expect(url.searchParams.get('redirect_uri')).toBe(
      'https://app.example.com/api/auth/callback/cognito'
    );
  });

  it('stays put and logs when the provider is not configured', () => {
    vi.stubEnv('NEXT_PUBLIC_GITHUB_CLIENT_ID', '');
    vi.stubEnv('NEXT_PUBLIC_GITHUB_APP_SLUG', '');
    vi.stubEnv('NEXT_PUBLIC_COGNITO_DOMAIN', '');
    authApi.githubLogin();
    authApi.githubInstall();
    authApi.cognitoGoogleLogin();
    expect(window.location.href).toBe('/login');
    expect(errors).toHaveBeenCalledTimes(3);
  });
});

describe('resumesApi.aiEdit', () => {
  it('posts the message with the bearer token and returns the stream response', async () => {
    localStorage.setItem('token', 'jwt');
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('data: {}\n'));
    const response = await resumesApi.aiEdit('r1', 'Shorten it', '\\x');
    expect(response.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/resumes\/r1\/ai-edit$/);
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt');
    expect(JSON.parse(init?.body as string)).toEqual({
      message: 'Shorten it',
      latex_content: '\\x',
    });
  });

  it('throws on an HTTP error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 503 }));
    await expect(resumesApi.aiEdit('r1', 'x', 'y')).rejects.toThrow('AI edit failed: 503');
  });
});

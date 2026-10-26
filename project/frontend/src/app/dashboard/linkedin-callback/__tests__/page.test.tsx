import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const nav = vi.hoisted(() => ({ params: new URLSearchParams(), router: { push: vi.fn() } }));
vi.mock('next/navigation', () => ({
  useRouter: () => nav.router,
  useSearchParams: () => nav.params,
}));
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import LinkedInCallbackPage from '@/app/dashboard/linkedin-callback/page';

let fetchMock: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  vi.clearAllMocks();
  fetchMock = vi.spyOn(globalThis, 'fetch');
  localStorage.setItem('token', 'jwt');
  nav.params = new URLSearchParams('code=li-1');
});
afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('LinkedIn callback page', () => {
  it('sends the code with the session token and returns to the dashboard', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    render(<LinkedInCallbackPage />);
    await waitFor(() => expect(nav.router.push).toHaveBeenCalledWith('/dashboard'));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/auth\/linkedin\/callback$/);
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt');
    expect(JSON.parse(String(init?.body))).toEqual({ code: 'li-1' });
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'LinkedIn Connected!' }));
  });

  it('shows the backend reason when the exchange fails', async () => {
    fetchMock.mockResolvedValue(new Response('{"detail":"Code expired"}', { status: 400 }));
    render(<LinkedInCallbackPage />);
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(expect.objectContaining({ description: 'Code expired' }))
    );
  });

  it('needs a code and a signed-in user', async () => {
    nav.params = new URLSearchParams();
    const { unmount } = render(<LinkedInCallbackPage />);
    await waitFor(() => expect(nav.router.push).toHaveBeenCalledWith('/dashboard'));
    unmount();

    nav.params = new URLSearchParams('code=li-1');
    localStorage.clear();
    render(<LinkedInCallbackPage />);
    await waitFor(() => expect(nav.router.push).toHaveBeenCalledWith('/login'));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('reports a network failure', async () => {
    fetchMock.mockRejectedValue(new Error('offline'));
    render(<LinkedInCallbackPage />);
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Failed to process LinkedIn callback' })
      )
    );
  });
});

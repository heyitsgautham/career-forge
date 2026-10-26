import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router }));
const api = vi.hoisted(() => ({
  authApi: { githubLogin: vi.fn(), cognitoGoogleLogin: vi.fn(), login: vi.fn(), register: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

import LoginPage from '@/app/login/page';

beforeEach(() => vi.clearAllMocks());
afterEach(() => localStorage.clear());

describe('LoginPage', () => {
  it('sends a signed-in visitor straight to the dashboard', () => {
    localStorage.setItem('token', 'jwt');
    render(<LoginPage />);
    expect(router.replace).toHaveBeenCalledWith('/dashboard');
  });

  it('starts GitHub and Google sign-in from their buttons', async () => {
    render(<LoginPage />);
    await userEvent.click(screen.getByRole('button', { name: 'Continue with GitHub' }));
    await userEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(api.authApi.githubLogin).toHaveBeenCalledOnce();
    expect(api.authApi.cognitoGoogleLogin).toHaveBeenCalledOnce();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it('reveals the email forms on demand', async () => {
    render(<LoginPage />);
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Or use email/ }));
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Sign Up' }));
    expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument();
  });
});

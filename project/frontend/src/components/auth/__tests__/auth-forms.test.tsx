import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router }));
const api = vi.hoisted(() => ({ authApi: { login: vi.fn(), register: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { SignInForm } from '../sign-in-form';
import { SignUpForm } from '../sign-up-form';

beforeEach(() => vi.clearAllMocks());
afterEach(() => localStorage.clear());

describe('SignInForm', () => {
  it('signs in, stores the token and opens the dashboard', async () => {
    api.authApi.login.mockResolvedValue({ data: { access_token: 'jwt' } });
    render(<SignInForm />);
    await userEvent.type(screen.getByLabelText('Email'), 'asha@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'pw-1234');
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith('/dashboard'));
    expect(api.authApi.login).toHaveBeenCalledWith('asha@example.com', 'pw-1234');
    expect(localStorage.getItem('token')).toBe('jwt');
  });

  it('shows the reason a sign-in failed', async () => {
    api.authApi.login.mockRejectedValue({
      response: { data: { detail: 'Incorrect email or password' } },
    });
    render(<SignInForm />);
    await userEvent.type(screen.getByLabelText('Email'), 'asha@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Login failed',
        description: 'Incorrect email or password',
        variant: 'destructive',
      })
    );
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeEnabled();
  });
});

describe('SignUpForm', () => {
  async function fill(password: string, confirm: string) {
    await userEvent.type(screen.getByLabelText('Full Name'), 'Asha Example');
    await userEvent.type(screen.getByLabelText('Email'), 'asha@example.com');
    await userEvent.type(screen.getByLabelText('Password'), password);
    await userEvent.type(screen.getByLabelText('Confirm Password'), confirm);
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }));
  }

  it('refuses mismatched passwords without calling the API', async () => {
    render(<SignUpForm />);
    await fill('pw-1234', 'pw-9999');
    expect(api.authApi.register).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Passwords do not match' })
    );
  });

  it('creates the account and opens the dashboard', async () => {
    api.authApi.register.mockResolvedValue({ data: { access_token: 'new-jwt' } });
    render(<SignUpForm />);
    await fill('pw-1234', 'pw-1234');
    await waitFor(() => expect(router.push).toHaveBeenCalledWith('/dashboard'));
    expect(api.authApi.register).toHaveBeenCalledWith(
      'asha@example.com',
      'pw-1234',
      'Asha Example'
    );
    expect(localStorage.getItem('token')).toBe('new-jwt');
  });

  it('explains a refused registration', async () => {
    api.authApi.register.mockRejectedValue({
      response: { data: { detail: 'Email already registered' } },
    });
    render(<SignUpForm />);
    await fill('pw-1234', 'pw-1234');
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Registration failed',
          description: 'Email already registered',
        })
      )
    );
  });
});

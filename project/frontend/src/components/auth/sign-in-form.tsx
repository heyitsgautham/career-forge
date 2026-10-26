'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { clearCachedData } from '@/lib/query-cache';

/** Email and password sign-in. Stores the token and opens the dashboard on success. */
export function SignInForm() {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isLoading, setIsLoading] = useState(false);
  const [loginData, setLoginData] = useState({ email: '', password: '' });

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const res = await authApi.login(loginData.email, loginData.password);
      localStorage.setItem('token', res.data.access_token);
      // A new session must not see what the previous user left in the cache.
      await clearCachedData(queryClient);
      toast({ title: 'Welcome back!' });
      router.push('/dashboard');
    } catch (error: unknown) {
      const msg = apiErrorDetail(error, 'Invalid credentials');
      toast({ title: 'Login failed', description: msg, variant: 'destructive' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleLogin} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="login-email">Email</Label>
        <Input
          id="login-email"
          type="email"
          value={loginData.email}
          onChange={(e) => setLoginData((d) => ({ ...d, email: e.target.value }))}
          placeholder="you@example.com"
          autoComplete="email"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="login-password">Password</Label>
        <Input
          id="login-password"
          type="password"
          value={loginData.password}
          onChange={(e) => setLoginData((d) => ({ ...d, password: e.target.value }))}
          placeholder="••••••••"
          autoComplete="current-password"
          required
        />
      </div>
      <Button type="submit" variant="secondary" className="w-full" disabled={isLoading}>
        {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" aria-hidden="true" />}
        Sign In
      </Button>
    </form>
  );
}

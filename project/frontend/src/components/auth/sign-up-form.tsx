'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

/** Account creation. Checks the passwords match before calling the API. */
export function SignUpForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [registerData, setRegisterData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    fullName: '',
  });

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();

    if (registerData.password !== registerData.confirmPassword) {
      toast({
        title: 'Error',
        description: 'Passwords do not match',
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);

    try {
      const res = await authApi.register(
        registerData.email,
        registerData.password,
        registerData.fullName
      );
      localStorage.setItem('token', res.data.access_token);
      toast({ title: 'Account created!' });
      router.push('/dashboard');
    } catch (error: unknown) {
      const msg = apiErrorDetail(error, 'Could not create account');
      toast({ title: 'Registration failed', description: msg, variant: 'destructive' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleRegister} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="register-name">Full Name</Label>
        <Input
          id="register-name"
          value={registerData.fullName}
          onChange={(e) => setRegisterData((d) => ({ ...d, fullName: e.target.value }))}
          placeholder="Jane Doe"
          autoComplete="name"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="register-email">Email</Label>
        <Input
          id="register-email"
          type="email"
          value={registerData.email}
          onChange={(e) => setRegisterData((d) => ({ ...d, email: e.target.value }))}
          placeholder="you@example.com"
          autoComplete="email"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="register-password">Password</Label>
        <Input
          id="register-password"
          type="password"
          value={registerData.password}
          onChange={(e) => setRegisterData((d) => ({ ...d, password: e.target.value }))}
          placeholder="••••••••"
          autoComplete="new-password"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="register-confirm">Confirm Password</Label>
        <Input
          id="register-confirm"
          type="password"
          value={registerData.confirmPassword}
          onChange={(e) => setRegisterData((d) => ({ ...d, confirmPassword: e.target.value }))}
          placeholder="••••••••"
          autoComplete="new-password"
          required
        />
      </div>
      <Button type="submit" variant="secondary" className="w-full" disabled={isLoading}>
        {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" aria-hidden="true" />}
        Create Account
      </Button>
    </form>
  );
}

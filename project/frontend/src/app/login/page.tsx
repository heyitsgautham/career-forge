'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { Github, Loader2, ChevronDown, Chrome } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [showEmail, setShowEmail] = useState(false);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [registerData, setRegisterData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    fullName: '',
  });

  /* Redirect if already authenticated */
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) router.replace('/dashboard');
  }, [router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const res = await authApi.login(loginData.email, loginData.password);
      localStorage.setItem('token', res.data.access_token);
      toast({ title: 'Welcome back!' });
      router.push('/dashboard');
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || 'Invalid credentials';
      toast({ title: 'Login failed', description: msg, variant: 'destructive' });
    } finally {
      setIsLoading(false);
    }
  };

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
      const msg =
        (error as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || 'Could not create account';
      toast({ title: 'Registration failed', description: msg, variant: 'destructive' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden bg-background">
      {/* Ambient background */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute left-1/2 top-1/4 -translate-x-1/2 h-[500px] w-[700px] rounded-full bg-primary/6 blur-[140px] animate-blob" />
        <div className="absolute right-0 bottom-0 h-[350px] w-[350px] rounded-full bg-[hsl(var(--accent))]/5 blur-[120px] animate-blob animation-delay-2000" />
        <div className="absolute left-0 top-0 h-[300px] w-[300px] rounded-full bg-[hsl(var(--success))]/4 blur-[100px] animate-blob animation-delay-4000" />
      </div>

      <div className="w-full max-w-md space-y-6 animate-fade-in-up">
        {/* Logo */}
        <div className="text-center">
          <Link
            href="/"
            className="group inline-flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-md"
          >
            <img src="/logo.svg" alt="CareerForge logo" className="h-12 w-12 rounded-full bg-white p-0.5 object-contain shadow-lg shadow-primary/25 transition-all duration-300 group-hover:shadow-xl group-hover:shadow-primary/30 group-hover:scale-105" />
            <span className="font-bold text-xl tracking-tight">CareerForge</span>
          </Link>
          <p className="mt-2 text-sm text-muted-foreground">
            Turn your GitHub into a job engine
          </p>
        </div>

        <Card className="border-border/40 shadow-xl shadow-primary/5 backdrop-blur-sm">
          <CardHeader className="text-center pb-2">
            <CardTitle className="text-lg">Get started</CardTitle>
            <CardDescription>
              Authenticate with GitHub to import repos &amp; build AI resumes
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {/* Primary CTA — GitHub OAuth */}
            <Button
              className="w-full gap-2.5 h-12 text-base font-medium shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/25"
              onClick={() => authApi.githubLogin()}
              aria-label="Continue with GitHub"
            >
              <Github className="h-5 w-5" aria-hidden="true" />
              Continue with GitHub
            </Button>

            {/* Google via Cognito */}
            <Button
              variant="outline"
              className="w-full gap-2.5 h-12 text-base font-medium"
              onClick={() => authApi.cognitoGoogleLogin()}
              aria-label="Continue with Google"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              Continue with Google
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              GitHub grants <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">repo</code> access for project import
            </p>

            {/* Collapsible email section */}
            <div>
              <button
                type="button"
                onClick={() => setShowEmail(!showEmail)}
                className="group flex w-full items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors py-2"
                aria-expanded={showEmail}
              >
                <span className="h-px flex-1 bg-border" />
                <span className="flex items-center gap-1">
                  Or use email
                  <ChevronDown
                    className={`h-3 w-3 transition-transform duration-200 ${showEmail ? 'rotate-180' : ''}`}
                    aria-hidden="true"
                  />
                </span>
                <span className="h-px flex-1 bg-border" />
              </button>

              {showEmail && (
                <div className="mt-2 animate-in fade-in-0 slide-in-from-top-2 duration-200">
                  <Tabs defaultValue="login" className="w-full">
                    <TabsList className="grid w-full grid-cols-2 mb-4">
                      <TabsTrigger value="login">Sign In</TabsTrigger>
                      <TabsTrigger value="register">Sign Up</TabsTrigger>
                    </TabsList>

                    <TabsContent value="login">
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
                    </TabsContent>

                    <TabsContent value="register">
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
                            onChange={(e) =>
                              setRegisterData((d) => ({ ...d, password: e.target.value }))
                            }
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
                            onChange={(e) =>
                              setRegisterData((d) => ({ ...d, confirmPassword: e.target.value }))
                            }
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
                    </TabsContent>
                  </Tabs>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}

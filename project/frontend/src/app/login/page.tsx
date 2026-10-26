'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Github, ChevronDown } from 'lucide-react';
import { GoogleIcon } from '@/components/auth/google-icon';
import { SignInForm } from '@/components/auth/sign-in-form';
import { SignUpForm } from '@/components/auth/sign-up-form';

export default function LoginPage() {
  const router = useRouter();
  const [showEmail, setShowEmail] = useState(false);

  /* Redirect if already authenticated */
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) router.replace('/dashboard');
  }, [router]);

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
            <img
              src="/logo.svg"
              alt="CareerForge logo"
              className="h-12 w-12 rounded-full bg-white p-0.5 object-contain shadow-lg shadow-primary/25 transition-all duration-300 group-hover:shadow-xl group-hover:shadow-primary/30 group-hover:scale-105"
            />
            <span className="font-bold text-xl tracking-tight">CareerForge</span>
          </Link>
          <p className="mt-2 text-sm text-muted-foreground">Turn your GitHub into a job engine</p>
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
              <GoogleIcon />
              Continue with Google
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              GitHub grants{' '}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">repo</code>{' '}
              access for project import
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
                      <SignInForm />
                    </TabsContent>

                    <TabsContent value="register">
                      <SignUpForm />
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

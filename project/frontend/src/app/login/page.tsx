'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { FileText, Github, Loader2 } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { toast } = useToast();
  
  const [isLoading, setIsLoading] = useState(false);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [registerData, setRegisterData] = useState({ 
    email: '', 
    password: '', 
    confirmPassword: '',
    fullName: '' 
  });

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const res = await authApi.login(loginData.email, loginData.password);
      localStorage.setItem('token', res.data.access_token);
      toast({ title: 'Welcome back!' });
      router.push('/dashboard');
    } catch (error: any) {
      toast({ 
        title: 'Login failed', 
        description: error.response?.data?.detail || 'Invalid credentials',
        variant: 'destructive'
      });
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
        variant: 'destructive'
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
    } catch (error: any) {
      toast({ 
        title: 'Registration failed', 
        description: error.response?.data?.detail || 'Could not create account',
        variant: 'destructive'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleGithubLogin = () => {
    // Redirect to GitHub OAuth
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID || 'Ov23li7PyDbHv0U1oqbZ';
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/$/, '');
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/github`);
    const scope = encodeURIComponent('read:user user:email repo');
    
    console.log('Redirecting to GitHub OAuth...');
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-blue-950 dark:to-purple-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2">
            <FileText className="h-8 w-8 text-blue-600" />
            <span className="font-bold text-xl bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">LaTeX Resume Agent</span>
          </Link>
        </div>

        <Card>
          <CardHeader className="text-center">
            <CardTitle>Welcome</CardTitle>
            <CardDescription>
              Sign in to manage your resumes and projects
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* GitHub OAuth */}
            <Button 
              variant="outline" 
              className="w-full mb-6 gap-2"
              onClick={handleGithubLogin}
            >
              <Github className="h-5 w-5" />
              Continue with GitHub
            </Button>

            <div className="relative mb-6">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">
                  Or continue with email
                </span>
              </div>
            </div>

            <Tabs defaultValue="login" className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-4">
                <TabsTrigger value="login">Sign In</TabsTrigger>
                <TabsTrigger value="register">Sign Up</TabsTrigger>
              </TabsList>
              
              <TabsContent value="login">
                <form onSubmit={handleLogin} className="space-y-4">
                  <div>
                    <Label htmlFor="login-email">Email</Label>
                    <Input 
                      id="login-email"
                      type="email"
                      value={loginData.email}
                      onChange={(e) => setLoginData(d => ({ ...d, email: e.target.value }))}
                      placeholder="you@example.com"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="login-password">Password</Label>
                    <Input 
                      id="login-password"
                      type="password"
                      value={loginData.password}
                      onChange={(e) => setLoginData(d => ({ ...d, password: e.target.value }))}
                      placeholder="••••••••"
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Sign In
                  </Button>
                </form>
              </TabsContent>
              
              <TabsContent value="register">
                <form onSubmit={handleRegister} className="space-y-4">
                  <div>
                    <Label htmlFor="register-name">Full Name</Label>
                    <Input 
                      id="register-name"
                      value={registerData.fullName}
                      onChange={(e) => setRegisterData(d => ({ ...d, fullName: e.target.value }))}
                      placeholder="John Doe"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="register-email">Email</Label>
                    <Input 
                      id="register-email"
                      type="email"
                      value={registerData.email}
                      onChange={(e) => setRegisterData(d => ({ ...d, email: e.target.value }))}
                      placeholder="you@example.com"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="register-password">Password</Label>
                    <Input 
                      id="register-password"
                      type="password"
                      value={registerData.password}
                      onChange={(e) => setRegisterData(d => ({ ...d, password: e.target.value }))}
                      placeholder="••••••••"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="register-confirm">Confirm Password</Label>
                    <Input 
                      id="register-confirm"
                      type="password"
                      value={registerData.confirmPassword}
                      onChange={(e) => setRegisterData(d => ({ ...d, confirmPassword: e.target.value }))}
                      placeholder="••••••••"
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Create Account
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground mt-4">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}

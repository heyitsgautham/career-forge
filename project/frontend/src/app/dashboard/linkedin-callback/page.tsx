'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useToast } from '@/hooks/use-toast';

export default function LinkedInCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      
      if (!code) {
        toast({
          title: 'Error',
          description: 'No authorization code received',
          variant: 'destructive',
        });
        router.push('/dashboard');
        return;
      }

      const token = localStorage.getItem('token');
      if (!token) {
        toast({
          title: 'Error',
          description: 'Not authenticated',
          variant: 'destructive',
        });
        router.push('/login');
        return;
      }

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/auth/linkedin/callback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ code }),
        });

        const data = await response.json();

        if (!response.ok) {
          toast({
            title: 'LinkedIn Connection Failed',
            description: data.detail || 'Failed to connect LinkedIn account',
            variant: 'destructive',
          });
        } else {
          toast({
            title: 'LinkedIn Connected!',
            description: 'You can now import certifications from LinkedIn',
          });
        }
      } catch (error) {
        toast({
          title: 'Error',
          description: 'Failed to process LinkedIn callback',
          variant: 'destructive',
        });
      }

      router.push('/dashboard');
    };

    handleCallback();
  }, [searchParams, router, toast]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-blue-950 dark:to-purple-950">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-muted-foreground">Connecting LinkedIn...</p>
      </div>
    </div>
  );
}

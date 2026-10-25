'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { resumesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Loader2, RefreshCw } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

// ─── Compile Button ─────────────────────────────────────────────────────────

export function CompileButton({ resumeId }: { resumeId: string }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const compileMutation = useMutation({
    mutationFn: () => resumesApi.compile(resumeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'PDF compiled successfully!' });
    },
    onError: (error: unknown) => {
      toast({
        title: 'Compilation failed',
        description: apiErrorDetail(error, 'Check LaTeX syntax'),
        variant: 'destructive',
      });
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
  });

  return (
    <Button
      size="sm"
      variant="outline"
      className="gap-1 h-8 text-xs"
      onClick={() => compileMutation.mutate()}
      disabled={compileMutation.isPending}
    >
      {compileMutation.isPending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <RefreshCw className="h-3 w-3" />
      )}
      Compile PDF
    </Button>
  );
}

import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { summarizeImport, type ImportResult } from './import-summary';
import type { ImportProgressItem } from './types';

/** Gap between revealing each repository's result, so cards flip one by one. */
export const REVEAL_STAGGER_MS = 650;
/** How often the fake progress moves to the next queued repository while the API works. */
export const SIMULATED_STEP_MS = 3000;

/**
 * Imports selected GitHub repositories and drives the progress banner and
 * skeleton cards. The import lives here, not in the modal, so its progress
 * survives the modal closing.
 */
export function useProjectImport() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [importProgress, setImportProgress] = useState<ImportProgressItem[]>([]);
  // Holds the visual simulation interval so it can be cancelled when real results arrive
  const simulationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopSimulation = () => {
    if (simulationIntervalRef.current) {
      clearInterval(simulationIntervalRef.current);
      simulationIntervalRef.current = null;
    }
  };
  useEffect(() => stopSimulation, []);

  const importMutation = useMutation({
    mutationFn: (fullNames: string[]) => projectsApi.importGithub(fullNames),
    onSuccess: (response) => {
      // Stop simulation — real results drive the state from here
      stopSimulation();

      queryClient.invalidateQueries({ queryKey: ['projects'] });
      const results: ImportResult[] = response.data?.results ?? [];

      // Reveal done/failed one by one so cards appear sequentially
      results.forEach((result, idx) => {
        setTimeout(() => {
          setImportProgress((prev) =>
            prev.map((repo) => {
              if (
                repo.fullName === result.full_name ||
                (!result.full_name &&
                  idx ===
                    prev.indexOf(prev.find((r) => r.status !== 'done' && r.status !== 'failed')!))
              ) {
                return { ...repo, status: result.status === 'success' ? 'done' : 'failed' };
              }
              return repo;
            })
          );
        }, idx * REVEAL_STAGGER_MS);
      });

      const allDoneDelay = results.length * REVEAL_STAGGER_MS;

      // Toast after the last card flips
      setTimeout(() => toast(summarizeImport(results)), allDoneDelay);

      // Clear skeleton cards after real cards have had time to load via polling
      setTimeout(() => setImportProgress([]), allDoneDelay + 3500);

      // Poll for 30s to catch delayed DB writes
      const pollId = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ['projects'] });
      }, 5000);
      setTimeout(() => clearInterval(pollId), 30_000);
    },
    onError: (error: unknown) => {
      stopSimulation();
      // Mark all as failed, then clear after a short delay
      setImportProgress((prev) => prev.map((repo) => ({ ...repo, status: 'failed' })));
      toast({
        title: 'Failed to import repositories',
        description: apiErrorDetail(
          error,
          error instanceof Error && error.message ? error.message : 'Unknown error'
        ),
        variant: 'destructive',
      });
      setTimeout(() => setImportProgress([]), 4000);
    },
  });

  const startImport = (fullNames: string[]) => {
    // Initialize — first repo immediately processing, rest queued
    setImportProgress(
      fullNames.map((fn, idx) => ({
        name: fn.split('/').pop() || fn,
        fullName: fn,
        status: idx === 0 ? 'processing' : 'queued',
      }))
    );
    importMutation.mutate(fullNames);

    // Advance the "processing" indicator along the queue while waiting for the API
    if (fullNames.length > 1) {
      let nextIdx = 1;
      simulationIntervalRef.current = setInterval(() => {
        if (nextIdx < fullNames.length) {
          // React may run the updater after this callback returns, so it must
          // not read nextIdx, which has moved on by then.
          const step = nextIdx;
          setImportProgress((prev) =>
            prev.map((item, i) =>
              i <= step && item.status === 'queued' ? { ...item, status: 'processing' } : item
            )
          );
          nextIdx++;
        } else {
          stopSimulation();
        }
      }, SIMULATED_STEP_MS);
    }
  };

  return { importProgress, startImport };
}

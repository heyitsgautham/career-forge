import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { githubApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import type { SyncSummary } from './types';

export const SYNC_POLL_MS = 3000;

/**
 * Runs "Sync Existing": starts a GitHub re-ingest, then polls its status every
 * three seconds until it finishes or fails, and refreshes the project list.
 */
export function useGithubSync() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string>('none');
  const [syncSummary, setSyncSummary] = useState<SyncSummary | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const res = await githubApi.getIngestStatus();
      const s = res.data.status as string;
      const summary = res.data.summary;
      setSyncStatus(s);
      setSyncSummary(summary);
      if (s === 'done' || s === 'completed') {
        stopPoll();
        setSyncing(false);
        queryClient.invalidateQueries({ queryKey: ['projects'] });
        const count = summary?.processed ?? 0;
        toast({
          title: 'Sync complete',
          description: `${count} existing project${count !== 1 ? 's' : ''} refreshed.`,
        });
      } else if (s === 'failed') {
        stopPoll();
        setSyncing(false);
        toast({
          title: 'Sync failed',
          description: 'Check your GitHub connection and try again.',
          variant: 'destructive',
        });
      }
    } catch {
      stopPoll();
      setSyncing(false);
    }
  }, [stopPoll, queryClient, toast]);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const startSync = async () => {
    setSyncing(true);
    try {
      await githubApi.sync(false);
    } catch {
      /* server already processing */
    }
    pollRef.current = setInterval(pollStatus, SYNC_POLL_MS);
    pollStatus();
  };

  return { syncing, syncStatus, syncSummary, startSync };
}

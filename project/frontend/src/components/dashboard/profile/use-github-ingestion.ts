import { useCallback, useEffect, useRef, useState } from 'react';
import { githubApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import type { IngestionSummary } from './types';

export const INGEST_POLL_MS = 3000;
export const MAX_POLLS = 40; // 40 × 3s = 2 minutes max

/**
 * The GitHub projects shown on the profile and the "refresh repos" import.
 * A refresh that the API runs as a background job is polled every three
 * seconds for up to two minutes. `onProfileStale` runs when an import may
 * have added skills, so the caller can reload the profile.
 */
export function useGithubIngestion(onProfileStale: () => Promise<void>) {
  const { toast } = useToast();
  const [ingesting, setIngesting] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<string>('none');
  const [ingestionSummary, setIngestionSummary] = useState<IngestionSummary | null>(null);
  const [projects, setProjects] = useState<Array<Record<string, unknown>>>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll ingestion status and load projects on mount
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      const res = await githubApi.listProjects();
      setProjects(res.data as Array<Record<string, unknown>>);
    } catch {
      /* ignore */
    }
  }, []);

  const pollCountRef = useRef(0);

  const pollIngestionStatus = useCallback(async () => {
    try {
      const res = await githubApi.getIngestStatus();
      const s = res.data.status;
      setIngestionStatus(s);
      setIngestionSummary(res.data.summary);

      if (s === 'done') {
        stopPolling();
        setIngesting(false);
        await loadProjects();
        // Reload profile so newly-added skills appear immediately
        await onProfileStale();
        toast({
          title: 'Import Complete',
          description: `${res.data.summary?.processed ?? 0} projects imported.`,
        });
      } else if (s === 'failed' || s === 'stale') {
        stopPolling();
        setIngesting(false);
        if (s === 'stale') {
          toast({
            title: 'Import Timed Out',
            description: 'The previous import did not complete. Please try again.',
            variant: 'destructive',
          });
        } else {
          toast({
            title: 'Import Failed',
            description: 'Check your GitHub connection and try again.',
            variant: 'destructive',
          });
        }
      } else {
        // Safety cap: stop polling after MAX_POLLS attempts
        pollCountRef.current += 1;
        if (pollCountRef.current >= MAX_POLLS) {
          stopPolling();
          setIngesting(false);
          toast({
            title: 'Import Timed Out',
            description: 'The import is taking too long. Please try again.',
            variant: 'destructive',
          });
        }
      }
    } catch {
      stopPolling();
      setIngesting(false);
    }
  }, [stopPolling, loadProjects, toast, onProfileStale]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollCountRef.current = 0;
    setIngesting(true);
    pollRef.current = setInterval(pollIngestionStatus, INGEST_POLL_MS);
    // Also poll immediately
    pollIngestionStatus();
  }, [stopPolling, pollIngestionStatus]);

  useEffect(() => {
    // On mount: only resume polling if a sync is actively running.
    // Never auto-trigger a new sync — user must click the button.
    (async () => {
      try {
        const res = await githubApi.getIngestStatus();
        const s = res.data.status;
        setIngestionStatus(s);
        setIngestionSummary(res.data.summary);
        if (s === 'in_progress') {
          startPolling();
        }
      } catch {
        /* ignore */
      }
      await loadProjects();
    })();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefreshRepos = async () => {
    setIngesting(true);
    try {
      await githubApi.ingest(false);
      // Ingest is synchronous — skills are already updated in DynamoDB.
      // Reload profile immediately so the skills field reflects the new data.
      await onProfileStale();
      await loadProjects();
      setIngesting(false);
      setIngestionStatus('done');
      toast({ title: 'Sync complete', description: 'Projects refreshed and skills updated.' });
    } catch {
      // Ingest may be running as a background job — fall back to polling.
      startPolling();
    }
  };

  return {
    projects,
    ingesting,
    ingestionStatus,
    ingestionSummary,
    refreshRepos: handleRefreshRepos,
  };
}

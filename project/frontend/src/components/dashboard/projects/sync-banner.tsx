'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Github, RefreshCw, Trash2 } from 'lucide-react';
import type { SyncSummary } from './types';

/** Sync status line with the "Sync Existing" and "Clear All" controls above the project grid. */
export function SyncBanner({
  syncing,
  syncStatus,
  syncSummary,
  onSyncAll,
  showClearAll,
  clearing,
  onClearAll,
}: {
  syncing: boolean;
  syncStatus: string;
  syncSummary: SyncSummary | null;
  onSyncAll: () => void;
  showClearAll: boolean;
  clearing: boolean;
  onClearAll: () => void;
}) {
  return (
    <Card className="mb-4 border-l-4 border-l-primary bg-card">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-2">
          <Github className="h-5 w-5 text-primary" />
          <span className="text-base font-semibold leading-none tracking-tight">GitHub Sync</span>
          {syncStatus === 'done' || syncStatus === 'completed' ? (
            <Badge className="bg-[hsl(var(--success))]/10 text-[hsl(var(--success))] border-0">
              {syncSummary ? `${syncSummary.processed} imported` : 'Synced'}
            </Badge>
          ) : syncStatus === 'in_progress' || syncStatus === 'pending' ? (
            <Badge className="bg-primary/10 text-primary border-0 animate-pulse">
              {syncStatus === 'pending' ? 'Pending…' : 'Importing…'}
            </Badge>
          ) : syncStatus === 'failed' ? (
            <Badge variant="destructive">Failed</Badge>
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={onSyncAll}
            disabled={syncing}
            variant="outline"
            className="gap-2 border-primary/40 text-primary hover:bg-primary/5"
          >
            {syncing ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Syncing…
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" />
                Sync Existing
              </>
            )}
          </Button>
          {showClearAll && (
            <Button
              size="sm"
              variant="outline"
              className="gap-2 border-destructive/40 text-destructive hover:bg-destructive/5"
              onClick={onClearAll}
              disabled={clearing}
            >
              <Trash2 className="h-4 w-4" />
              {clearing ? 'Clearing…' : 'Clear All'}
            </Button>
          )}
        </div>
      </div>
      {(syncStatus === 'in_progress' || syncStatus === 'pending') && (
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground animate-pulse">
            Refreshing existing projects via Bedrock — this takes ~1–2 min for large accounts.
          </p>
        </CardContent>
      )}
      {syncStatus === 'done' && syncSummary?.lastRunAt && (
        <CardContent className="pt-0">
          <p className="text-xs text-muted-foreground">
            Last synced {new Date(syncSummary.lastRunAt).toLocaleString()}
            {syncSummary.failed > 0 && ` · ${syncSummary.failed} failed`}
          </p>
        </CardContent>
      )}
    </Card>
  );
}

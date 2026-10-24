'use client';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Github, RefreshCw, X, Sparkles } from 'lucide-react';
import type { ImportProgressItem } from './types';

// ── Skeleton card shown in the grid while a repo is being imported ────────
export function ImportSkeletonCard({ item }: { item: ImportProgressItem }) {
  const isProcessing = item.status === 'processing';
  const isDone = item.status === 'done';
  const isFailed = item.status === 'failed';

  return (
    <Card
      className={`border-l-4 transition-all duration-500 ${
        isDone    ? 'border-l-[hsl(var(--success))]' :
        isFailed  ? 'border-l-destructive' :
        isProcessing ? 'border-l-destructive' :
                    'border-l-muted'
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Github className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <span className="font-medium text-sm truncate">{item.name}</span>
          </div>
          {isProcessing && <RefreshCw className="h-6 w-6 text-destructive animate-spin flex-shrink-0" />}
          {isDone && (
            <div className="h-3.5 w-3.5 rounded-full bg-[hsl(var(--success))] flex-shrink-0" />
          )}
          {isFailed && <X className="h-3.5 w-3.5 text-destructive flex-shrink-0" />}
          {item.status === 'queued' && (
            <div className="h-3.5 w-3.5 rounded-full border-2 border-muted-foreground/30 flex-shrink-0" />
          )}
        </div>
        {/* fake description lines */}
        <div className={`h-3 bg-muted rounded mt-2 ${isProcessing ? 'animate-pulse' : 'opacity-50'}`} style={{ width: '78%' }} />
        <div className={`h-3 bg-muted rounded mt-1 ${isProcessing ? 'animate-pulse' : 'opacity-50'}`} style={{ width: '52%' }} />
      </CardHeader>
      <CardContent className="pb-4">
        {/* fake tech badges */}
        <div className="flex gap-2 mb-3">
          {[64, 48, 56].map((w, i) => (
            <div
              key={i}
              className={`h-5 rounded bg-muted ${isProcessing ? 'animate-pulse' : 'opacity-50'}`}
              style={{ width: w }}
            />
          ))}
        </div>
        <p className={`text-xs font-medium ${
          isDone       ? 'text-[hsl(var(--success))]' :
          isFailed     ? 'text-destructive' :
          isProcessing ? 'text-destructive' :
                         'text-muted-foreground'
        }`}>
          {item.status === 'queued'     ? 'Waiting in queue…'    :
           item.status === 'processing' ? 'Analyzing with AI…'   :
           item.status === 'done'       ? 'Import complete ✓'    :
                                          'Import failed'}
        </p>
      </CardContent>
    </Card>
  );
}

// ── Compact non-blocking import progress banner (A4) ─────────────────────
export function ImportProgressBanner({ importProgress }: { importProgress: ImportProgressItem[] }) {
  const doneCount = importProgress.filter(r => r.status === 'done').length;
  const failedCount = importProgress.filter(r => r.status === 'failed').length;
  const processingCount = importProgress.filter(r => r.status === 'processing').length;
  const queuedCount = importProgress.filter(r => r.status === 'queued').length;
  
  const allDone = doneCount + failedCount === importProgress.length;
  const currentRepo = importProgress.find(r => r.status === 'processing');

  return (
    <Card className={`mb-4 border-l-4 ${allDone ? (failedCount > 0 ? 'border-l-destructive' : 'border-l-[hsl(var(--success))]') : 'border-l-destructive'} bg-card`}>
      <CardContent className="py-3 px-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {allDone ? (
              failedCount > 0 ? (
                <div className="h-8 w-8 rounded-lg bg-destructive/10 flex items-center justify-center">
                  <X className="h-4 w-4 text-destructive" />
                </div>
              ) : (
                <div className="h-8 w-8 rounded-lg bg-[hsl(var(--success))]/10 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-[hsl(var(--success))]" />
                </div>
              )
            ) : (
              <div className="h-8 w-8 rounded-lg bg-destructive/10 flex items-center justify-center">
                <RefreshCw className="h-5 w-5 text-destructive animate-spin" />
              </div>
            )}
            <div>
              <p className="text-sm font-medium">
                {allDone 
                  ? (failedCount > 0 
                    ? `Import completed with ${failedCount} failure${failedCount !== 1 ? 's' : ''}`
                    : `Successfully imported ${doneCount} project${doneCount !== 1 ? 's' : ''}`)
                  : `Importing ${importProgress.length} repositor${importProgress.length !== 1 ? 'ies' : 'y'}…`
                }
              </p>
              <p className="text-xs text-muted-foreground">
                {allDone 
                  ? `${doneCount} succeeded${failedCount > 0 ? `, ${failedCount} failed` : ''}`
                  : currentRepo 
                    ? `Analyzing ${currentRepo.name}…`
                    : `${processingCount} processing, ${queuedCount} queued`
                }
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Progress indicators */}
            <div className="flex gap-1">
              {importProgress.map((item) => (
                <div
                  key={item.fullName}
                  className={`h-2 w-2 rounded-full transition-colors ${
                    item.status === 'done' ? 'bg-[hsl(var(--success))]' :
                    item.status === 'failed' ? 'bg-destructive' :
                    item.status === 'processing' ? 'bg-destructive animate-pulse' :
                    'bg-muted'
                  }`}
                  title={`${item.name}: ${item.status}`}
                />
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

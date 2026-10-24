'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Github, RefreshCw, X, Code2, Sparkles, GitBranch, FileCode } from 'lucide-react';
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

// ── Creative import loading overlay with per-repo progress ─────────────
export const LOADING_PHRASES = [
  'Cloning repository data...',
  'Scanning source files...',
  'Analyzing code architecture...',
  'Extracting tech stack...',
  'Generating AI summaries...',
  'Building project highlights...',
  'Crafting project cards...',
  'Almost there...',
];

export function ImportLoadingOverlay({ importProgress }: { importProgress: ImportProgressItem[] }) {
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [visibleRepos, setVisibleRepos] = useState(0);

  useEffect(() => {
    const phraseTimer = setInterval(() => {
      setPhraseIdx(prev => (prev + 1) % LOADING_PHRASES.length);
    }, 3000);
    return () => clearInterval(phraseTimer);
  }, []);

  useEffect(() => {
    if (visibleRepos < importProgress.length) {
      const timer = setTimeout(() => setVisibleRepos(prev => prev + 1), 400);
      return () => clearTimeout(timer);
    }
  }, [visibleRepos, importProgress.length]);

  const doneCount = importProgress.filter(r => r.status === 'done').length;
  const failedCount = importProgress.filter(r => r.status === 'failed').length;
  const processingCount = importProgress.filter(r => r.status === 'processing').length;

  const getStatusInfo = (status: ImportProgressItem['status']) => {
    switch (status) {
      case 'done':
        return { text: 'Done!', color: 'text-[hsl(var(--success))]', bgColor: 'bg-[hsl(var(--success))]/10' };
      case 'failed':
        return { text: 'Failed', color: 'text-destructive', bgColor: 'bg-destructive/10' };
      case 'processing':
        return { text: 'Analyzing...', color: 'text-primary animate-pulse', bgColor: 'bg-primary/10' };
      case 'queued':
      default:
        return { text: 'Queued', color: 'text-muted-foreground', bgColor: 'bg-muted' };
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      {/* Animated orbital spinner */}
      <div className="relative w-32 h-32 mb-8">
        {/* Outer ring */}
        <div className="absolute inset-0 rounded-full border-2 border-violet-200 dark:border-violet-900" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-500 animate-spin" style={{ animationDuration: '2s' }} />
        {/* Middle ring */}
        <div className="absolute inset-3 rounded-full border-2 border-transparent border-b-purple-500 animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
        {/* Inner ring */}
        <div className="absolute inset-6 rounded-full border-2 border-transparent border-t-blue-500 animate-spin" style={{ animationDuration: '1s' }} />
        {/* Center icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 bg-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/30 animate-pulse">
            <Code2 className="h-6 w-6 text-white" />
          </div>
        </div>
      </div>

      {/* Title */}
      <h3 className="text-xl font-bold text-violet-600 mb-2">
        Importing {importProgress.length} {importProgress.length === 1 ? 'Repository' : 'Repositories'}
      </h3>

      {/* Progress summary */}
      <div className="flex gap-3 mb-4 text-xs">
        {processingCount > 0 && (
          <span className="text-primary">{processingCount} processing</span>
        )}
        {doneCount > 0 && (
          <span className="text-[hsl(var(--success))]">{doneCount} done</span>
        )}
        {failedCount > 0 && (
          <span className="text-destructive">{failedCount} failed</span>
        )}
      </div>

      {/* Animated status text */}
      <p className="text-sm text-muted-foreground mb-8 h-5 transition-opacity duration-500">
        {LOADING_PHRASES[phraseIdx]}
      </p>

      {/* Repo cards with progress status */}
      <div className="w-full max-w-lg space-y-3">
        {importProgress.slice(0, visibleRepos).map((item, idx) => {
          const statusInfo = getStatusInfo(item.status);
          return (
            <div
              key={item.fullName}
              className={`flex items-center gap-3 p-3 rounded-lg border bg-card animate-in slide-in-from-bottom-2 fade-in duration-500 ${
                item.status === 'done' ? 'border-[hsl(var(--success))]/30' :
                item.status === 'failed' ? 'border-destructive/30' :
                item.status === 'processing' ? 'border-primary/30' : ''
              }`}
              style={{ animationDelay: `${idx * 100}ms` }}
            >
              <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${statusInfo.bgColor}`}>
                {item.status === 'done' ? (
                  <Sparkles className="h-4 w-4 text-[hsl(var(--success))]" />
                ) : item.status === 'failed' ? (
                  <X className="h-4 w-4 text-destructive" />
                ) : item.status === 'processing' ? (
                  <RefreshCw className="h-4 w-4 text-primary animate-spin" />
                ) : idx % 3 === 0 ? (
                  <GitBranch className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                ) : idx % 3 === 1 ? (
                  <FileCode className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                ) : (
                  <Code2 className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{item.name}</p>
                <div className="flex gap-2 mt-1 items-center">
                  {item.status === 'processing' ? (
                    <>
                      <div className="h-2 bg-muted rounded-full overflow-hidden flex-1 max-w-[180px]">
                        <div
                          className="h-full bg-violet-600 rounded-full animate-pulse"
                          style={{ width: '100%', animationDuration: '1.5s' }}
                        />
                      </div>
                      <span className={`text-[10px] whitespace-nowrap ${statusInfo.color}`}>{statusInfo.text}</span>
                    </>
                  ) : (
                    <span className={`text-[10px] whitespace-nowrap ${statusInfo.color}`}>{statusInfo.text}</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Ghost cards for repos not yet shown */}
        {visibleRepos < importProgress.length && (
          <div className="flex items-center gap-3 p-3 rounded-lg border border-dashed bg-muted/30 animate-pulse">
            <div className="w-8 h-8 rounded-lg bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-3 bg-muted rounded w-32" />
              <div className="h-2 bg-muted rounded w-24" />
            </div>
          </div>
        )}
      </div>

      <p className="text-xs text-muted-foreground mt-6 text-center max-w-md">
        Each repository is analyzed by AI to extract technologies, highlights, and project details. This may take a moment.
      </p>
    </div>
  );
}

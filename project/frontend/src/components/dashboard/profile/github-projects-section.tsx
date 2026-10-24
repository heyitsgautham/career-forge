'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { IngestionSummary } from './types';

/** Imported GitHub projects with the repo refresh control and ingestion status. */
export function GithubProjectsSection({
  projects,
  ingesting,
  ingestionStatus,
  ingestionSummary,
  onRefresh,
}: {
  projects: Array<Record<string, unknown>>;
  ingesting: boolean;
  ingestionStatus: string;
  ingestionSummary: IngestionSummary | null;
  onRefresh: () => void;
}) {
  return (
    <>
      {/* GitHub Projects */}
      <Card className="border-l-4 border-l-green-500">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                GitHub Projects
              </CardTitle>
              <CardDescription>Import and sync your GitHub repositories</CardDescription>
            </div>
            <Button
              onClick={onRefresh}
              disabled={ingesting}
              className="bg-green-600 hover:bg-green-700"
            >
              {ingesting ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-2 h-4 w-4"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Importing…
                </>
              ) : (
                'Refresh Repos'
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Status region */}
          <div aria-live="polite" className="mb-4">
            {ingestionStatus === 'in_progress' && (
              <p className="text-sm text-primary animate-pulse">
                Importing repositories… This may take a minute.
              </p>
            )}
            {ingestionStatus === 'pending' && (
              <p className="text-sm text-[hsl(var(--accent))] animate-pulse">
                Initial import pending…
              </p>
            )}
            {ingestionStatus === 'done' && ingestionSummary && (
              <p className="text-sm text-[hsl(var(--success))]">
                {ingestionSummary.processed} projects imported
                {ingestionSummary.failed > 0 && ` (${ingestionSummary.failed} failed)`}
                {ingestionSummary.lastRunAt &&
                  ` — last run ${new Date(ingestionSummary.lastRunAt).toLocaleString()}`}
              </p>
            )}
            {ingestionStatus === 'failed' && (
              <p className="text-sm text-destructive">
                Import failed. Check your GitHub connection and try again.
              </p>
            )}
          </div>

          {/* Project list */}
          {projects.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p className="text-sm">
                No projects imported yet. Click &quot;Refresh Repos&quot; to import your GitHub
                repositories.
              </p>
            </div>
          ) : (
            <div className="grid gap-3">
              {projects.map((proj) => (
                <div
                  key={String(proj.projectId)}
                  className="p-3 border rounded-lg flex justify-between items-start bg-card hover:bg-accent/50 transition-colors"
                >
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{String(proj.name)}</span>
                      {Number(proj.stars) > 0 && (
                        <span className="text-xs text-[hsl(var(--accent))]">
                          ★ {String(proj.stars)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-1">
                      {String(proj.oneLiner || proj.description || '')}
                    </p>
                    {Array.isArray(proj.technologies) && proj.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(proj.technologies as string[]).slice(0, 6).map((tech) => (
                          <span key={tech} className="text-xs px-1.5 py-0.5 bg-muted rounded">
                            {tech}
                          </span>
                        ))}
                        {(proj.technologies as string[]).length > 6 && (
                          <span className="text-xs text-muted-foreground">
                            +{(proj.technologies as string[]).length - 6} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  {Boolean(proj.repoUrl) && (
                    <a
                      href={String(proj.repoUrl)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground ml-2 shrink-0"
                    >
                      View ↗
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

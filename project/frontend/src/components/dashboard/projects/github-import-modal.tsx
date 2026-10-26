'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Github, RefreshCw, X } from 'lucide-react';
import { apiErrorDetail } from '@/lib/api-error';
import { Portal } from '@/components/ui/portal';
import { RepoOption } from './repo-option';
import { VisibilityFilter } from './visibility-filter';
import { filterRepos, parseGithubRepoUrl, type GithubRepo, type Visibility } from './github-repos';

export function GithubImportModal({
  onClose,
  onStartImport,
  importedRepoNames,
  projectsLoading = false,
}: {
  onClose: () => void;
  onStartImport: (fullNames: string[]) => void;
  importedRepoNames: Set<string>;
  projectsLoading?: boolean;
}) {
  const [repoUrl, setRepoUrl] = useState('');
  const [selectedRepos, setSelectedRepos] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [importMode, setImportMode] = useState<'select' | 'url'>('select');
  const [visibilityFilter, setVisibilityFilter] = useState<Visibility>('all');

  // Fetch user's GitHub repositories
  const {
    data: userRepos,
    isLoading: loadingRepos,
    error: reposError,
  } = useQuery({
    queryKey: ['github-user-repos'],
    queryFn: async () => {
      const res = await projectsApi.listGithubUserRepos();
      return res.data as GithubRepo[];
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 min
    gcTime: 30 * 60 * 1000, // 30 min
  });

  const filteredRepos = userRepos && filterRepos(userRepos, searchQuery, visibilityFilter);

  // Compute visibility counts from full userRepos list
  const publicCount = userRepos?.filter((r) => !r.is_private).length ?? 0;
  const privateCount = userRepos?.filter((r) => r.is_private).length ?? 0;

  const isAlreadyImported = (repo: { name: string }) => importedRepoNames.has(repo.name);

  const toggleRepo = (fullName: string) => {
    setSelectedRepos((prev) => {
      const next = new Set(prev);
      if (next.has(fullName)) {
        next.delete(fullName);
      } else {
        next.add(fullName);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (!filteredRepos) return;
    const selectableRepos = filteredRepos.filter((r) => !isAlreadyImported(r));
    const allFilteredSelected = selectableRepos.every((r) => selectedRepos.has(r.full_name));
    if (allFilteredSelected) {
      setSelectedRepos((prev) => {
        const next = new Set(prev);
        selectableRepos.forEach((r) => next.delete(r.full_name));
        return next;
      });
    } else {
      setSelectedRepos((prev) => {
        const next = new Set(prev);
        selectableRepos.forEach((r) => next.add(r.full_name));
        return next;
      });
    }
  };

  const handleImport = () => {
    if (importMode === 'select') {
      if (selectedRepos.size === 0) return;
      onStartImport(Array.from(selectedRepos));
    } else {
      const fullName = parseGithubRepoUrl(repoUrl);
      if (!fullName) return;
      onStartImport([fullName]);
    }
  };

  const selectableFilteredRepos = filteredRepos?.filter((r) => !isAlreadyImported(r));
  const allFilteredSelected =
    selectableFilteredRepos &&
    selectableFilteredRepos.length > 0 &&
    selectableFilteredRepos.every((r) => selectedRepos.has(r.full_name));

  return (
    <Portal>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-fade-in-up">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">Import from GitHub</h2>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-4">
            {/* Import Mode Tabs */}
            <div className="flex gap-2 mb-4">
              <Button
                variant={importMode === 'select' ? 'default' : 'outline'}
                onClick={() => setImportMode('select')}
                className="flex-1"
              >
                Select from Your Repos
              </Button>
              <Button
                variant={importMode === 'url' ? 'default' : 'outline'}
                onClick={() => setImportMode('url')}
                className="flex-1"
              >
                Import by URL
              </Button>
            </div>

            {importMode === 'select' ? (
              <>
                {loadingRepos ? (
                  <div className="text-center py-8">
                    <RefreshCw className="h-8 w-8 mx-auto animate-spin text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">Loading your repositories...</p>
                  </div>
                ) : reposError ? (
                  <div className="text-center py-8">
                    <Github className="h-12 w-12 mx-auto text-red-500 mb-2" />
                    <p className="text-sm font-semibold text-red-600 dark:text-red-400 mb-1">
                      Failed to load repositories
                    </p>
                    <p className="text-xs text-muted-foreground mb-3">
                      {apiErrorDetail(
                        reposError,
                        'No GitHub account connected or connection expired'
                      )}
                    </p>
                    <Button variant="outline" size="sm" onClick={() => setImportMode('url')}>
                      Switch to URL Import
                    </Button>
                  </div>
                ) : userRepos && userRepos.length > 0 ? (
                  <>
                    <div>
                      <Label htmlFor="repoSearch">Search Repositories</Label>
                      <Input
                        id="repoSearch"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search by name, description, or language..."
                        className="mt-1"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        {filteredRepos?.length} of {userRepos.length} repositories
                        {selectedRepos.size > 0 && (
                          <span className="ml-2 font-medium text-violet-600 dark:text-violet-400">
                            · {selectedRepos.size} selected
                          </span>
                        )}
                      </p>
                    </div>

                    <VisibilityFilter
                      value={visibilityFilter}
                      onChange={setVisibilityFilter}
                      counts={{ all: userRepos.length, public: publicCount, private: privateCount }}
                    />

                    {/* Projects loading warning banner (A2) */}
                    {projectsLoading && (
                      <div className="flex items-center gap-2 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                        <RefreshCw className="h-3 w-3 animate-spin" />
                        Loading your imported projects…
                      </div>
                    )}

                    {/* Select All / Deselect All */}
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={toggleAll} className="text-xs">
                        {allFilteredSelected ? 'Deselect All' : 'Select All'}
                      </Button>
                      {selectedRepos.size > 0 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedRepos(new Set())}
                          className="text-xs text-muted-foreground"
                        >
                          Clear Selection
                        </Button>
                      )}
                    </div>

                    {/* Repo List with Checkboxes */}
                    <div className="border rounded-lg max-h-72 overflow-y-auto divide-y">
                      {filteredRepos?.map((repo) => {
                        const imported = isAlreadyImported(repo);
                        return (
                          <RepoOption
                            key={repo.full_name}
                            repo={repo}
                            imported={imported}
                            isSelected={!imported && selectedRepos.has(repo.full_name)}
                            onToggle={() => toggleRepo(repo.full_name)}
                          />
                        );
                      })}
                    </div>

                    <p className="text-sm text-muted-foreground">
                      💡 Select one or more repositories to import. We&apos;ll analyze each to
                      extract project details via AI.
                    </p>
                  </>
                ) : (
                  <div className="text-center py-8">
                    <Github className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No repositories found. Make sure your GitHub account is connected.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
                <div>
                  <Label htmlFor="repoUrl">GitHub Repository URL</Label>
                  <Input
                    id="repoUrl"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/username/repository"
                  />
                </div>

                <p className="text-sm text-muted-foreground">
                  Enter any GitHub repository URL to import it as a project.
                </p>
              </>
            )}

            <div className="flex gap-2 justify-end pt-4">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                onClick={handleImport}
                disabled={
                  (importMode === 'url' && !parseGithubRepoUrl(repoUrl)) ||
                  (importMode === 'select' && selectedRepos.size === 0)
                }
              >
                {importMode === 'select' && selectedRepos.size > 1
                  ? `Import ${selectedRepos.size} Repositories`
                  : 'Import Repository'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Portal>
  );
}

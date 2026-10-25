'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Github, Plus } from 'lucide-react';
import { ProjectDetailsModal } from './projects/project-details-modal';
import { AddProjectModal } from './projects/add-project-modal';
import { GithubImportModal } from './projects/github-import-modal';
import { ImportSkeletonCard, ImportProgressBanner } from './projects/import-progress';
import type { Project } from './projects/types';
import { SyncBanner } from './projects/sync-banner';
import { ProjectCard } from './projects/project-card';
import { ClearAllDialog } from './projects/clear-all-dialog';
import { ImportGithubButton } from './projects/import-github-button';
import { ProjectGridSkeleton } from './projects/project-grid-skeleton';
import { useGithubSync } from './projects/use-github-sync';
import { useProjectImport } from './projects/use-project-import';
import { useProjectDeletes } from './projects/use-project-deletes';

export function ProjectsList() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const { syncing, syncStatus, syncSummary, startSync } = useGithubSync();
  const { importProgress, startImport } = useProjectImport();
  const { deleteProject, clearAll, clearing } = useProjectDeletes();

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await projectsApi.list();
      return res.data as Project[];
    },
    staleTime: 5 * 60 * 1000, // 5 min
    gcTime: 30 * 60 * 1000, // 30 min
  });

  // Fetch GitHub repos count for the badge
  const { data: githubReposCount } = useQuery({
    queryKey: ['github-repos-count'],
    queryFn: async () => {
      try {
        const res = await projectsApi.listGithubUserRepos();
        return (res.data as unknown[]).length;
      } catch {
        return 0;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 min
    gcTime: 30 * 60 * 1000, // 30 min
    retry: false,
  });

  const handleStartImport = (fullNames: string[]) => {
    setShowGithubModal(false);
    startImport(fullNames);
  };

  const banners = (
    <>
      <SyncBanner
        syncing={syncing}
        syncStatus={syncStatus}
        syncSummary={syncSummary}
        onSyncAll={startSync}
        showClearAll={Boolean(mounted && projects && projects.length > 0)}
        clearing={clearing}
        onClearAll={() => setShowClearConfirm(true)}
      />
      {importProgress.length > 0 && <ImportProgressBanner importProgress={importProgress} />}
    </>
  );

  const modals = (
    <>
      {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} />}
      {showGithubModal && (
        <GithubImportModal
          onClose={() => setShowGithubModal(false)}
          onStartImport={handleStartImport}
          importedRepoNames={new Set((projects ?? []).map((p) => p.title))}
          projectsLoading={isLoading}
        />
      )}
    </>
  );

  if (isLoading) {
    return (
      <>
        {banners}
        <ProjectGridSkeleton />
      </>
    );
  }

  // If an import is actively running, skip the empty state and fall through to the grid
  // so skeleton cards are visible even before the first real project lands.
  if ((!projects || projects.length === 0) && importProgress.length === 0) {
    return (
      <>
        {banners}
        <Card className="text-center py-12">
          <CardContent>
            <Github className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
            <p className="text-muted-foreground mb-4">
              Sync your GitHub repos above, or import/add projects below.
            </p>
            <div className="flex gap-2 justify-center">
              <ImportGithubButton
                repoCount={githubReposCount}
                className="gap-2"
                onClick={() => setShowGithubModal(true)}
              />
              <Button onClick={() => setShowAddModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Manually
              </Button>
            </div>
          </CardContent>
        </Card>
        {modals}
      </>
    );
  }

  return (
    <>
      {banners}
      <div className="flex justify-end gap-2 mb-4">
        <ImportGithubButton
          repoCount={githubReposCount}
          className="gap-2 border-primary/30 hover:bg-primary/5"
          onClick={() => setShowGithubModal(true)}
        />
        <Button
          onClick={() => setShowAddModal(true)}
          className="shadow-md shadow-primary/20 hover:shadow-lg"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Project
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Skeleton placeholder cards for in-flight imports */}
        {importProgress.map((item) => (
          <ImportSkeletonCard key={`skeleton-${item.fullName}`} item={item} />
        ))}
        {(projects ?? []).map((project) => (
          <ProjectCard
            key={project.id}
            project={project}
            onShowDetails={() => setSelectedProject(project)}
            onDelete={() => deleteProject(project.id)}
          />
        ))}
      </div>

      {modals}
      {selectedProject && (
        <ProjectDetailsModal project={selectedProject} onClose={() => setSelectedProject(null)} />
      )}
      {showClearConfirm && (
        <ClearAllDialog
          count={projects?.length ?? 0}
          onCancel={() => setShowClearConfirm(false)}
          onConfirm={() => {
            clearAll();
            setShowClearConfirm(false);
          }}
        />
      )}
    </>
  );
}

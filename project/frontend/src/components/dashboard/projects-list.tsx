'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { Github, ExternalLink, RefreshCw, Trash2, Calendar, Plus, X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface Project {
  id: string;
  title: string;
  description: string;
  technologies: string[];
  url?: string;
  highlights: string[];
  start_date?: string;
  end_date?: string;
  created_at: string;
}

export function ProjectsList() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: projects, isLoading, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await projectsApi.list();
      return res.data as Project[];
    },
  });

  // Fetch GitHub repos count for the badge
  const { data: githubReposCount } = useQuery({
    queryKey: ['github-repos-count'],
    queryFn: async () => {
      try {
        const res = await projectsApi.listGithubUserRepos();
        return (res.data as any[]).length;
      } catch {
        return 0;
      }
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast({ title: 'Project deleted successfully' });
    },
    onError: () => {
      toast({ title: 'Failed to delete project', variant: 'destructive' });
    },
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-6 bg-muted rounded w-3/4"></div>
              <div className="h-4 bg-muted rounded w-full mt-2"></div>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <div className="h-5 bg-muted rounded w-16"></div>
                <div className="h-5 bg-muted rounded w-16"></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!projects || projects.length === 0) {
    return (
      <>
        <Card className="text-center py-12">
          <CardContent>
            <Github className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
            <p className="text-muted-foreground mb-4">
              Import projects from GitHub or add them manually to get started.
            </p>
            <div className="flex gap-2 justify-center">
              <Button variant="outline" className="gap-2" onClick={() => setShowGithubModal(true)}>
                <Github className="h-4 w-4" />
                Import from GitHub
                {githubReposCount !== undefined && githubReposCount > 0 && (
                  <Badge variant="secondary" className="ml-1 bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                    {githubReposCount}
                  </Badge>
                )}
              </Button>
              <Button onClick={() => setShowAddModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Manually
              </Button>
            </div>
          </CardContent>
        </Card>
        
        {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} />}
        {showGithubModal && <GithubImportModal onClose={() => setShowGithubModal(false)} />}
      </>
    );
  }

  return (
    <>
      <div className="flex justify-end gap-2 mb-4">
        <Button variant="outline" className="gap-2 border-purple-300 dark:border-purple-700 hover:bg-purple-50 dark:hover:bg-purple-950" onClick={() => setShowGithubModal(true)}>
          <Github className="h-4 w-4" />
          Import from GitHub
          {githubReposCount !== undefined && githubReposCount > 0 && (
            <Badge variant="secondary" className="ml-1 bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
              {githubReposCount}
            </Badge>
          )}
        </Button>
        <Button onClick={() => setShowAddModal(true)} className="bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 shadow-lg">
          <Plus className="h-4 w-4 mr-2" />
          Add Project
        </Button>
      </div>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Card key={project.id} className="hover:shadow-lg hover:shadow-green-200 dark:hover:shadow-green-900 transition-all hover:scale-105 border-l-4 border-l-green-400">
            <CardHeader>
              <div className="flex justify-between items-start">
                <CardTitle className="text-lg">{project.title}</CardTitle>
                <div className="flex gap-1">
                  {project.url && (
                    <Button variant="ghost" size="icon" asChild>
                      <a href={project.url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
              <CardDescription className="line-clamp-2">
                {project.description}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1 mb-4">
                {project.technologies?.slice(0, 5).map((tech, idx) => (
                  <Badge key={tech} variant="secondary" className={`text-xs ${
                    idx % 3 === 0 ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200' :
                    idx % 3 === 1 ? 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200' :
                    'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200'
                  }`}>
                    {tech}
                  </Badge>
                ))}
                {project.technologies?.length > 5 && (
                  <Badge variant="outline" className="text-xs">
                    +{project.technologies.length - 5}
                  </Badge>
                )}
              </div>
              {project.start_date && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  {project.start_date} - {project.end_date || 'Present'}
                </div>
              )}
              <div className="flex justify-between gap-2 mt-4">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setSelectedProject(project)}
                >
                  Show Details
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="text-destructive"
                  onClick={() => deleteMutation.mutate(project.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      
      {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} />}
      {showGithubModal && <GithubImportModal onClose={() => setShowGithubModal(false)} />}
      {selectedProject && <ProjectDetailsModal project={selectedProject} onClose={() => setSelectedProject(null)} />}
    </>
  );
}

function ProjectDetailsModal({ project, onClose }: { project: Project; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{project.title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="space-y-4">
          {/* Description */}
          <div>
            <h3 className="font-semibold text-sm text-muted-foreground mb-1">Description</h3>
            <p className="text-sm">{project.description}</p>
          </div>
          
          {/* Technologies */}
          {project.technologies && project.technologies.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Technologies</h3>
              <div className="flex flex-wrap gap-2">
                {project.technologies.map((tech) => (
                  <Badge key={tech} variant="secondary">
                    {tech}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          {/* Highlights */}
          {project.highlights && project.highlights.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Key Highlights</h3>
              <ul className="list-disc list-inside space-y-1">
                {project.highlights.map((highlight, idx) => (
                  <li key={idx} className="text-sm">{highlight}</li>
                ))}
              </ul>
            </div>
          )}
          
          {/* URL */}
          {project.url && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-1">Project URL</h3>
              <a 
                href={project.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                {project.url}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
          
          {/* Dates */}
          {project.start_date && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-1">Timeline</h3>
              <p className="text-sm">
                {project.start_date} - {project.end_date || 'Present'}
              </p>
            </div>
          )}
          
          <div className="flex justify-end pt-4">
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AddProjectModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [technologies, setTechnologies] = useState('');
  const [highlights, setHighlights] = useState('');
  const [url, setUrl] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () => projectsApi.create({
      title,
      description,
      technologies: technologies.split(',').map(t => t.trim()).filter(Boolean),
      highlights: highlights.split('\n').map(h => h.trim()).filter(Boolean),
      url: url || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast({ title: 'Project created successfully' });
      onClose();
    },
    onError: (error: any) => {
      toast({ 
        title: 'Failed to create project', 
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Add Project</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="space-y-4">
          <div>
            <Label htmlFor="title">Project Title *</Label>
            <Input 
              id="title" 
              value={title} 
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My Awesome Project"
            />
          </div>
          
          <div>
            <Label htmlFor="description">Description *</Label>
            <Textarea 
              id="description" 
              value={description} 
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this project do?"
              rows={3}
            />
          </div>
          
          <div>
            <Label htmlFor="technologies">Technologies (comma-separated)</Label>
            <Input 
              id="technologies" 
              value={technologies} 
              onChange={(e) => setTechnologies(e.target.value)}
              placeholder="Python, FastAPI, React"
            />
          </div>
          
          <div>
            <Label htmlFor="highlights">Key Highlights (optional - auto-generated if empty)</Label>
            <Textarea 
              id="highlights" 
              value={highlights} 
              onChange={(e) => setHighlights(e.target.value)}
              placeholder="Leave empty to auto-generate 3 technical highlights using AI"
              rows={3}
            />
            <p className="text-xs text-muted-foreground mt-1">
              💡 Leave empty and we'll generate 3 technical bullet points automatically
            </p>
          </div>
          
          <div>
            <Label htmlFor="url">Project URL (optional)</Label>
            <Input 
              id="url" 
              value={url} 
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/..."
            />
          </div>
          
          <div className="flex gap-2 justify-end pt-4">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button 
              onClick={() => createMutation.mutate()}
              disabled={!title || !description || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function GithubImportModal({ onClose }: { onClose: () => void }) {
  const [repoUrl, setRepoUrl] = useState('');
  const [selectedRepo, setSelectedRepo] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [importMode, setImportMode] = useState<'url' | 'dropdown'>('dropdown');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch user's GitHub repositories
  const { data: userRepos, isLoading: loadingRepos, error: reposError } = useQuery({
    queryKey: ['github-user-repos'],
    queryFn: async () => {
      const res = await projectsApi.listGithubUserRepos();
      return res.data as Array<{
        full_name: string;
        name: string;
        description?: string;
        html_url: string;
        stars: number;
        forks: number;
        language?: string;
        is_private: boolean;
        is_fork: boolean;
      }>;
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Filter repos based on search query
  const filteredRepos = userRepos?.filter(repo => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      repo.full_name.toLowerCase().includes(query) ||
      repo.name.toLowerCase().includes(query) ||
      repo.description?.toLowerCase().includes(query) ||
      repo.language?.toLowerCase().includes(query)
    );
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      let url = importMode === 'url' ? repoUrl : selectedRepo;
      
      // Parse GitHub URL
      const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)/);
      if (!match) {
        throw new Error('Invalid GitHub URL');
      }
      const [, owner, repo] = match;
      return projectsApi.importGithub(owner, repo.replace('.git', ''));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast({ title: 'Repository imported successfully' });
      onClose();
    },
    onError: (error: any) => {
      toast({ 
        title: 'Failed to import repository', 
        description: error.response?.data?.detail || error.message || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
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
              variant={importMode === 'dropdown' ? 'default' : 'outline'}
              onClick={() => setImportMode('dropdown')}
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

          {importMode === 'dropdown' ? (
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
                    {(reposError as any)?.response?.data?.detail || 'No GitHub account connected or connection expired'}
                  </p>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setImportMode('url')}
                  >
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
                    </p>
                  </div>
                  
                  <div>
                    <Label htmlFor="repoSelect">Select Repository</Label>
                    <Select
                      id="repoSelect"
                      value={selectedRepo}
                      onChange={(e) => setSelectedRepo(e.target.value)}
                      className="mt-1"
                    >
                      <option value="">-- Select a repository --</option>
                      {filteredRepos?.map((repo) => (
                        <option key={repo.full_name} value={repo.html_url}>
                          {repo.full_name} 
                          {repo.is_private && ' 🔒'} 
                          {repo.is_fork && ' 🍴'}
                          {repo.language && ` • ${repo.language}`}
                          {` • ⭐ ${repo.stars}`}
                        </option>
                      ))}
                    </Select>
                  </div>
                  
                  {selectedRepo && (
                    <div className="mt-2 p-3 bg-muted rounded-lg">
                      {(() => {
                        const repo = userRepos.find(r => r.html_url === selectedRepo);
                        return repo ? (
                          <div>
                            <h3 className="font-semibold">{repo.name}</h3>
                            {repo.description && (
                              <p className="text-sm text-muted-foreground mt-1">{repo.description}</p>
                            )}
                            <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
                              {repo.language && <span>📝 {repo.language}</span>}
                              <span>⭐ {repo.stars}</span>
                              <span>🍴 {repo.forks}</span>
                            </div>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  )}
                  
                  <p className="text-sm text-muted-foreground">
                    💡 Select a repository from your GitHub account to import. We'll analyze it to extract project details.
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
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button 
              onClick={() => importMutation.mutate()}
              disabled={
                (importMode === 'url' && !repoUrl) || 
                (importMode === 'dropdown' && !selectedRepo) || 
                importMutation.isPending
              }
            >
              {importMutation.isPending ? 'Importing...' : 'Import Repository'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

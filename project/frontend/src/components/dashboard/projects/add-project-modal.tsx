'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

export function AddProjectModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [technologies, setTechnologies] = useState('');
  const [highlights, setHighlights] = useState('');
  const [url, setUrl] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () =>
      projectsApi.create({
        title,
        description,
        technologies: technologies
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        highlights: highlights
          .split('\n')
          .map((h) => h.trim())
          .filter(Boolean),
        url: url || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast({ title: 'Project created successfully' });
      onClose();
    },
    onError: (error: unknown) => {
      toast({
        title: 'Failed to create project',
        description: apiErrorDetail(error, 'Unknown error'),
        variant: 'destructive',
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-md max-h-[90vh] overflow-y-auto animate-fade-in-up">
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
              💡 Leave empty and we&apos;ll generate 3 technical bullet points automatically
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
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!title || !description || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating…' : 'Create Project'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, Trash2, Calendar, Lock, Globe } from 'lucide-react';
import type { Project } from './types';

export function ProjectCard({
  project,
  onShowDetails,
  onDelete,
}: {
  project: Project;
  onShowDetails: () => void;
  onDelete: () => void;
}) {
  return (
    <Card className="hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-4 border-l-[hsl(var(--success))]">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-2 min-w-0">
            <CardTitle className="text-lg truncate">{project.title}</CardTitle>
            {project.source_type === 'github' &&
              (project.is_private ? (
                <span title="Private repository" className="flex-shrink-0">
                  <Lock className="h-3.5 w-3.5 text-amber-500" />
                </span>
              ) : (
                <span title="Public repository" className="flex-shrink-0">
                  <Globe className="h-3.5 w-3.5 text-green-500" />
                </span>
              ))}
          </div>
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
        <CardDescription className="line-clamp-2">{project.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1 mb-4">
          {project.technologies?.slice(0, 5).map((tech, idx) => (
            <Badge
              key={tech}
              variant="secondary"
              className={`text-xs ${
                idx % 3 === 0
                  ? 'bg-primary/10 text-primary'
                  : idx % 3 === 1
                    ? 'bg-[hsl(var(--accent))]/10 text-[hsl(var(--accent))]'
                    : 'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]'
              }`}
            >
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
          <Button variant="outline" size="sm" onClick={onShowDetails}>
            Show Details
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

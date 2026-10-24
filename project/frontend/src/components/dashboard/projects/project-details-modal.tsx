'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, X } from 'lucide-react';
import type { Project } from './types';

export function ProjectDetailsModal({
  project,
  onClose,
}: {
  project: Project;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-fade-in-up">
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
                  <li key={idx} className="text-sm">
                    {highlight}
                  </li>
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

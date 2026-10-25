import { Building2, ExternalLink, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { JobDescription } from './types';
import { Portal } from '@/components/ui/portal';

/** Full text, skills and keywords of one saved job description. */
export function JobDescriptionModal({
  job,
  onClose,
}: {
  job: JobDescription;
  onClose: () => void;
}) {
  return (
    <Portal>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-3xl max-h-[90vh] overflow-y-auto animate-fade-in-up">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h2 className="text-2xl font-bold">{job.title}</h2>
              <p className="text-muted-foreground flex items-center gap-1">
                <Building2 className="h-4 w-4" />
                {job.company || 'Unknown Company'}
              </p>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-4">
            {/* Job Description */}
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Job Description</h3>
              <div className="text-sm whitespace-pre-wrap bg-muted p-4 rounded-md">
                {job.raw_text}
              </div>
            </div>

            {/* Required Skills */}
            {job.required_skills && job.required_skills.length > 0 && (
              <div>
                <h3 className="font-semibold text-sm text-muted-foreground mb-2">
                  Required Skills
                </h3>
                <div className="flex flex-wrap gap-2">
                  {job.required_skills.map((skill) => (
                    <Badge key={skill} variant="default">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Preferred Skills */}
            {job.preferred_skills && job.preferred_skills.length > 0 && (
              <div>
                <h3 className="font-semibold text-sm text-muted-foreground mb-2">
                  Preferred Skills
                </h3>
                <div className="flex flex-wrap gap-2">
                  {job.preferred_skills.map((skill) => (
                    <Badge key={skill} variant="outline">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Keywords */}
            {job.keywords && job.keywords.length > 0 && (
              <div>
                <h3 className="font-semibold text-sm text-muted-foreground mb-2">Keywords</h3>
                <div className="flex flex-wrap gap-2">
                  {job.keywords.map((keyword) => (
                    <Badge key={keyword} variant="secondary">
                      {keyword}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Source URL */}
            {job.source_url && (
              <div>
                <h3 className="font-semibold text-sm text-muted-foreground mb-1">Source URL</h3>
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline flex items-center gap-1"
                >
                  {job.source_url}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}

            <div className="flex justify-end pt-4">
              <Button onClick={onClose}>Close</Button>
            </div>
          </div>
        </div>
      </div>
    </Portal>
  );
}

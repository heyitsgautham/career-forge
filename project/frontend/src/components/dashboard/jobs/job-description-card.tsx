import { Building2, ExternalLink, Sparkles, Trash2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { JobDescription } from './types';

/** One saved job description with its top skills and analyze and delete actions. */
export function JobDescriptionCard({
  job,
  analyzing,
  onOpen,
  onAnalyze,
  onDelete,
}: {
  job: JobDescription;
  analyzing: boolean;
  onOpen: () => void;
  onAnalyze: () => void;
  onDelete: () => void;
}) {
  return (
    <Card
      className="hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 cursor-pointer border-l-4 border-l-[hsl(var(--accent))]"
      onClick={onOpen}
    >
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-lg">{job.title}</CardTitle>
            <CardDescription className="flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {job.company || 'Unknown Company'}
            </CardDescription>
          </div>
          <div className="flex gap-1">
            {job.is_analyzed && <Badge variant="default">Analyzed</Badge>}
            {job.source_url && (
              <Button variant="ghost" size="icon" asChild>
                <a href={job.source_url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {job.required_skills && job.required_skills.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Required Skills</p>
              <div className="flex flex-wrap gap-1">
                {job.required_skills.slice(0, 6).map((skill) => (
                  <Badge key={skill} variant="outline" className="text-xs">
                    {skill}
                  </Badge>
                ))}
                {job.required_skills.length > 6 && (
                  <Badge variant="outline" className="text-xs">
                    +{job.required_skills.length - 6}
                  </Badge>
                )}
              </div>
            </div>
          )}

          <p className="text-sm text-muted-foreground line-clamp-2">
            {job.raw_text.substring(0, 150)}...
          </p>

          <div className="flex justify-between items-center pt-2">
            <div className="flex gap-2">
              {!job.is_analyzed ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    onAnalyze();
                  }}
                  disabled={analyzing}
                >
                  <Sparkles className="h-3 w-3" />
                  {analyzing ? 'Analyzing…' : 'Analyze'}
                </Button>
              ) : (
                <Badge variant="default" className="gap-1">
                  <Sparkles className="h-3 w-3" />
                  Analyzed
                </Badge>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

import { Github } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

/** "Import from GitHub" with a badge counting the user's repositories. */
export function ImportGithubButton({
  repoCount,
  className,
  onClick,
}: {
  repoCount: number | undefined;
  className: string;
  onClick: () => void;
}) {
  return (
    <Button variant="outline" className={className} onClick={onClick}>
      <Github className="h-4 w-4" />
      Import from GitHub
      {repoCount !== undefined && repoCount > 0 && (
        <Badge variant="secondary" className="ml-1 bg-primary/10 text-primary">
          {repoCount}
        </Badge>
      )}
    </Button>
  );
}

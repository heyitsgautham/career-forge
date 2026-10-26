import { Badge } from '@/components/ui/badge';
import type { GithubRepo } from './github-repos';

/** One repository in the import list, with its checkbox and badges. */
export function RepoOption({
  repo,
  imported,
  isSelected,
  onToggle,
}: {
  repo: GithubRepo;
  imported: boolean;
  isSelected: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={`flex items-start gap-3 px-3 py-2.5 transition-colors ${
        imported
          ? 'opacity-50 cursor-not-allowed bg-muted/30'
          : isSelected
            ? 'bg-primary/5 cursor-pointer hover:bg-muted/50'
            : 'cursor-pointer hover:bg-muted/50'
      }`}
    >
      <input
        type="checkbox"
        checked={isSelected}
        onChange={() => !imported && onToggle()}
        disabled={imported}
        className="mt-1 h-4 w-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500 disabled:opacity-50"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">{repo.full_name}</span>
          {imported && (
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]"
            >
              Imported
            </Badge>
          )}
          {repo.is_private && (
            <Badge variant="outline" className="text-[10px] px-1 py-0">
              Private
            </Badge>
          )}
          {repo.is_fork && (
            <Badge variant="outline" className="text-[10px] px-1 py-0">
              Fork
            </Badge>
          )}
        </div>
        {repo.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{repo.description}</p>
        )}
        <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
          {repo.language && <span>{repo.language}</span>}
          <span>⭐ {repo.stars}</span>
          <span>🍴 {repo.forks}</span>
        </div>
      </div>
    </label>
  );
}

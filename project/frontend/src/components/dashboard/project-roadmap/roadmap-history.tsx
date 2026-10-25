import { Loader2, Trash2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { ProjectRoadmap } from '@/lib/api';

/** Saved roadmaps with their progress, each opening on click. */
export function RoadmapHistory({
  history,
  deleting,
  onOpen,
  onDelete,
}: {
  history: ProjectRoadmap[];
  deleting: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (history.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
        Previous Roadmaps ({history.length})
      </h3>
      <div className="space-y-2">
        {history.map((rm) => {
          const pct = Math.round((rm.completedDays / rm.totalDays) * 100);
          return (
            <Card
              key={rm.projectRoadmapId}
              className="group cursor-pointer hover:shadow-md transition-all duration-200 hover:border-primary/30"
              onClick={() => onOpen(rm.projectRoadmapId)}
            >
              <CardContent className="flex items-center justify-between p-4 gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate">{rm.projectTitle}</p>
                  <p className="text-xs text-muted-foreground">
                    {rm.completedDays}/{rm.totalDays} days • {rm.domain}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className="w-20 h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium tabular-nums w-8 text-right">{pct}%</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(rm.projectRoadmapId);
                    }}
                    disabled={deleting === rm.projectRoadmapId}
                  >
                    {deleting === rm.projectRoadmapId ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

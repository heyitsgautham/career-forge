import { Card, CardContent, CardHeader } from '@/components/ui/card';

/** Three pulsing cards shown while the project list loads. */
export function ProjectGridSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="animate-pulse" data-testid="project-skeleton">
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

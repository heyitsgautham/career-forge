import { Timer } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { SchedulerStatus } from '@/lib/api';

/** Green or red strip that reports how the last scheduled scrape went. */
export function ScrapeStatusBanner({
  lastScrape,
}: {
  lastScrape: SchedulerStatus['lastScrape'] | undefined;
}) {
  if (!lastScrape?.status) return null;
  const ok = lastScrape.status === 'success';

  return (
    <Card
      className={
        ok
          ? 'border-[hsl(var(--success))]/20 bg-[hsl(var(--success))]/5'
          : 'border-destructive/20 bg-destructive/5'
      }
    >
      <CardContent className="flex items-center gap-3 px-5 py-3">
        <Timer className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="text-sm">
          <span className="font-medium">{ok ? 'Last Scrape Completed' : 'Last Scrape Failed'}</span>
          {' — '}
          <span className="text-muted-foreground">{lastScrape.message}</span>
        </div>
      </CardContent>
    </Card>
  );
}

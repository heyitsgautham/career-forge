import { Loader2, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DOMAIN_CHIPS } from './constants';

/** Domain input with quick-pick chips and the "Suggest 3 Projects" button. */
export function DomainForm({
  domain,
  suggesting,
  onDomainChange,
  onSuggest,
}: {
  domain: string;
  suggesting: boolean;
  onDomainChange: (domain: string) => void;
  onSuggest: () => void;
}) {
  return (
    <Card className="border-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          What do you want to build?
        </CardTitle>
        <CardDescription>Pick a domain to get started</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Domain input */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Domain / Area</label>
          <input
            type="text"
            value={domain}
            onChange={(e) => onDomainChange(e.target.value)}
            placeholder="e.g., Web Development, Machine Learning..."
            className="w-full rounded-xl border border-input px-4 py-3 text-sm bg-background transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40"
            onKeyDown={(e) => e.key === 'Enter' && onSuggest()}
          />
          <div className="flex flex-wrap gap-2 pt-1">
            {DOMAIN_CHIPS.map((d) => (
              <button
                key={d}
                onClick={() => onDomainChange(d)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-200 ${
                  domain === d
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-muted/50 text-muted-foreground border-border hover:bg-primary/10 hover:text-primary hover:border-primary/30'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Generate button */}
        <Button
          onClick={onSuggest}
          disabled={suggesting || !domain.trim()}
          className="w-full h-12 text-base gap-2 rounded-xl"
          size="lg"
        >
          {suggesting ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" /> Finding projects...
            </>
          ) : (
            <>
              <Sparkles className="h-5 w-5" /> Suggest 3 Projects
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

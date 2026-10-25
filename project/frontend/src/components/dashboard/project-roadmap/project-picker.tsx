'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, ChevronDown, Clock, Sparkles, ArrowLeft, Code2, Rocket } from 'lucide-react';
import { type ProjectSuggestion } from '@/lib/api';

export function ProjectPicker({
  suggestions,
  onPick,
  picking,
  onBack,
}: {
  suggestions: { domain: string; projects: ProjectSuggestion[] };
  onPick: (p: ProjectSuggestion) => void;
  picking: boolean;
  onBack: () => void;
}) {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1 -ml-2 mb-2 text-muted-foreground"
          onClick={onBack}
        >
          <ArrowLeft className="h-4 w-4" /> Change domain
        </Button>
        <h2 className="text-2xl font-bold">Choose Your Project</h2>
        <p className="text-muted-foreground text-sm mt-1">
          Pick one of these <strong>{suggestions.domain}</strong> projects. We&apos;ll build a 7-day
          plan for the one you choose.
        </p>
      </div>

      <div className="grid gap-4 stagger-children">
        {suggestions.projects.map((p) => (
          <Card
            key={p.id}
            className="group relative border-2 cursor-pointer transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:-translate-y-0.5 overflow-hidden"
            onClick={() => !picking && onPick(p)}
          >
            {/* Difficulty strip */}
            <div
              className={`absolute left-0 top-0 bottom-0 w-1.5 ${p.difficulty === 'hard' ? 'bg-rose-500' : 'bg-amber-500'}`}
            />

            <CardContent className="flex items-start gap-4 p-5 pl-6">
              {/* Icon */}
              <div
                className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${
                  p.difficulty === 'hard'
                    ? 'bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:text-rose-400'
                    : 'bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400'
                }`}
              >
                {p.difficulty === 'hard' ? (
                  <Rocket className="h-6 w-6" />
                ) : (
                  <Code2 className="h-6 w-6" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold">{p.title}</h3>
                  <Badge
                    variant="outline"
                    className={`text-xs capitalize ${
                      p.difficulty === 'hard'
                        ? 'border-rose-200 text-rose-600 dark:border-rose-800 dark:text-rose-400'
                        : 'border-amber-200 text-amber-600 dark:border-amber-800 dark:text-amber-400'
                    }`}
                  >
                    {p.difficulty}
                  </Badge>
                </div>

                <p className="text-sm text-muted-foreground leading-relaxed">{p.description}</p>

                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {p.techStack.map((t) => (
                    <Badge key={t} variant="secondary" className="text-xs font-normal">
                      {t}
                    </Badge>
                  ))}
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" /> ~{p.estimatedHours}h
                  </span>
                  {p.keySkills.slice(0, 3).map((s, i) => (
                    <span key={i} className="flex items-center gap-1">
                      <Sparkles className="h-3 w-3" /> {s}
                    </span>
                  ))}
                </div>
              </div>

              {/* Hover arrow */}
              <div className="self-center opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronDown className="h-5 w-5 text-primary rotate-[-90deg]" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {picking && (
        <div className="flex items-center justify-center gap-2 text-primary py-4">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm font-medium">Building your 7-day plan...</span>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Main component — orchestrates the 3 steps
   ═══════════════════════════════════════════════════════════════════════════ */

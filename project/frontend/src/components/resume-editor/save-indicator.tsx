import { CheckCircle, Cloud } from 'lucide-react';
import type { SaveStatus } from './use-resume-save';

/** "Saving…", "Unsaved" or "Saved" under the resume name. */
export function SaveIndicator({ saveStatus }: { saveStatus: SaveStatus }) {
  return saveStatus === 'saving' ? (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Cloud className="h-3.5 w-3.5 animate-pulse" /> Saving…
    </span>
  ) : saveStatus === 'dirty' ? (
    <span className="text-xs text-amber-500">● Unsaved</span>
  ) : (
    <span className="flex items-center gap-1 text-xs text-emerald-600">
      <CheckCircle className="h-3.5 w-3.5" /> Saved
    </span>
  );
}

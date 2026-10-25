import { useCallback, useRef, useState } from 'react';
import { resumesApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export type SaveStatus = 'saved' | 'dirty' | 'saving';

export const AUTO_SAVE_DELAY = 2000; // ms

/**
 * Saves the editor's LaTeX, either now or two seconds after the last change.
 * A pending auto-save still runs if the page unmounts first, so leaving the
 * editor straight after typing keeps the edit.
 */
export function useResumeSave(resumeId: string, getContent: () => string | undefined) {
  const { toast } = useToast();
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const save = useCallback(
    async (latex?: string) => {
      const content = latex ?? getContent() ?? '';
      if (!content) return;
      setSaveStatus('saving');
      try {
        await resumesApi.saveLaTeX(resumeId, content);
        setSaveStatus('saved');
      } catch {
        setSaveStatus('dirty');
        toast({ title: 'Save failed', variant: 'destructive' });
      }
    },
    [resumeId, toast, getContent]
  );

  /** Marks the document dirty and restarts the auto-save countdown. */
  const scheduleSave = useCallback(
    (latex: string) => {
      setSaveStatus('dirty');
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => save(latex), AUTO_SAVE_DELAY);
    },
    [save]
  );

  return { saveStatus, save, scheduleSave };
}

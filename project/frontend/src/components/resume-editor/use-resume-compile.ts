import { useCallback, useEffect, useState } from 'react';
import { resumesApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

export type CompileStatus = 'idle' | 'compiling' | 'success' | 'error';

const MAX_ERROR_LINES = 3;
const MAX_ERROR_CHARS = 300;

/** The first few lines of a LaTeX log message on one line, short enough for a toast. */
export function summarizeCompileError(message: string): string {
  const lines = message
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, MAX_ERROR_LINES)
    .join(' ');
  return lines.length > MAX_ERROR_CHARS ? `${lines.slice(0, MAX_ERROR_CHARS - 1)}…` : lines;
}

interface LoadedResume {
  status?: string;
  pdf_path?: string | null;
}

/**
 * Compiles the editor's LaTeX to a PDF and tracks the preview URL.
 *
 * When the resume loads already compiled, the hook fetches a fresh signed URL
 * for the stored PDF so the preview works before the first compile.
 */
export function useResumeCompile(
  resumeId: string,
  resume: LoadedResume | undefined,
  getContent: () => string | undefined,
  beforeCompile?: () => void
) {
  const { toast } = useToast();
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [compileStatus, setCompileStatus] = useState<CompileStatus>('idle');
  const [compileError, setCompileError] = useState<string | null>(null);

  useEffect(() => {
    if (!resume) return;
    if (resume.status === 'compiled' || resume.pdf_path) {
      resumesApi
        .getPdfUrl(resumeId)
        .then((res) => {
          setPdfUrl(res.data.url);
          setCompileStatus('success');
        })
        .catch(() => {
          if (resume.pdf_path) {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            setPdfUrl(`${apiBase}/uploads/pdfs/${resumeId.slice(0, 8)}.pdf`);
            setCompileStatus('success');
          }
        });
    }
  }, [resume, resumeId]);

  const compile = useCallback(async () => {
    const content = getContent();
    if (!content) return;
    setCompileStatus('compiling');
    setCompileError(null);
    beforeCompile?.();
    try {
      const res = await resumesApi.compileWithContent(resumeId, content);
      const { pdf_url, status, error_message } = res.data;
      if (status === 'compiled' && pdf_url) {
        let finalUrl = pdf_url;
        try {
          const urlRes = await resumesApi.getPdfUrl(resumeId);
          finalUrl = urlRes.data.url;
        } catch {
          finalUrl = pdf_url;
        }
        setPdfUrl(finalUrl);
        setCompileStatus('success');
        toast({ title: 'Compiled successfully' });
      } else {
        const message = error_message || 'Compilation failed';
        setCompileStatus('error');
        setCompileError(message);
        toast({
          title: 'Compilation failed',
          description: summarizeCompileError(message),
          variant: 'destructive',
        });
      }
    } catch (err: unknown) {
      const message = apiErrorDetail(
        err,
        err instanceof Error && err.message ? err.message : 'Compilation failed'
      );
      setCompileStatus('error');
      setCompileError(message);
      toast({ title: 'Compile error', description: message, variant: 'destructive' });
    }
  }, [resumeId, toast, getContent, beforeCompile]);

  return { pdfUrl, compileStatus, compileError, compile };
}

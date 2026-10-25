import { useCallback, useEffect, useState } from 'react';
import { resumesApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export type CompileStatus = 'idle' | 'compiling' | 'success' | 'error';

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
        setCompileStatus('error');
        setCompileError(error_message ?? 'Compilation failed');
        toast({ title: 'Compilation failed', variant: 'destructive' });
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Compilation failed';
      setCompileStatus('error');
      setCompileError(message);
      toast({ title: 'Compile error', variant: 'destructive' });
    }
  }, [resumeId, toast, getContent, beforeCompile]);

  return { pdfUrl, compileStatus, compileError, compile };
}

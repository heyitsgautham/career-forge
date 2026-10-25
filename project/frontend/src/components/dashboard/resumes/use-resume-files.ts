import { resumesApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import type { Resume } from './types';

/** The YYYY-MM-DD part of a resume timestamp, used in download file names. */
export function resumeDateStamp(createdAt: string): string {
  return new Date(createdAt).toISOString().split('T')[0];
}

/** Opening and downloading a resume's PDF and LaTeX source. */
export function useResumeFiles() {
  const { toast } = useToast();

  const previewPdf = async (resume: Resume) => {
    if (!resume.pdf_path) {
      toast({ title: 'PDF not available', variant: 'destructive' });
      return;
    }
    try {
      const { data } = await resumesApi.getPdfUrl(resume.id);
      window.open(data.url, '_blank', 'noopener,noreferrer');
    } catch {
      toast({ title: 'Failed to open PDF', variant: 'destructive' });
    }
  };

  const downloadPdf = async (resume: Resume) => {
    if (!resume.pdf_path) {
      toast({ title: 'PDF not available', variant: 'destructive' });
      return;
    }
    try {
      // Use the /pdf endpoint which returns a redirect to a presigned URL
      // with Content-Disposition: attachment so the browser saves the file.
      const { data } = await resumesApi.getPdfDownloadUrl(resume.id);
      const link = document.createElement('a');
      link.href = data.url;
      link.setAttribute('download', `resume-${resumeDateStamp(resume.created_at)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      toast({ title: 'Failed to download PDF', variant: 'destructive' });
    }
  };

  const downloadTex = async (resumeId: string, filename?: string) => {
    try {
      const response = await resumesApi.downloadTex(resumeId);
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/plain' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename ?? `resume-${resumeId.slice(0, 8)}.tex`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast({ title: '.tex download failed', variant: 'destructive' });
    }
  };

  return { previewPdf, downloadPdf, downloadTex };
}

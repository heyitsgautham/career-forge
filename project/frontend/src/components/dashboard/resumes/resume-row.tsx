import Link from 'next/link';
import { Download, Edit, Eye, FileText, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { statusConfig } from './status-config';
import { CompileButton } from './compile-button';
import { resumeDateStamp, useResumeFiles } from './use-resume-files';
import type { Resume } from './types';

/** One resume with its status and the actions that status allows. */
export function ResumeRow({ resume, onDelete }: { resume: Resume; onDelete: () => void }) {
  const { previewPdf, downloadPdf, downloadTex } = useResumeFiles();
  const status = statusConfig[resume.status] || statusConfig.draft;
  const StatusIcon = status.icon;
  const isProcessing = resume.status === 'generating' || resume.status === 'compiling';

  return (
    <div className="group flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors">
      {/* Icon */}
      <div className="shrink-0 h-8 w-8 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
        <FileText className="h-4 w-4 text-violet-600 dark:text-violet-400" />
      </div>

      {/* Name + date */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{resume.name}</p>
        <p className="text-xs text-muted-foreground">
          {new Date(resume.updated_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
        {resume.error_message && (
          <p className="text-xs text-red-500 truncate mt-0.5">{resume.error_message}</p>
        )}
      </div>

      {/* Status badge */}
      <Badge variant="secondary" className={`shrink-0 text-xs font-medium gap-1 ${status.color}`}>
        <StatusIcon className={`h-3 w-3 ${isProcessing ? 'animate-spin' : ''}`} />
        {status.text}
      </Badge>

      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {(resume.status === 'compiled' || resume.status === 'generated') && resume.pdf_path && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="gap-1 h-7 text-xs"
              onClick={() => previewPdf(resume)}
            >
              <Eye className="h-3 w-3" />
              Preview
            </Button>
            <Button size="sm" className="gap-1 h-7 text-xs" onClick={() => downloadPdf(resume)}>
              <Download className="h-3 w-3" />
              PDF
            </Button>
            {resume.tex_s3_key && (
              <Button
                size="sm"
                variant="outline"
                className="gap-1 h-7 text-xs"
                onClick={() =>
                  downloadTex(resume.id, `resume-${resumeDateStamp(resume.created_at)}.tex`)
                }
              >
                <FileText className="h-3 w-3" />
                .tex
              </Button>
            )}
          </>
        )}
        {resume.status === 'generated' && !resume.pdf_path && (
          <CompileButton resumeId={resume.id} />
        )}
        {(resume.latex_content || ['generated', 'compiled', 'error'].includes(resume.status)) && (
          <Link href={`/dashboard/resumes/${resume.id}/edit`}>
            <Button
              size="sm"
              variant={resume.status === 'compiled' ? 'default' : 'outline'}
              className={`gap-1 h-7 text-xs ${resume.status === 'compiled' ? 'bg-primary hover:bg-primary/90 text-primary-foreground' : ''}`}
            >
              <Edit className="h-3 w-3" />
              {resume.status === 'compiled' ? 'Open in Editor' : 'Edit'}
            </Button>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={() => {
            if (confirm('Delete this resume?')) {
              onDelete();
            }
          }}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

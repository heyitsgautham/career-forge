'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { resumesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { Loader2, FileText } from 'lucide-react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import type { LatexEditorHandle } from '@/components/resume-editor/latex-editor';
import { EditorLayout } from '@/components/resume-editor/editor-layout';
import { AiChatDrawer } from '@/components/resume-editor/ai-chat-drawer';
import { CodePreviewPanel } from '@/components/resume-editor/code-preview-panel';
import { EditorToolbar } from '@/components/resume-editor/editor-toolbar';
import { useResumeFiles } from '@/components/dashboard/resumes/use-resume-files';
import { useResumeCompile } from '@/components/resume-editor/use-resume-compile';
import { useResumeSave } from '@/components/resume-editor/use-resume-save';

// Monaco editor must be dynamically imported (no SSR)
const LatexEditor = dynamic(
  () => import('@/components/resume-editor/latex-editor').then((m) => m.LatexEditor),
  { ssr: false, loading: () => <div className="flex-1 bg-[#1e1e1e]" /> }
);

const AUTO_COMPILE_DELAY = 3000; // ms

export default function ResumeEditorPage() {
  const params = useParams();
  const { toast } = useToast();
  const resumeId = params.id as string;

  // Editor handle ref (from Monaco)
  const editorHandleRef = useRef<LatexEditorHandle | null>(null);

  // State
  const [autoCompile, setAutoCompile] = useState(true); // on by default

  // Debounce timer
  const autoCompileTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch resume
  const { data: resume, isLoading } = useQuery({
    queryKey: ['resume', resumeId],
    queryFn: async () => {
      const res = await resumesApi.get(resumeId);
      return res.data;
    },
    enabled: !!resumeId,
  });

  const getContent = useCallback(() => editorHandleRef.current?.getValue(), []);
  const clearMarkers = useCallback(() => editorHandleRef.current?.clearMarkers?.(), []);
  const { saveStatus, save: doSave, scheduleSave } = useResumeSave(resumeId, getContent);
  const { downloadTex } = useResumeFiles();
  const {
    pdfUrl,
    compileStatus,
    compile: doCompile,
  } = useResumeCompile(resumeId, resume, getContent, clearMarkers);

  // ─── Editor change handler ────────────────────────────────────────────────────

  const handleEditorChange = useCallback(
    (value: string) => {
      scheduleSave(value);

      if (autoCompile) {
        if (autoCompileTimerRef.current) clearTimeout(autoCompileTimerRef.current);
        autoCompileTimerRef.current = setTimeout(() => doCompile(), AUTO_COMPILE_DELAY);
      }
    },
    [scheduleSave, doCompile, autoCompile]
  );

  const toggleAutoCompile = useCallback(() => {
    // Switching off also drops a compile the last keystroke already queued.
    if (autoCompileTimerRef.current) clearTimeout(autoCompileTimerRef.current);
    autoCompileTimerRef.current = null;
    setAutoCompile((v) => !v);
  }, []);

  // ─── Keyboard shortcuts ───────────────────────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === 's') {
        e.preventDefault();
        doSave();
      }
      if (mod && e.key === 'Enter') {
        e.preventDefault();
        doCompile();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [doSave, doCompile]);

  // ─── Download PDF ─────────────────────────────────────────────────────────────

  const handleDownload = () => {
    if (pdfUrl) window.open(pdfUrl, '_blank');
  };

  // ─── Apply AI latex ────────────────────────────────────────────────────────────

  const handleApplyLatex = useCallback(
    (latex: string) => {
      editorHandleRef.current?.setValue(latex);
      scheduleSave(latex);
      toast({ title: 'AI changes applied to editor' });
    },
    [scheduleSave, toast]
  );

  // ─── Render ───────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
          <span className="text-sm text-muted-foreground">Loading editor…</span>
        </div>
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-4">
        <FileText className="h-12 w-12 text-muted-foreground opacity-30" />
        <p className="text-muted-foreground">Resume not found.</p>
        <Link href="/dashboard">
          <Button variant="outline" size="sm">
            Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <EditorToolbar
        name={resume.name}
        saveStatus={saveStatus}
        compileStatus={compileStatus}
        autoCompile={autoCompile}
        pdfUrl={pdfUrl}
        onToggleAutoCompile={toggleAutoCompile}
        onSave={() => doSave()}
        onCompile={doCompile}
        onDownloadPdf={handleDownload}
        onDownloadTex={() => downloadTex(resumeId, `${resume.name || 'resume'}.tex`)}
      />

      {/* ── Main: left (AI chat) + right (code/preview toggle) ───── */}
      <EditorLayout
        className="flex-1"
        left={
          <AiChatDrawer
            resumeId={resumeId}
            getLatex={() => editorHandleRef.current?.getValue() ?? resume.latex_content ?? ''}
            onApplyLatex={handleApplyLatex}
          />
        }
        right={
          <CodePreviewPanel
            fileName={`${resume.name}.tex`}
            pdfUrl={pdfUrl}
            onPreviewWithoutPdf={() =>
              toast({ title: 'No PDF yet — compile first', variant: 'destructive' })
            }
            editor={
              <LatexEditor
                initialValue={resume.latex_content ?? ''}
                onChange={handleEditorChange}
                onEditorReady={(handle) => {
                  editorHandleRef.current = handle;
                }}
              />
            }
          />
        }
      />
    </div>
  );
}

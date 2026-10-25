'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { resumesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import {
  ArrowLeft,
  Save,
  Play,
  Download,
  Loader2,
  FileText,
  Eye,
  Cloud,
  CheckCircle,
  Code2,
} from 'lucide-react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { LatexEditorHandle } from '@/components/resume-editor/latex-editor';
import { EditorLayout } from '@/components/resume-editor/editor-layout';
import { AiChatDrawer } from '@/components/resume-editor/ai-chat-drawer';
import { cn } from '@/lib/utils';
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
  const [activeTab, setActiveTab] = useState<'code' | 'preview'>('code');

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

  // ─── Download .tex ────────────────────────────────────────────────────────────

  const handleDownloadTex = async () => {
    try {
      const response = await resumesApi.downloadTex(resumeId);
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/plain' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `${resume?.name || 'resume'}.tex`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast({ title: '.tex download failed', variant: 'destructive' });
    }
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

  const saveIndicator =
    saveStatus === 'saving' ? (
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

  // ─── Left panel ───────────────────────────────────────────────────────────────

  const leftPanel = (
    <div className="h-full flex flex-col">
      {/* Tab bar: Code / Preview toggle */}
      <div className="flex items-center gap-0 px-2 py-1.5 border-b bg-card shrink-0">
        <button
          onClick={() => setActiveTab('code')}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors',
            activeTab === 'code'
              ? 'bg-violet-600 text-white'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          <Code2 className="h-3.5 w-3.5" />
          Code
        </button>
        <button
          onClick={() => {
            if (!pdfUrl) {
              toast({ title: 'No PDF yet — compile first', variant: 'destructive' });
              return;
            }
            setActiveTab('preview');
          }}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors',
            activeTab === 'preview'
              ? 'bg-violet-600 text-white'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          <Eye className="h-3.5 w-3.5" />
          Preview
        </button>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground pr-1">
          <FileText className="h-3.5 w-3.5" />
          {resume.name}.tex
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {/* Monaco editor — always mounted so state is preserved, hidden when previewing */}
        <div className={cn('h-full', activeTab !== 'code' && 'hidden')}>
          <LatexEditor
            initialValue={resume.latex_content ?? ''}
            onChange={handleEditorChange}
            onEditorReady={(handle) => {
              editorHandleRef.current = handle;
            }}
          />
        </div>

        {/* Inline PDF preview */}
        {activeTab === 'preview' && (
          <div className="h-full bg-[#525659]">
            {pdfUrl ? (
              <iframe src={pdfUrl} title="Resume PDF preview" className="w-full h-full border-0" />
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-sm text-muted-foreground">No PDF yet — compile first</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* ── Toolbar ─────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-4 py-2 border-b bg-card shrink-0 h-14">
        {/* Left */}
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/dashboard?tab=resumes">
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="min-w-0">
            <h1 className="font-semibold text-sm truncate">{resume.name}</h1>
            <div className="flex items-center gap-2">{saveIndicator}</div>
          </div>
        </div>

        {/* Right */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Auto-compile toggle */}
          <Button
            variant={autoCompile ? 'secondary' : 'ghost'}
            size="sm"
            className="h-8 gap-1.5 text-xs hidden sm:flex"
            onClick={() => setAutoCompile((v) => !v)}
          >
            <Play className="h-3 w-3" />
            Auto-compile {autoCompile ? 'ON' : 'OFF'}
          </Button>

          {/* Save */}
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => doSave()}
            disabled={saveStatus === 'saving'}
          >
            {saveStatus === 'saving' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save
          </Button>

          {/* Compile */}
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={doCompile}
            disabled={compileStatus === 'compiling'}
          >
            {compileStatus === 'compiling' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Compile
          </Button>

          {/* Download PDF */}
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs bg-violet-600 hover:bg-violet-700 text-white"
            onClick={handleDownload}
            disabled={!pdfUrl}
          >
            <Download className="h-3.5 w-3.5" />
            PDF
          </Button>

          {/* Download .tex */}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs hidden md:flex"
            onClick={handleDownloadTex}
          >
            <FileText className="h-3.5 w-3.5" />
            .tex
          </Button>
        </div>
      </header>

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
        right={leftPanel}
      />
    </div>
  );
}

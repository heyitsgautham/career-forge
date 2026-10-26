import Link from 'next/link';
import { ArrowLeft, Download, FileText, Loader2, Play, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SaveIndicator } from './save-indicator';
import type { CompileStatus } from './use-resume-compile';
import type { SaveStatus } from './use-resume-save';

/** Top bar of the resume editor: name and save state, then the editor actions. */
export function EditorToolbar({
  name,
  saveStatus,
  compileStatus,
  autoCompile,
  pdfUrl,
  onToggleAutoCompile,
  onSave,
  onCompile,
  onDownloadPdf,
  onDownloadTex,
}: {
  name: string;
  saveStatus: SaveStatus;
  compileStatus: CompileStatus;
  autoCompile: boolean;
  pdfUrl: string | null;
  onToggleAutoCompile: () => void;
  onSave: () => void;
  onCompile: () => void;
  onDownloadPdf: () => void;
  onDownloadTex: () => void;
}) {
  return (
    <header className="flex items-center justify-between px-4 py-2 border-b bg-card shrink-0 h-14">
      {/* Left */}
      <div className="flex items-center gap-3 min-w-0">
        <Link href="/dashboard?tab=resumes">
          <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="min-w-0">
          <h1 className="font-semibold text-sm truncate">{name}</h1>
          <div className="flex items-center gap-2">
            <SaveIndicator saveStatus={saveStatus} />
          </div>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Auto-compile toggle */}
        <Button
          variant={autoCompile ? 'secondary' : 'ghost'}
          size="sm"
          className="h-8 gap-1.5 text-xs hidden sm:flex"
          onClick={onToggleAutoCompile}
        >
          <Play className="h-3 w-3" />
          Auto-compile {autoCompile ? 'ON' : 'OFF'}
        </Button>

        {/* Save */}
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-xs"
          onClick={onSave}
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
          onClick={onCompile}
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
          onClick={onDownloadPdf}
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
          onClick={onDownloadTex}
        >
          <FileText className="h-3.5 w-3.5" />
          .tex
        </Button>
      </div>
    </header>
  );
}

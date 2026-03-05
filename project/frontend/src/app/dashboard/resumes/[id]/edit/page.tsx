'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import Editor from '@monaco-editor/react';
import { resumesApi, projectsApi, templatesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { 
  ArrowLeft, 
  Save, 
  Play, 
  Download, 
  FileText,
  Loader2,
  CheckCircle,
  XCircle,
  Eye
} from 'lucide-react';
import Link from 'next/link';

export default function ResumeEditorPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const resumeId = params.id as string;
  
  const [latexContent, setLatexContent] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Fetch resume data
  const { data: resume, isLoading, refetch } = useQuery({
    queryKey: ['resume', resumeId],
    queryFn: async () => {
      const res = await resumesApi.get(resumeId);
      return res.data;
    },
    enabled: !!resumeId,
  });

  // Update local state when resume loads
  useEffect(() => {
    if (resume?.latex_content) {
      setLatexContent(resume.latex_content);
    }
  }, [resume]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: () => resumesApi.updateLatex(resumeId, latexContent),
    onSuccess: () => {
      setHasUnsavedChanges(false);
      toast({ title: 'Saved!', description: 'LaTeX content saved successfully.' });
      refetch();
    },
    onError: () => {
      toast({ 
        title: 'Error', 
        description: 'Failed to save changes.', 
        variant: 'destructive' 
      });
    },
  });

  // Compile mutation
  const compileMutation = useMutation({
    mutationFn: async () => {
      // Save first if there are changes
      if (hasUnsavedChanges) {
        await resumesApi.updateLatex(resumeId, latexContent);
      }
      return resumesApi.compile(resumeId);
    },
    onSuccess: (res) => {
      if (res.data.success) {
        toast({ title: 'Compiled!', description: 'PDF generated successfully.' });
      } else {
        toast({ 
          title: 'Compilation failed', 
          description: res.data.errors?.[0]?.message || 'Check LaTeX for errors.',
          variant: 'destructive'
        });
      }
      refetch();
    },
    onError: () => {
      toast({ 
        title: 'Error', 
        description: 'Compilation failed.', 
        variant: 'destructive' 
      });
    },
  });

  // Download PDF
  const handleDownload = async () => {
    try {
      const response = await resumesApi.downloadPdf(resumeId);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${resume?.name || 'resume'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      toast({ 
        title: 'Error', 
        description: 'Failed to download PDF.',
        variant: 'destructive'
      });
    }
  };

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setLatexContent(value);
      setHasUnsavedChanges(true);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b bg-card px-4 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/dashboard">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="font-semibold flex items-center gap-2">
              {resume?.name}
              {hasUnsavedChanges && <span className="text-muted-foreground text-sm">(unsaved)</span>}
            </h1>
            <p className="text-xs text-muted-foreground">
              Status: {resume?.status}
            </p>
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !hasUnsavedChanges}
          >
            {saveMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save
          </Button>
          
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => compileMutation.mutate()}
            disabled={compileMutation.isPending}
          >
            {compileMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Compile
          </Button>
          
          <Button 
            size="sm"
            onClick={handleDownload}
            disabled={resume?.status !== 'compiled'}
          >
            <Download className="h-4 w-4 mr-2" />
            Download PDF
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Editor Panel */}
        <div className="flex-1 border-r flex flex-col">
          <div className="p-2 border-b bg-muted/50 flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">LaTeX Editor</span>
          </div>
          <div className="flex-1">
            <Editor
              height="100%"
              defaultLanguage="latex"
              value={latexContent}
              onChange={handleEditorChange}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                wordWrap: 'on',
                automaticLayout: true,
                scrollBeyondLastLine: false,
              }}
            />
          </div>
        </div>

        {/* Preview Panel */}
        <div className="w-1/2 flex flex-col">
          <div className="p-2 border-b bg-muted/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">PDF Preview</span>
            </div>
            {resume?.status === 'compiled' && (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <CheckCircle className="h-3 w-3" />
                Ready
              </span>
            )}
            {resume?.status === 'error' && (
              <span className="flex items-center gap-1 text-xs text-red-600">
                <XCircle className="h-3 w-3" />
                Error
              </span>
            )}
          </div>
          <div className="flex-1 bg-muted overflow-auto p-4">
            {resume?.status === 'compiled' && resume?.pdf_path ? (
              <iframe
                src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/uploads/pdfs/${resumeId.slice(0, 8)}.pdf`}
                className="w-full h-full border-0"
                title="PDF Preview"
              />
            ) : resume?.latex_content ? (
              <div className="h-full">
                <div className="bg-card p-4 rounded-lg shadow-inner max-h-full overflow-auto">
                  <h3 className="text-sm font-semibold mb-2 text-muted-foreground">LaTeX Preview (raw)</h3>
                  <pre className="text-xs font-mono whitespace-pre-wrap">
                    {latexContent.slice(0, 2000)}
                    {latexContent.length > 2000 && '...'}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                <FileText className="h-16 w-16 mb-4 opacity-30" />
                <p className="text-center">
                  {resume?.status === 'error' 
                    ? 'Compilation failed. Check your LaTeX for errors.'
                    : 'Click "Compile" to generate PDF preview'}
                </p>
                {resume?.error_message && (
                  <p className="text-sm text-destructive mt-2 max-w-md text-center">
                    {resume.error_message}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { templatesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import { LatexOutlinePreview } from './latex-outline-preview';
import type { Template } from './types';

export function TemplatePreviewModal({
  template,
  onClose,
}: {
  template: Template;
  onClose: () => void;
}) {
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview');
  const { data: fullTemplate, isLoading } = useQuery({
    queryKey: ['template', template.id],
    queryFn: async () => {
      const res = await templatesApi.get(template.id);
      return res.data;
    },
    staleTime: 30 * 60 * 1000, // 30 min
    gcTime: 60 * 60 * 1000, // 60 min
  });

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-4xl max-h-[90vh] overflow-y-auto animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{template.name}</h2>
          <div className="flex items-center gap-2">
            <div className="flex bg-muted rounded-lg p-1">
              <button
                className={`px-3 py-1 rounded text-sm ${viewMode === 'preview' ? 'bg-background shadow' : ''}`}
                onClick={() => setViewMode('preview')}
              >
                Preview
              </button>
              <button
                className={`px-3 py-1 rounded text-sm ${viewMode === 'code' ? 'bg-background shadow' : ''}`}
                onClick={() => setViewMode('code')}
              >
                LaTeX Code
              </button>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <p className="text-muted-foreground mb-4">{template.description || 'Resume template'}</p>

        <div className="bg-muted p-4 rounded-lg">
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading…</div>
          ) : viewMode === 'preview' ? (
            <div className="overflow-auto max-h-[60vh]">
              {fullTemplate?.latex_content ? (
                <LatexOutlinePreview latex={fullTemplate.latex_content} />
              ) : (
                <p className="text-center text-muted-foreground">No content available</p>
              )}
            </div>
          ) : (
            <pre className="text-sm font-mono whitespace-pre-wrap overflow-x-auto max-h-[60vh]">
              {fullTemplate?.latex_content || 'No LaTeX content available'}
            </pre>
          )}
        </div>

        <div className="flex justify-between mt-4">
          <p className="text-xs text-muted-foreground">
            💡 Create a resume using this template to generate the actual PDF
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => {
                if (fullTemplate?.latex_content) {
                  navigator.clipboard.writeText(fullTemplate.latex_content);
                }
              }}
              disabled={!fullTemplate?.latex_content}
            >
              Copy LaTeX
            </Button>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

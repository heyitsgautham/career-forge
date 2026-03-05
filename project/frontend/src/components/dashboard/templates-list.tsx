'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { templatesApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { LayoutTemplate, Eye, Copy, Edit, Trash2, Star, Plus, X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  is_system: boolean;
  use_count: number;
  latex_content: string;
  preview_image?: string;
  created_at: string;
}

export function TemplatesList() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState<Template | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: templates, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const res = await templatesApi.list();
      return res.data as Template[];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => templatesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      toast({ title: 'Template deleted' });
    },
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <div className="aspect-[8.5/11] bg-muted"></div>
            <CardHeader>
              <div className="h-5 bg-muted rounded w-3/4"></div>
              <div className="h-4 bg-muted rounded w-full mt-2"></div>
            </CardHeader>
          </Card>
        ))}
      </div>
    );
  }

  // Separate system and user templates
  const systemTemplates = templates?.filter(t => t.is_system) || [];
  const userTemplates = templates?.filter(t => !t.is_system) || [];

  return (
    <div className="space-y-8">
      <div className="flex justify-end">
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Template
        </Button>
      </div>

      {/* System Templates */}
      {systemTemplates.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Star className="h-5 w-5 text-yellow-500" />
            System Templates
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {systemTemplates.map((template) => (
              <TemplateCard 
                key={template.id} 
                template={template} 
                isSystem 
                onPreview={() => setShowPreviewModal(template)}
              />
            ))}
          </div>
        </section>
      )}

      {/* User Templates */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Your Templates</h2>
        {userTemplates.length === 0 ? (
          <Card className="text-center py-8">
            <CardContent>
              <LayoutTemplate className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground mb-4">
                No custom templates yet. Create one or duplicate a system template.
              </p>
              <Button onClick={() => setShowAddModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Template
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {userTemplates.map((template) => (
              <TemplateCard 
                key={template.id} 
                template={template}
                onPreview={() => setShowPreviewModal(template)}
                onDelete={() => deleteMutation.mutate(template.id)}
              />
            ))}
          </div>
        )}
      </section>

      {showAddModal && <AddTemplateModal onClose={() => setShowAddModal(false)} />}
      {showPreviewModal && (
        <PreviewModal template={showPreviewModal} onClose={() => setShowPreviewModal(null)} />
      )}
    </div>
  );
}

function TemplateCard({ 
  template, 
  isSystem = false,
  onPreview,
  onDelete 
}: { 
  template: Template; 
  isSystem?: boolean;
  onPreview?: () => void;
  onDelete?: () => void;
}) {
  return (
    <Card className="hover:shadow-md transition-shadow overflow-hidden">
      {/* Preview */}
      <div className="h-48 bg-gradient-to-b from-muted to-muted/50 flex items-center justify-center border-b">
        {template.preview_image ? (
          <img 
            src={template.preview_image} 
            alt={template.name} 
            className="w-full h-full object-cover"
          />
        ) : (
          <LayoutTemplate className="h-16 w-16 text-muted-foreground/30" />
        )}
      </div>
      
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <CardTitle className="text-base">{template.name}</CardTitle>
          {template.category && (
            <Badge variant="outline" className="text-xs">
              {template.category}
            </Badge>
          )}
        </div>
        <CardDescription className="line-clamp-2 text-xs">
          {template.description}
        </CardDescription>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="flex justify-between items-center">
          <span className="text-xs text-muted-foreground">
            Used {template.use_count || 0} times
          </span>
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" onClick={onPreview}>
              <Eye className="h-3 w-3" />
            </Button>
            {!isSystem && onDelete && (
              <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}>
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AddTemplateModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [latexContent, setLatexContent] = useState(DEFAULT_TEMPLATE);
  const [category, setCategory] = useState('professional');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () => templatesApi.create({
      name,
      description,
      latex_content: latexContent,
      category,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      toast({ title: 'Template created' });
      onClose();
    },
    onError: (error: any) => {
      toast({ 
        title: 'Failed to create template', 
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Create Template</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="name">Template Name *</Label>
              <Input 
                id="name" 
                value={name} 
                onChange={(e) => setName(e.target.value)}
                placeholder="My Resume Template"
              />
            </div>
            <div>
              <Label htmlFor="category">Category</Label>
              <Input 
                id="category" 
                value={category} 
                onChange={(e) => setCategory(e.target.value)}
                placeholder="professional, academic, etc."
              />
            </div>
          </div>
          
          <div>
            <Label htmlFor="description">Description</Label>
            <Input 
              id="description" 
              value={description} 
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A clean, professional resume template"
            />
          </div>
          
          <div>
            <Label htmlFor="latexContent">LaTeX Content *</Label>
            <Textarea 
              id="latexContent" 
              value={latexContent} 
              onChange={(e) => setLatexContent(e.target.value)}
              placeholder="\\documentclass{article}..."
              rows={15}
              className="font-mono text-sm"
            />
          </div>
          
          <div className="flex gap-2 justify-end pt-4">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button 
              onClick={() => createMutation.mutate()}
              disabled={!name || !latexContent || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Template'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PreviewModal({ template, onClose }: { template: Template; onClose: () => void }) {
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview');
  const { data: fullTemplate, isLoading } = useQuery({
    queryKey: ['template', template.id],
    queryFn: async () => {
      const res = await templatesApi.get(template.id);
      return res.data;
    },
  });

  // Parse LaTeX to simple HTML preview
  const renderPreview = (latex: string) => {
    // Extract sections and content from LaTeX
    const getName = () => {
      const match = latex.match(/\\textbf\{([^}]+)\}|\\LARGE[^{]*\{([^}]+)\}|<<NAME>>|\{\{NAME\}\}/);
      return match ? (match[1] || match[2] || 'Your Name') : 'Your Name';
    };

    const getSections = () => {
      const sections: { title: string; content: string }[] = [];
      const sectionRegex = /\\section\*?\{([^}]+)\}([\s\S]*?)(?=\\section|\\end\{document\}|$)/g;
      let match;
      while ((match = sectionRegex.exec(latex)) !== null) {
        sections.push({ title: match[1], content: match[2].trim() });
      }
      return sections;
    };

    const sections = getSections();

    return (
      <div className="bg-white text-black p-8 shadow-lg max-w-[8.5in] mx-auto" style={{ fontFamily: 'Times New Roman, serif' }}>
        {/* Header */}
        <div className="text-center border-b-2 border-black pb-4 mb-4">
          <h1 className="text-2xl font-bold">{getName()}</h1>
          <p className="text-sm text-gray-600 mt-1">
            email@example.com | (555) 123-4567 | City, State
          </p>
        </div>

        {/* Sections */}
        {sections.length > 0 ? (
          sections.map((section, idx) => (
            <div key={idx} className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">{section.title}</h2>
              <div className="text-sm text-gray-700">
                {section.content.includes('<<') || section.content.includes('{{') ? (
                  <p className="italic text-gray-500">[Content will be generated based on your projects and job description]</p>
                ) : (
                  <p className="whitespace-pre-wrap">{section.content.slice(0, 200)}...</p>
                )}
              </div>
            </div>
          ))
        ) : (
          <>
            <div className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">Summary</h2>
              <p className="text-sm italic text-gray-500">[Professional summary will appear here]</p>
            </div>
            <div className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">Experience</h2>
              <p className="text-sm italic text-gray-500">[Work experience will appear here]</p>
            </div>
            <div className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">Projects</h2>
              <p className="text-sm italic text-gray-500">[Selected projects will appear here]</p>
            </div>
            <div className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">Skills</h2>
              <p className="text-sm italic text-gray-500">[Technical skills will appear here]</p>
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-background p-6 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
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
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : viewMode === 'preview' ? (
            <div className="overflow-auto max-h-[60vh]">
              {fullTemplate?.latex_content ? renderPreview(fullTemplate.latex_content) : (
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
            <Button variant="outline" onClick={onClose}>Close</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

const DEFAULT_TEMPLATE = `\\documentclass[11pt,a4paper]{article}
\\usepackage[margin=1in]{geometry}
\\usepackage{enumitem}
\\usepackage{hyperref}

\\begin{document}

\\begin{center}
{\\LARGE\\textbf{<<NAME>>}}\\\\[0.5em]
<<EMAIL>> | <<PHONE>> | <<LOCATION>>
\\end{center}

\\section*{Summary}
<<SUMMARY>>

\\section*{Experience}
<<EXPERIENCE>>

\\section*{Projects}
<<PROJECTS>>

\\section*{Education}
<<EDUCATION>>

\\section*{Skills}
<<SKILLS>>

\\end{document}`;

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { templatesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { DEFAULT_TEMPLATE } from './default-template';
import { apiErrorDetail } from '@/lib/api-error';

export function AddTemplateModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [latexContent, setLatexContent] = useState(DEFAULT_TEMPLATE);
  const [category, setCategory] = useState('professional');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () =>
      templatesApi.create({
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
    onError: (error: unknown) => {
      toast({
        title: 'Failed to create template',
        description: apiErrorDetail(error, 'Unknown error'),
        variant: 'destructive',
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-fade-in-up">
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
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!name || !latexContent || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating…' : 'Create Template'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

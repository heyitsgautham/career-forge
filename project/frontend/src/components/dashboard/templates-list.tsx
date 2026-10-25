'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { templatesApi } from '@/lib/api';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LayoutTemplate, Star, Plus } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { AddTemplateModal } from './templates/add-template-modal';
import { TemplateCard } from './templates/template-card';
import { TemplatePreviewModal } from './templates/template-preview-modal';
import type { Template } from './templates/types';

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
    staleTime: 30 * 60 * 1000, // 30 min — templates rarely change
    gcTime: 60 * 60 * 1000, // 60 min
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => templatesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      toast({ title: 'Template deleted' });
    },
    onError: (error: unknown) => {
      toast({
        title: 'Failed to delete template',
        description: apiErrorDetail(error, 'Please try again.'),
        variant: 'destructive',
      });
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
  const systemTemplates = templates?.filter((t) => t.is_system) || [];
  const userTemplates = templates?.filter((t) => !t.is_system) || [];

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
            <Star className="h-5 w-5 text-[hsl(var(--accent))]" />
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
        <TemplatePreviewModal
          template={showPreviewModal}
          onClose={() => setShowPreviewModal(null)}
        />
      )}
    </div>
  );
}

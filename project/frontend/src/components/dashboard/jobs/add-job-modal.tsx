import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { jobsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { Portal } from '@/components/ui/portal';

/** Form for pasting in a job description by hand. */
export function AddJobModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [rawText, setRawText] = useState('');
  const [url, setUrl] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () =>
      jobsApi.create({
        title,
        company,
        raw_text: rawText,
        url: url || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast({ title: 'Job description added' });
      onClose();
    },
    onError: (error: unknown) => {
      toast({
        title: 'Failed to add job description',
        description: apiErrorDetail(error, 'Unknown error'),
        variant: 'destructive',
      });
    },
  });

  return (
    <Portal>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-lg max-h-[90vh] overflow-y-auto animate-fade-in-up">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">Add Job Description</h2>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-4">
            <div>
              <Label htmlFor="title">Job Title *</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Senior Software Engineer"
              />
            </div>

            <div>
              <Label htmlFor="company">Company</Label>
              <Input
                id="company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Google, Microsoft, etc."
              />
            </div>

            <div>
              <Label htmlFor="rawText">Job Description *</Label>
              <Textarea
                id="rawText"
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="Paste the full job description here..."
                rows={10}
              />
            </div>

            <div>
              <Label htmlFor="url">Job URL (optional)</Label>
              <Input
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://careers.company.com/..."
              />
            </div>

            <div className="flex gap-2 justify-end pt-4">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                onClick={() => createMutation.mutate()}
                disabled={!title || !rawText || createMutation.isPending}
              >
                {createMutation.isPending ? 'Adding…' : 'Add Job Description'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Portal>
  );
}

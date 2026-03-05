'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { resumesApi, jobsApi, templatesApi, api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { FileText, Download, Edit, Trash2, Clock, CheckCircle, XCircle, Loader2, Plus, X, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';

interface Resume {
  id: string;
  name: string;
  template_id?: string;
  job_description_id?: string;
  status: 'draft' | 'generating' | 'generated' | 'compiling' | 'compiled' | 'error';
  pdf_path?: string;
  latex_content?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

interface Job {
  id: string;
  title: string;
  company: string;
}

interface Template {
  id: string;
  name: string;
}

const statusConfig = {
  draft: { icon: Clock, color: 'bg-gradient-to-r from-gray-500 to-gray-600', text: 'Draft' },
  generating: { icon: Loader2, color: 'bg-gradient-to-r from-blue-500 to-cyan-500 animate-pulse', text: 'Generating' },
  generated: { icon: CheckCircle, color: 'bg-gradient-to-r from-yellow-500 to-orange-500', text: 'Generated' },
  compiling: { icon: Loader2, color: 'bg-gradient-to-r from-purple-500 to-pink-500 animate-pulse', text: 'Compiling' },
  compiled: { icon: CheckCircle, color: 'bg-gradient-to-r from-green-500 to-emerald-500', text: 'Ready' },
  error: { icon: XCircle, color: 'bg-gradient-to-r from-red-500 to-rose-600', text: 'Error' },
};

export function ResumesList() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: resumes, isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: async () => {
      const res = await resumesApi.list();
      return res.data as Resume[];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => resumesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'Resume deleted' });
    },
  });

  const downloadPdf = async (resume: Resume) => {
    if (!resume.pdf_path) {
      toast({ title: 'PDF not available', variant: 'destructive' });
      return;
    }
    try {
      const response = await api.get(`/resumes/${resume.id}/download`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${resume.name}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      toast({ title: 'Failed to download PDF', variant: 'destructive' });
    }
  };

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-6 bg-muted rounded w-3/4"></div>
              <div className="h-4 bg-muted rounded w-1/2 mt-2"></div>
            </CardHeader>
            <CardContent>
              <div className="h-8 bg-muted rounded w-full"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!resumes || resumes.length === 0) {
    return (
      <>
        <Card className="text-center py-12">
          <CardContent>
            <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No resumes yet</h3>
            <p className="text-muted-foreground mb-4">
              Create your first resume by selecting a template and your best projects.
            </p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Resume
            </Button>
          </CardContent>
        </Card>
        {showCreateModal && <CreateResumeModal onClose={() => setShowCreateModal(false)} />}
      </>
    );
  }

  return (
    <>
      <div className="flex justify-end mb-4">
        <Button onClick={() => setShowCreateModal(true)} className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg">
          <Plus className="h-4 w-4 mr-2" />
          Create Resume
        </Button>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {resumes.map((resume) => {
          const status = statusConfig[resume.status];
          const StatusIcon = status.icon;
          
          return (
            <Card key={resume.id} className="hover:shadow-lg hover:shadow-purple-200 dark:hover:shadow-purple-900 transition-all hover:scale-105 border-l-4 border-l-purple-400">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg">{resume.name}</CardTitle>
                  <Badge 
                    variant="outline" 
                    className={`gap-1 ${resume.status === 'generating' || resume.status === 'compiling' ? 'animate-pulse' : ''}`}
                  >
                    <StatusIcon className={`h-3 w-3 ${resume.status === 'generating' || resume.status === 'compiling' ? 'animate-spin' : ''}`} />
                    {status.text}
                  </Badge>
                </div>
                <CardDescription>
                  Updated {new Date(resume.updated_at).toLocaleDateString()}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {resume.error_message && (
                  <p className="text-sm text-destructive mb-4 line-clamp-2">
                    {resume.error_message}
                  </p>
                )}
                
                <div className="flex justify-between items-center">
                  <div className="flex gap-2">
                    <Link href={`/dashboard/resumes/${resume.id}/edit`}>
                      <Button size="sm" variant="outline" className="gap-1">
                        <Edit className="h-3 w-3" />
                        Edit
                      </Button>
                    </Link>
                    {resume.status === 'compiled' && resume.pdf_path && (
                      <Button size="sm" className="gap-1" onClick={() => downloadPdf(resume)}>
                        <Download className="h-3 w-3" />
                        PDF
                      </Button>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-destructive"
                    onClick={() => deleteMutation.mutate(resume.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      {showCreateModal && <CreateResumeModal onClose={() => setShowCreateModal(false)} />}
    </>
  );
}

function CreateResumeModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [selectedJob, setSelectedJob] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const res = await jobsApi.list();
      return res.data as Job[];
    },
  });

  const { data: templates } = useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const res = await templatesApi.list();
      return res.data as Template[];
    },
  });

  const createMutation = useMutation({
    mutationFn: () => resumesApi.create({
      name,
      job_description_id: selectedJob || undefined,
      template_id: selectedTemplate || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'Resume created' });
      onClose();
    },
    onError: (error: any) => {
      toast({ 
        title: 'Failed to create resume', 
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      // First create the resume
      const createRes = await resumesApi.create({
        name,
        job_description_id: selectedJob || undefined,
        template_id: selectedTemplate || undefined,
      });
      const resume = createRes.data;
      // Then generate it with AI
      await resumesApi.generate(resume.id);
      return resume;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
      toast({ title: 'Resume created and generation started!' });
      onClose();
    },
    onError: (error: any) => {
      toast({ 
        title: 'Failed to generate resume', 
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Create Resume</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="space-y-4">
          <div>
            <Label htmlFor="name">Resume Name *</Label>
            <Input 
              id="name" 
              value={name} 
              onChange={(e) => setName(e.target.value)}
              placeholder="Software Engineer Resume"
            />
          </div>
          
          <div>
            <Label htmlFor="job">Target Job (optional)</Label>
            <select 
              id="job"
              className="w-full border rounded-md p-2"
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value)}
            >
              <option value="">-- Select a job --</option>
              {jobs?.map(job => (
                <option key={job.id} value={job.id}>
                  {job.title} at {job.company}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <Label htmlFor="template">Template (optional)</Label>
            <select 
              id="template"
              className="w-full border rounded-md p-2"
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
            >
              <option value="">-- Select a template --</option>
              {templates?.map(template => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="flex gap-2 justify-end pt-4">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button 
              variant="outline"
              onClick={() => createMutation.mutate()}
              disabled={!name || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Draft'}
            </Button>
            <Button 
              onClick={() => generateMutation.mutate()}
              disabled={!name || !selectedJob || generateMutation.isPending}
            >
              <Sparkles className="h-4 w-4 mr-2" />
              {generateMutation.isPending ? 'Generating...' : 'Generate with AI'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Briefcase, ExternalLink, Trash2, Sparkles, Building2, Plus, X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface JobDescription {
  id: string;
  title: string;
  company: string;
  raw_text: string;
  source_url?: string;
  required_skills: string[];
  preferred_skills: string[];
  keywords: string[];
  is_analyzed: boolean;
  created_at: string;
}

export function JobsList() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobDescription | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const res = await jobsApi.list();
      return res.data as JobDescription[];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => jobsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast({ title: 'Job description deleted' });
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: (id: string) => jobsApi.analyze(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast({ title: 'Job description analyzed' });
    },
    onError: (error: any) => {
      toast({ 
        title: 'Analysis failed', 
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {[1, 2].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-6 bg-muted rounded w-3/4"></div>
              <div className="h-4 bg-muted rounded w-1/2 mt-2"></div>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 flex-wrap">
                <div className="h-5 bg-muted rounded w-20"></div>
                <div className="h-5 bg-muted rounded w-24"></div>
                <div className="h-5 bg-muted rounded w-16"></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <>
        <Card className="text-center py-12">
          <CardContent>
            <Briefcase className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No job descriptions yet</h3>
            <p className="text-muted-foreground mb-4">
              Add job descriptions to tailor your resumes and find matching projects.
            </p>
            <Button onClick={() => setShowAddModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Job Description
            </Button>
          </CardContent>
        </Card>
        {showAddModal && <AddJobModal onClose={() => setShowAddModal(false)} />}
      </>
    );
  }

  return (
    <>
      <div className="flex justify-end mb-4">
        <Button onClick={() => setShowAddModal(true)} className="bg-gradient-to-r from-orange-600 to-pink-600 hover:from-orange-700 hover:to-pink-700 shadow-lg">
          <Plus className="h-4 w-4 mr-2" />
          Add Job Description
        </Button>
      </div>
      
      <div className="grid gap-4 md:grid-cols-2">
        {jobs.map((job) => (
          <Card key={job.id} className="hover:shadow-lg hover:shadow-orange-200 dark:hover:shadow-orange-900 transition-all hover:scale-105 cursor-pointer border-l-4 border-l-orange-400" onClick={() => setSelectedJob(job)}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-lg">{job.title}</CardTitle>
                  <CardDescription className="flex items-center gap-1">
                    <Building2 className="h-3 w-3" />
                    {job.company || 'Unknown Company'}
                  </CardDescription>
                </div>
                <div className="flex gap-1">
                  {job.is_analyzed && (
                    <Badge variant="default">Analyzed</Badge>
                  )}
                  {job.source_url && (
                    <Button variant="ghost" size="icon" asChild>
                      <a href={job.source_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {job.required_skills && job.required_skills.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Required Skills</p>
                    <div className="flex flex-wrap gap-1">
                      {job.required_skills.slice(0, 6).map((skill) => (
                        <Badge key={skill} variant="outline" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                      {job.required_skills.length > 6 && (
                        <Badge variant="outline" className="text-xs">
                          +{job.required_skills.length - 6}
                        </Badge>
                      )}
                    </div>
                  </div>
                )}
                
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {job.raw_text.substring(0, 150)}...
                </p>

                <div className="flex justify-between items-center pt-2">
                  <div className="flex gap-2">
                    {!job.is_analyzed ? (
                      <Button 
                        size="sm" 
                        variant="outline" 
                        className="gap-1"
                        onClick={(e) => {
                          e.stopPropagation();
                          analyzeMutation.mutate(job.id);
                        }}
                        disabled={analyzeMutation.isPending}
                      >
                        <Sparkles className="h-3 w-3" />
                        {analyzeMutation.isPending ? 'Analyzing...' : 'Analyze'}
                      </Button>
                    ) : (
                      <Badge variant="default" className="gap-1">
                        <Sparkles className="h-3 w-3" />
                        Analyzed
                      </Badge>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteMutation.mutate(job.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      
      {selectedJob && <JobDetailsModal job={selectedJob} onClose={() => setSelectedJob(null)} />}
      {showAddModal && <AddJobModal onClose={() => setShowAddModal(false)} />}
    </>
  );
}

function JobDetailsModal({ job, onClose }: { job: JobDescription; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold">{job.title}</h2>
            <p className="text-muted-foreground flex items-center gap-1">
              <Building2 className="h-4 w-4" />
              {job.company || 'Unknown Company'}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="space-y-4">
          {/* Job Description */}
          <div>
            <h3 className="font-semibold text-sm text-muted-foreground mb-2">Job Description</h3>
            <div className="text-sm whitespace-pre-wrap bg-muted p-4 rounded-md">
              {job.raw_text}
            </div>
          </div>
          
          {/* Required Skills */}
          {job.required_skills && job.required_skills.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Required Skills</h3>
              <div className="flex flex-wrap gap-2">
                {job.required_skills.map((skill) => (
                  <Badge key={skill} variant="default">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          {/* Preferred Skills */}
          {job.preferred_skills && job.preferred_skills.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Preferred Skills</h3>
              <div className="flex flex-wrap gap-2">
                {job.preferred_skills.map((skill) => (
                  <Badge key={skill} variant="outline">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          {/* Keywords */}
          {job.keywords && job.keywords.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-2">Keywords</h3>
              <div className="flex flex-wrap gap-2">
                {job.keywords.map((keyword) => (
                  <Badge key={keyword} variant="secondary">
                    {keyword}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          {/* Source URL */}
          {job.source_url && (
            <div>
              <h3 className="font-semibold text-sm text-muted-foreground mb-1">Source URL</h3>
              <a 
                href={job.source_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                {job.source_url}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
          
          <div className="flex justify-end pt-4">
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AddJobModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [rawText, setRawText] = useState('');
  const [url, setUrl] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () => jobsApi.create({
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
    onError: (error: any) => {
      toast({ 
        title: 'Failed to add job description', 
        description: error.response?.data?.detail || 'Unknown error',
        variant: 'destructive' 
      });
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background p-6 rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
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
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button 
              onClick={() => createMutation.mutate()}
              disabled={!title || !rawText || createMutation.isPending}
            >
              {createMutation.isPending ? 'Adding...' : 'Add Job Description'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

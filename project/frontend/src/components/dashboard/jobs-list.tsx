'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Briefcase, Plus } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import { AddJobModal } from './jobs/add-job-modal';
import { JobDescriptionCard } from './jobs/job-description-card';
import { JobDescriptionModal } from './jobs/job-description-modal';
import type { JobDescription } from './jobs/types';

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
    staleTime: 2 * 60 * 1000, // 2 min
    gcTime: 15 * 60 * 1000, // 15 min
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
    onError: (error: unknown) => {
      toast({
        title: 'Analysis failed',
        description: apiErrorDetail(error, 'Unknown error'),
        variant: 'destructive',
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
        <Button
          onClick={() => setShowAddModal(true)}
          className="shadow-md shadow-primary/20 hover:shadow-lg"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Job Description
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {jobs.map((job) => (
          <JobDescriptionCard
            key={job.id}
            job={job}
            analyzing={analyzeMutation.isPending}
            onOpen={() => setSelectedJob(job)}
            onAnalyze={() => analyzeMutation.mutate(job.id)}
            onDelete={() => deleteMutation.mutate(job.id)}
          />
        ))}
      </div>

      {selectedJob && (
        <JobDescriptionModal job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
      {showAddModal && <AddJobModal onClose={() => setShowAddModal(false)} />}
    </>
  );
}

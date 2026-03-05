'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { resumesApi, projectsApi, templatesApi, jobsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { 
  ArrowLeft, 
  ArrowRight,
  Check,
  LayoutTemplate,
  FolderGit2,
  Briefcase,
  User,
  Loader2
} from 'lucide-react';
import Link from 'next/link';

type Step = 'template' | 'projects' | 'job' | 'personal';

export default function NewResumePage() {
  const router = useRouter();
  const { toast } = useToast();
  
  const [step, setStep] = useState<Step>('template');
  const [resumeName, setResumeName] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [personalInfo, setPersonalInfo] = useState({
    name: '',
    email: '',
    phone: '',
    location: '',
    linkedin: '',
    github: '',
    website: '',
  });

  // Fetch templates
  const { data: templates } = useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const res = await templatesApi.list();
      return res.data;
    },
  });

  // Fetch projects
  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await projectsApi.list();
      return res.data;
    },
  });

  // Fetch jobs
  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const res = await jobsApi.list();
      return res.data;
    },
  });

  // Create resume mutation
  const createMutation = useMutation({
    mutationFn: async () => {
      // Create the resume
      const createRes = await resumesApi.create({
        name: resumeName || 'My Resume',
        template_id: selectedTemplateId!,
        job_description_id: selectedJobId || undefined,
        project_ids: selectedProjectIds,
      });
      
      // Generate the content
      const generateRes = await resumesApi.generate(createRes.data.id, {
        personal: personalInfo,
        tailor_to_jd: !!selectedJobId,
      });
      
      return generateRes.data;
    },
    onSuccess: (data) => {
      toast({ title: 'Resume created!', description: 'Redirecting to editor...' });
      router.push(`/dashboard/resumes/${data.id}/edit`);
    },
    onError: () => {
      toast({ 
        title: 'Error', 
        description: 'Failed to create resume.',
        variant: 'destructive'
      });
    },
  });

  const steps: { key: Step; title: string; icon: React.ReactNode }[] = [
    { key: 'template', title: 'Template', icon: <LayoutTemplate className="h-4 w-4" /> },
    { key: 'projects', title: 'Projects', icon: <FolderGit2 className="h-4 w-4" /> },
    { key: 'job', title: 'Job (Optional)', icon: <Briefcase className="h-4 w-4" /> },
    { key: 'personal', title: 'Personal Info', icon: <User className="h-4 w-4" /> },
  ];

  const currentStepIndex = steps.findIndex(s => s.key === step);
  
  const canProceed = () => {
    switch (step) {
      case 'template':
        return !!selectedTemplateId;
      case 'projects':
        return selectedProjectIds.length > 0;
      case 'job':
        return true; // Optional
      case 'personal':
        return personalInfo.name && personalInfo.email;
    }
  };

  const handleNext = () => {
    const nextIndex = currentStepIndex + 1;
    if (nextIndex < steps.length) {
      setStep(steps[nextIndex].key);
    }
  };

  const handleBack = () => {
    const prevIndex = currentStepIndex - 1;
    if (prevIndex >= 0) {
      setStep(steps[prevIndex].key);
    }
  };

  const toggleProject = (id: string) => {
    setSelectedProjectIds(prev => 
      prev.includes(id) 
        ? prev.filter(p => p !== id) 
        : [...prev, id]
    );
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card px-4 py-3 flex items-center gap-4">
        <Link href="/dashboard">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="font-semibold">Create New Resume</h1>
          <p className="text-xs text-muted-foreground">
            Step {currentStepIndex + 1} of {steps.length}
          </p>
        </div>
      </header>

      {/* Progress Steps */}
      <div className="border-b bg-card">
        <div className="container max-w-4xl mx-auto py-4">
          <div className="flex justify-between">
            {steps.map((s, i) => (
              <div 
                key={s.key}
                className={`flex items-center gap-2 ${
                  i <= currentStepIndex ? 'text-primary' : 'text-muted-foreground'
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                  i < currentStepIndex 
                    ? 'bg-primary border-primary text-primary-foreground' 
                    : i === currentStepIndex
                      ? 'border-primary'
                      : 'border-muted'
                }`}>
                  {i < currentStepIndex ? <Check className="h-4 w-4" /> : s.icon}
                </div>
                <span className="text-sm font-medium hidden sm:inline">{s.title}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container max-w-4xl mx-auto py-8">
        {step === 'template' && (
          <div>
            <h2 className="text-2xl font-bold mb-2">Choose a Template</h2>
            <p className="text-muted-foreground mb-6">
              Select a LaTeX template for your resume. You can customize it later.
            </p>
            <div className="grid gap-4 md:grid-cols-3">
              {templates?.map((template: any) => (
                <Card 
                  key={template.id}
                  className={`cursor-pointer transition-all ${
                    selectedTemplateId === template.id 
                      ? 'ring-2 ring-primary' 
                      : 'hover:shadow-md'
                  }`}
                  onClick={() => setSelectedTemplateId(template.id)}
                >
                  <div className="aspect-[8.5/11] bg-muted flex items-center justify-center">
                    <LayoutTemplate className="h-12 w-12 text-muted-foreground/30" />
                  </div>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">{template.name}</CardTitle>
                    <CardDescription className="text-xs line-clamp-2">
                      {template.description}
                    </CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          </div>
        )}

        {step === 'projects' && (
          <div>
            <h2 className="text-2xl font-bold mb-2">Select Projects</h2>
            <p className="text-muted-foreground mb-6">
              Choose the projects to include in your resume. Selected: {selectedProjectIds.length}
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              {projects?.map((project: any) => (
                <Card 
                  key={project.id}
                  className={`cursor-pointer transition-all ${
                    selectedProjectIds.includes(project.id) 
                      ? 'ring-2 ring-primary' 
                      : 'hover:shadow-md'
                  }`}
                  onClick={() => toggleProject(project.id)}
                >
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <CardTitle className="text-base">{project.title}</CardTitle>
                      {selectedProjectIds.includes(project.id) && (
                        <Check className="h-5 w-5 text-primary" />
                      )}
                    </div>
                    <CardDescription className="line-clamp-2">
                      {project.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="flex flex-wrap gap-1">
                      {project.technologies?.slice(0, 4).map((tech: string) => (
                        <span key={tech} className="text-xs bg-muted px-2 py-0.5 rounded">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {step === 'job' && (
          <div>
            <h2 className="text-2xl font-bold mb-2">Target Job Description (Optional)</h2>
            <p className="text-muted-foreground mb-6">
              Select a job description to tailor your resume, or skip this step.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <Card 
                className={`cursor-pointer transition-all ${
                  selectedJobId === null ? 'ring-2 ring-primary' : 'hover:shadow-md'
                }`}
                onClick={() => setSelectedJobId(null)}
              >
                <CardHeader>
                  <CardTitle className="text-base">No specific job</CardTitle>
                  <CardDescription>
                    Create a general-purpose resume without tailoring to a specific role.
                  </CardDescription>
                </CardHeader>
              </Card>
              {jobs?.map((job: any) => (
                <Card 
                  key={job.id}
                  className={`cursor-pointer transition-all ${
                    selectedJobId === job.id ? 'ring-2 ring-primary' : 'hover:shadow-md'
                  }`}
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-base">{job.title}</CardTitle>
                        <CardDescription>{job.company}</CardDescription>
                      </div>
                      {selectedJobId === job.id && (
                        <Check className="h-5 w-5 text-primary" />
                      )}
                    </div>
                  </CardHeader>
                </Card>
              ))}
            </div>
          </div>
        )}

        {step === 'personal' && (
          <div>
            <h2 className="text-2xl font-bold mb-2">Personal Information</h2>
            <p className="text-muted-foreground mb-6">
              Enter your contact information for the resume header.
            </p>
            
            <div className="space-y-4 max-w-md">
              <div>
                <Label>Resume Name</Label>
                <Input 
                  value={resumeName}
                  onChange={(e) => setResumeName(e.target.value)}
                  placeholder="e.g., Software Engineer Resume"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Full Name *</Label>
                  <Input 
                    value={personalInfo.name}
                    onChange={(e) => setPersonalInfo(p => ({ ...p, name: e.target.value }))}
                    placeholder="John Doe"
                  />
                </div>
                <div>
                  <Label>Email *</Label>
                  <Input 
                    type="email"
                    value={personalInfo.email}
                    onChange={(e) => setPersonalInfo(p => ({ ...p, email: e.target.value }))}
                    placeholder="john@example.com"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Phone</Label>
                  <Input 
                    value={personalInfo.phone}
                    onChange={(e) => setPersonalInfo(p => ({ ...p, phone: e.target.value }))}
                    placeholder="+1 (555) 123-4567"
                  />
                </div>
                <div>
                  <Label>Location</Label>
                  <Input 
                    value={personalInfo.location}
                    onChange={(e) => setPersonalInfo(p => ({ ...p, location: e.target.value }))}
                    placeholder="San Francisco, CA"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>LinkedIn</Label>
                  <Input 
                    value={personalInfo.linkedin}
                    onChange={(e) => setPersonalInfo(p => ({ ...p, linkedin: e.target.value }))}
                    placeholder="linkedin.com/in/johndoe"
                  />
                </div>
                <div>
                  <Label>GitHub</Label>
                  <Input 
                    value={personalInfo.github}
                    onChange={(e) => setPersonalInfo(p => ({ ...p, github: e.target.value }))}
                    placeholder="github.com/johndoe"
                  />
                </div>
              </div>
              
              <div>
                <Label>Website</Label>
                <Input 
                  value={personalInfo.website}
                  onChange={(e) => setPersonalInfo(p => ({ ...p, website: e.target.value }))}
                  placeholder="johndoe.dev"
                />
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-8">
          <Button 
            variant="outline" 
            onClick={handleBack}
            disabled={currentStepIndex === 0}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          
          {currentStepIndex < steps.length - 1 ? (
            <Button 
              onClick={handleNext}
              disabled={!canProceed()}
            >
              Next
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button 
              onClick={() => createMutation.mutate()}
              disabled={!canProceed() || createMutation.isPending}
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              Create Resume
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

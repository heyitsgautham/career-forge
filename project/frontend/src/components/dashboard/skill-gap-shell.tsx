'use client';

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Target, BookOpen, ArrowRight, Loader2 } from 'lucide-react';
import { skillGapApi, roadmapApi, type SkillGapReport, type Roadmap } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { ROLE_ICONS } from './skill-gap/helpers';
import { GapResults } from './skill-gap/gap-results';
import { LearningRoadmap } from './skill-gap/learning-roadmap';
import { apiErrorDetail } from '@/lib/api-error';

/* ─── Main component ─────────────────────────────────────────────────────── */
export function SkillGapShell() {
  const { toast } = useToast();

  // State
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [report, setReport] = useState<SkillGapReport | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [generatingRoadmap, setGeneratingRoadmap] = useState(false);
  const [roadmapOpen, setRoadmapOpen] = useState(true);

  // Load roles via React Query (static data, long cache)
  const { data: roles = [], isLoading: loadingRoles } = useQuery({
    queryKey: ['skill-gap-roles'],
    queryFn: async () => {
      const res = await skillGapApi.getRoles();
      return res.data.roles || [];
    },
    staleTime: 60 * 60 * 1000, // 1 hour — static data
    gcTime: 2 * 60 * 60 * 1000, // 2 hours
  });

  // Run analysis
  const handleAnalyse = useCallback(async () => {
    if (!selectedRole) return;
    setAnalysing(true);
    setReport(null);
    setRoadmap(null);

    try {
      const res = await skillGapApi.analyse(selectedRole);
      if (res.data && res.data.reportId) {
        setReport(res.data);
        toast({
          title: 'Analysis complete!',
          description: `Overall fit: ${res.data.overallFitPercent}%`,
        });
      } else {
        toast({
          title: 'No results',
          description: 'Could not compute gap analysis.',
          variant: 'destructive',
        });
      }
    } catch (err: unknown) {
      toast({
        title: 'Analysis failed',
        description: apiErrorDetail(err, 'An error occurred.'),
        variant: 'destructive',
      });
    } finally {
      setAnalysing(false);
    }
  }, [selectedRole, toast]);

  // Generate roadmap
  const handleGenerateRoadmap = useCallback(async () => {
    if (!selectedRole || !report) return;
    setGeneratingRoadmap(true);

    try {
      const res = await roadmapApi.generate(selectedRole, report.reportId);
      if (res.data && res.data.roadmapId) {
        setRoadmap(res.data);
        setRoadmapOpen(true);
        toast({ title: 'Roadmap generated!' });
      }
    } catch (err: unknown) {
      toast({
        title: 'Roadmap generation failed',
        description: apiErrorDetail(err, 'An error occurred.'),
        variant: 'destructive',
      });
    } finally {
      setGeneratingRoadmap(false);
    }
  }, [selectedRole, report, toast]);

  // Mark milestone complete
  const handleMarkComplete = useCallback(
    async (week: number) => {
      if (!roadmap) return;
      try {
        const res = await roadmapApi.markComplete(roadmap.roadmapId, week);
        if (res.data) {
          setRoadmap(res.data);
          toast({ title: `Week ${week} completed!` });
        }
      } catch {
        toast({ title: 'Failed to update milestone', variant: 'destructive' });
      }
    },
    [roadmap, toast]
  );

  // ─── Radar chart data ─────────────────────────────────────────────────
  const radarData = report
    ? report.gaps.map((g) => ({
        domain: g.domain.length > 18 ? g.domain.slice(0, 16) + '…' : g.domain,
        fullDomain: g.domain,
        user: g.userScore,
        benchmark: g.requiredScore,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Skill Gap Analysis</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Identify gaps between your current skills and target roles — powered by
          Amazon&nbsp;Bedrock
        </p>
      </div>

      {/* ─── Role Picker ─────────────────────────────────────────────────── */}
      <div>
        <h3 className="text-sm font-medium mb-3">Select a Target Role</h3>
        {loadingRoles ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading roles…
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {roles.map((role) => (
              <button
                key={role.roleId}
                onClick={() => setSelectedRole(role.roleId)}
                className={`group relative flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-all duration-200 hover:border-primary/50 hover:bg-primary/5 hover:-translate-y-0.5 hover:shadow-sm ${
                  selectedRole === role.roleId
                    ? 'border-primary bg-primary/10 ring-2 ring-primary/20 shadow-sm'
                    : 'border-border'
                }`}
              >
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-full transition-colors ${
                    selectedRole === role.roleId
                      ? 'bg-primary/20 text-primary'
                      : 'bg-muted text-muted-foreground group-hover:text-primary'
                  }`}
                >
                  {ROLE_ICONS[role.icon] || <Target className="h-5 w-5" aria-hidden="true" />}
                </span>
                <span className="text-xs font-medium leading-tight">{role.role}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Analyse button */}
      <Button
        onClick={handleAnalyse}
        disabled={!selectedRole || analysing}
        className="w-full sm:w-auto gap-2"
        aria-label="Run Skill Gap Analysis"
      >
        {analysing ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <BookOpen className="h-4 w-4" aria-hidden="true" />
        )}
        {analysing ? 'Analysing…' : 'Analyse Skill Gap'}
        {!analysing && <ArrowRight className="h-4 w-4 ml-1" aria-hidden="true" />}
      </Button>

      {/* ─── Results ─────────────────────────────────────────────────────── */}
      {report && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <GapResults report={report} radarData={radarData} />

          {/* ─── Generate Roadmap Button ──────────────────────────────────── */}
          {!roadmap && (
            <Button
              onClick={handleGenerateRoadmap}
              disabled={generatingRoadmap}
              className="w-full sm:w-auto gap-2"
              variant="outline"
            >
              {generatingRoadmap ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <BookOpen className="h-4 w-4" aria-hidden="true" />
              )}
              {generatingRoadmap ? 'Generating Roadmap…' : 'Generate Learning Roadmap'}
            </Button>
          )}

          {/* ─── LearnWeave Roadmap ──────────────────────────────────────── */}
          {roadmap && (
            <LearningRoadmap
              roadmap={roadmap}
              open={roadmapOpen}
              onToggle={() => setRoadmapOpen(!roadmapOpen)}
              onMarkComplete={handleMarkComplete}
            />
          )}
        </div>
      )}
    </div>
  );
}

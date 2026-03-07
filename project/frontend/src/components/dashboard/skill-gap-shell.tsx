'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Target, BookOpen, ArrowRight, TrendingUp, CheckCircle2,
  Loader2, ExternalLink, ChevronDown, ChevronUp, Clock,
  Server, Monitor, Layers, Brain, BarChart3, Cloud, Smartphone, Shield,
} from 'lucide-react';
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend,
} from 'recharts';
import {
  skillGapApi, roadmapApi,
  type Role, type SkillGapReport, type SkillGap, type Roadmap,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

/* ─── Icon map for roles ─────────────────────────────────────────────────── */
const ROLE_ICONS: Record<string, React.ReactNode> = {
  Server: <Server className="h-5 w-5" aria-hidden="true" />,
  Monitor: <Monitor className="h-5 w-5" aria-hidden="true" />,
  Layers: <Layers className="h-5 w-5" aria-hidden="true" />,
  Brain: <Brain className="h-5 w-5" aria-hidden="true" />,
  BarChart3: <BarChart3 className="h-5 w-5" aria-hidden="true" />,
  Cloud: <Cloud className="h-5 w-5" aria-hidden="true" />,
  Smartphone: <Smartphone className="h-5 w-5" aria-hidden="true" />,
  Shield: <Shield className="h-5 w-5" aria-hidden="true" />,
};

/* ─── Priority color helper ──────────────────────────────────────────────── */
function priorityColor(p: string) {
  if (p === 'high') return 'bg-red-500/10 text-red-600 border-red-500/20';
  if (p === 'medium') return 'bg-amber-500/10 text-amber-600 border-amber-500/20';
  return 'bg-green-500/10 text-green-600 border-green-500/20';
}

/* ─── Main component ─────────────────────────────────────────────────────── */
export function SkillGapShell() {
  const { toast } = useToast();

  // State
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [report, setReport] = useState<SkillGapReport | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loadingRoles, setLoadingRoles] = useState(true);
  const [analysing, setAnalysing] = useState(false);
  const [generatingRoadmap, setGeneratingRoadmap] = useState(false);
  const [roadmapOpen, setRoadmapOpen] = useState(true);

  // Load roles on mount
  useEffect(() => {
    const load = async () => {
      try {
        const res = await skillGapApi.getRoles();
        setRoles(res.data.roles || []);
      } catch {
        toast({ title: 'Failed to load roles', variant: 'destructive' });
      } finally {
        setLoadingRoles(false);
      }
    };
    load();
  }, [toast]);

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
        toast({ title: 'Analysis complete!', description: `Overall fit: ${res.data.overallFitPercent}%` });
      } else {
        toast({ title: 'No results', description: 'Could not compute gap analysis.', variant: 'destructive' });
      }
    } catch (err: any) {
      toast({
        title: 'Analysis failed',
        description: err?.response?.data?.detail || 'An error occurred.',
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
    } catch (err: any) {
      toast({
        title: 'Roadmap generation failed',
        description: err?.response?.data?.detail || 'An error occurred.',
        variant: 'destructive',
      });
    } finally {
      setGeneratingRoadmap(false);
    }
  }, [selectedRole, report, toast]);

  // Mark milestone complete
  const handleMarkComplete = useCallback(async (week: number) => {
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
  }, [roadmap, toast]);

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
          Identify gaps between your current skills and target roles — powered by Amazon&nbsp;Bedrock
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
                className={`group relative flex flex-col items-center gap-2 rounded-lg border p-4 text-center transition-all hover:border-primary/50 hover:bg-primary/5 ${
                  selectedRole === role.roleId
                    ? 'border-primary bg-primary/10 ring-2 ring-primary/20'
                    : 'border-border'
                }`}
              >
                <span className={`flex h-10 w-10 items-center justify-center rounded-full transition-colors ${
                  selectedRole === role.roleId
                    ? 'bg-primary/20 text-primary'
                    : 'bg-muted text-muted-foreground group-hover:text-primary'
                }`}>
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
          {/* Overall fit + Radar */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Radar chart */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="h-4 w-4 text-primary" aria-hidden="true" />
                  Skill Radar — {report.roleName}
                </CardTitle>
                <CardDescription>
                  Your profile (blue) vs. role benchmark (orange)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div aria-label="Skill gap radar chart" role="img">
                  <ResponsiveContainer width="100%" height={320}>
                    <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                      <PolarGrid strokeDasharray="3 3" />
                      <PolarAngleAxis
                        dataKey="domain"
                        tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                      />
                      <PolarRadiusAxis
                        angle={90}
                        domain={[0, 100]}
                        tick={{ fontSize: 10 }}
                      />
                      <Radar
                        name="Your Score"
                        dataKey="user"
                        stroke="hsl(var(--primary))"
                        fill="hsl(var(--primary))"
                        fillOpacity={0.25}
                        animationDuration={800}
                      />
                      <Radar
                        name="Benchmark"
                        dataKey="benchmark"
                        stroke="hsl(25 95% 53%)"
                        fill="hsl(25 95% 53%)"
                        fillOpacity={0.1}
                        strokeDasharray="5 5"
                        animationDuration={800}
                        animationBegin={200}
                      />
                      <Legend />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Fit summary */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" aria-hidden="true" />
                  Overall Fit
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Big percentage */}
                <div className="flex items-baseline gap-2">
                  <span
                    className="text-5xl font-bold tracking-tight"
                    style={{ fontVariantNumeric: 'tabular-nums' }}
                  >
                    {report.overallFitPercent}%
                  </span>
                  <span className="text-sm text-muted-foreground">match to {report.roleName}</span>
                </div>

                {/* Progress bar */}
                <div className="w-full h-3 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-1000"
                    style={{ width: `${report.overallFitPercent}%` }}
                  />
                </div>

                <p className="text-xs text-muted-foreground">
                  Based on {report.projectCount} GitHub project{report.projectCount !== 1 ? 's' : ''} analysed by AI
                </p>

                {/* Missing skills badges */}
                <div>
                  <p className="text-xs font-medium mb-2">Priority Gaps</p>
                  <div className="flex flex-wrap gap-1.5">
                    {report.gaps
                      .filter((g) => g.priority === 'high' || g.priority === 'medium')
                      .map((g) => (
                        <Badge
                          key={g.domain}
                          variant="outline"
                          className={`text-xs ${priorityColor(g.priority)}`}
                        >
                          {g.domain} (−{g.gap})
                        </Badge>
                      ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Gap table */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Gap Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="py-2 pr-4 font-medium text-muted-foreground">Domain</th>
                      <th className="py-2 pr-4 font-medium text-muted-foreground text-right">Your Score</th>
                      <th className="py-2 pr-4 font-medium text-muted-foreground text-right">Required</th>
                      <th className="py-2 pr-4 font-medium text-muted-foreground text-right">Gap</th>
                      <th className="py-2 font-medium text-muted-foreground">Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.gaps.map((g) => (
                      <tr key={g.domain} className="border-b last:border-0">
                        <td className="py-2.5 pr-4 font-medium">{g.domain}</td>
                        <td className="py-2.5 pr-4 text-right" style={{ fontVariantNumeric: 'tabular-nums' }}>
                          {g.userScore}
                        </td>
                        <td className="py-2.5 pr-4 text-right" style={{ fontVariantNumeric: 'tabular-nums' }}>
                          {g.requiredScore}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-medium" style={{ fontVariantNumeric: 'tabular-nums' }}>
                          {g.gap > 0 ? `−${g.gap}` : '0'}
                        </td>
                        <td className="py-2.5">
                          <Badge variant="outline" className={`text-xs ${priorityColor(g.priority)}`}>
                            {g.priority}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

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
            <Card className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-primary" aria-hidden="true" />
                    Learning Roadmap — {roadmap.roleName}
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setRoadmapOpen(!roadmapOpen)}
                    aria-label={roadmapOpen ? 'Collapse roadmap' : 'Expand roadmap'}
                  >
                    {roadmapOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </Button>
                </div>
                {/* Progress bar */}
                <div className="space-y-1 mt-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {roadmap.completedWeeks} of {roadmap.totalWeeks} weeks completed
                    </span>
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {roadmap.totalWeeks > 0
                        ? Math.round((roadmap.completedWeeks / roadmap.totalWeeks) * 100)
                        : 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-500"
                      style={{
                        width: `${roadmap.totalWeeks > 0
                          ? (roadmap.completedWeeks / roadmap.totalWeeks) * 100
                          : 0}%`,
                      }}
                    />
                  </div>
                </div>
              </CardHeader>

              {roadmapOpen && (
                <CardContent className="pt-0">
                  <div className="relative space-y-0">
                    {/* Timeline line */}
                    <div className="absolute left-[18px] top-2 bottom-2 w-0.5 bg-border" />

                    {roadmap.weeks.map((week) => {
                      const done = !!week.completedAt;
                      return (
                        <div key={week.week} className="relative flex gap-4 pb-6 last:pb-0">
                          {/* Timeline dot */}
                          <div className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 ${
                            done
                              ? 'border-green-500 bg-green-500/10 text-green-600'
                              : 'border-border bg-background text-muted-foreground'
                          }`}>
                            {done ? (
                              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                            ) : (
                              <span className="text-xs font-bold">{week.week}</span>
                            )}
                          </div>

                          {/* Card */}
                          <div className={`flex-1 rounded-lg border p-4 ${done ? 'bg-muted/30' : ''}`}>
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <h4 className={`font-medium ${done ? 'line-through text-muted-foreground' : ''}`}>
                                  Week {week.week}: {week.projectTitle}
                                </h4>
                                {week.description && (
                                  <p className="text-xs text-muted-foreground mt-1">{week.description}</p>
                                )}
                              </div>
                              {!done && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="shrink-0 text-xs gap-1"
                                  onClick={() => handleMarkComplete(week.week)}
                                >
                                  <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                                  Complete
                                </Button>
                              )}
                              {done && (
                                <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20 text-xs">
                                  Done
                                </Badge>
                              )}
                            </div>

                            {/* Tech stack chips */}
                            <div className="flex flex-wrap gap-1.5 mt-3">
                              {week.techStack.map((tech) => (
                                <Badge
                                  key={tech}
                                  variant="secondary"
                                  className="text-xs"
                                >
                                  {tech}
                                </Badge>
                              ))}
                              <Badge variant="outline" className="text-xs gap-1">
                                <Clock className="h-3 w-3" aria-hidden="true" />
                                ~{week.estimatedHours}h
                              </Badge>
                            </div>

                            {/* Resources */}
                            {week.resources.length > 0 && (
                              <div className="mt-3 space-y-1">
                                <p className="text-xs font-medium text-muted-foreground">Resources</p>
                                {week.resources.map((r, i) => (
                                  <a
                                    key={i}
                                    href={r.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    aria-label={`${r.title} — opens in new tab`}
                                    className="flex items-center gap-1.5 text-xs text-primary hover:underline"
                                  >
                                    <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                                    {r.title}
                                  </a>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

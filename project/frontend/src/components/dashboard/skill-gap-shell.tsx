'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Target, BookOpen, ArrowRight, Loader2 } from 'lucide-react';
import { ROLE_ICONS } from './skill-gap/helpers';
import { GapResults } from './skill-gap/gap-results';
import { LearningRoadmap } from './skill-gap/learning-roadmap';
import { toRadarData } from './skill-gap/radar-data';
import { useSkillGap } from './skill-gap/use-skill-gap';

export function SkillGapShell() {
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const {
    roles,
    loadingRoles,
    report,
    roadmap,
    analysing,
    generatingRoadmap,
    roadmapOpen,
    toggleRoadmap,
    analyse,
    generateRoadmap,
    markWeekComplete,
  } = useSkillGap();

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
        onClick={() => analyse(selectedRole)}
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
          <GapResults report={report} radarData={toRadarData(report.gaps)} />

          {/* ─── Generate Roadmap Button ──────────────────────────────────── */}
          {!roadmap && (
            <Button
              onClick={generateRoadmap}
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
              onToggle={toggleRoadmap}
              onMarkComplete={markWeekComplete}
            />
          )}
        </div>
      )}
    </div>
  );
}

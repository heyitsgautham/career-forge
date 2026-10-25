'use client';

import { useState } from 'react';
import { Map } from 'lucide-react';
import { DAY_COLORS } from './project-roadmap/constants';
import { DuolingoPath } from './project-roadmap/duolingo-path';
import { DayDetailModal } from './project-roadmap/day-detail-modal';
import { ProjectPicker } from './project-roadmap/project-picker';
import { DomainForm } from './project-roadmap/domain-form';
import { RoadmapHistory } from './project-roadmap/roadmap-history';
import { useProjectRoadmap } from './project-roadmap/use-project-roadmap';

export function ProjectRoadmapShell() {
  const [domain, setDomain] = useState('');
  const {
    step,
    setStep,
    suggestions,
    suggesting,
    activeRoadmap,
    planning,
    selectedDay,
    setSelectedDay,
    completing,
    unlocking,
    deleting,
    history,
    suggest,
    pick,
    completeDay,
    loadRoadmap,
    unlockAll,
    deleteRoadmap,
    closeRoadmap,
  } = useProjectRoadmap();

  /* ─── STEP 3: S-curve path ─────────────────────────────────────────────── */
  if (step === 'path' && activeRoadmap) {
    return (
      <>
        <DuolingoPath
          roadmap={activeRoadmap}
          onDayClick={(day) => setSelectedDay(day)}
          onBack={closeRoadmap}
          onUnlockAll={unlockAll}
          unlocking={unlocking}
        />
        {selectedDay &&
          activeRoadmap &&
          (() => {
            const dayIdx = selectedDay.day - 1;
            const prevDone = activeRoadmap.days.slice(0, dayIdx).every((d) => d.completedAt);
            return (
              <DayDetailModal
                day={selectedDay}
                color={DAY_COLORS[(selectedDay.day - 1) % DAY_COLORS.length]}
                canComplete={prevDone}
                onClose={() => setSelectedDay(null)}
                onComplete={() => completeDay(selectedDay.day)}
                completing={completing}
              />
            );
          })()}
      </>
    );
  }

  /* ─── STEP 2: Pick project ─────────────────────────────────────────────── */
  if (step === 'pick' && suggestions) {
    return (
      <ProjectPicker
        suggestions={suggestions}
        onPick={pick}
        picking={planning}
        onBack={() => setStep('form')}
      />
    );
  }

  /* ─── STEP 1: Domain + hours form ──────────────────────────────────────── */
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Hero */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-2">
          <Map className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-3xl font-bold tracking-tight">Project Roadmap</h2>
        <p className="text-muted-foreground max-w-lg mx-auto">
          Choose a domain and we&apos;ll suggest 3 real-world projects — pick one and get a
          day-by-day build plan!
        </p>
      </div>

      <DomainForm
        domain={domain}
        suggesting={suggesting}
        onDomainChange={setDomain}
        onSuggest={() => suggest(domain)}
      />

      <RoadmapHistory
        history={history}
        deleting={deleting}
        onOpen={loadRoadmap}
        onDelete={deleteRoadmap}
      />
    </div>
  );
}

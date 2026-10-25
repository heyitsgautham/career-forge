import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { makeLearningRoadmap, makeReport } from '@/test/skill-gap';
import { GapResults } from '../gap-results';
import { priorityColor } from '../helpers';
import { LearningRoadmap } from '../learning-roadmap';
import { toRadarData } from '../radar-data';

// Recharts measures its container, which jsdom cannot do, so render the chart as a plain box.
vi.mock('recharts', async (importOriginal) => {
  const original = await importOriginal<typeof import('recharts')>();
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="chart">{children}</div>
    ),
  };
});

describe('toRadarData', () => {
  it('shortens long domain names and keeps the full name', () => {
    expect(toRadarData(makeReport().gaps)).toEqual([
      {
        domain: 'Distributed Syst…',
        fullDomain: 'Distributed Systems and Messaging',
        user: 40,
        benchmark: 80,
      },
      { domain: 'APIs', fullDomain: 'APIs', user: 75, benchmark: 80 },
    ]);
  });
});

describe('priorityColor', () => {
  it('maps each priority to its own colour', () => {
    expect(priorityColor('high')).toContain('destructive');
    expect(priorityColor('medium')).toContain('accent');
    expect(priorityColor('low')).toContain('success');
  });
});

describe('GapResults', () => {
  it('shows the fit, the project count and every gap', () => {
    const report = makeReport({ projectCount: 1 });
    render(<GapResults report={report} radarData={toRadarData(report.gaps)} />);
    expect(screen.getByText('62%')).toBeInTheDocument();
    expect(screen.getByText(/Based on 1 GitHub project/)).toHaveTextContent(
      'Based on 1 GitHub project analysed by AI'
    );
    expect(screen.getAllByText('Distributed Systems and Messaging').length).toBeGreaterThan(0);
    expect(screen.getByText('APIs')).toBeInTheDocument();
  });
});

describe('LearningRoadmap', () => {
  it('shows progress and marks an open week complete', async () => {
    const onMarkComplete = vi.fn();
    render(
      <LearningRoadmap
        roadmap={makeLearningRoadmap(1)}
        open
        onToggle={() => {}}
        onMarkComplete={onMarkComplete}
      />
    );
    expect(screen.getByText('1 of 2 weeks completed')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.getByText('Week 2: Queue worker 2')).toBeInTheDocument();

    const buttons = screen.getAllByRole('button', { name: /Mark|Complete/i });
    await userEvent.click(buttons[buttons.length - 1]);
    expect(onMarkComplete).toHaveBeenCalledWith(2);
  });

  it('collapses its weeks', async () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <LearningRoadmap
        roadmap={makeLearningRoadmap()}
        open
        onToggle={onToggle}
        onMarkComplete={() => {}}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: 'Collapse roadmap' }));
    expect(onToggle).toHaveBeenCalledOnce();

    rerender(
      <LearningRoadmap
        roadmap={makeLearningRoadmap()}
        open={false}
        onToggle={onToggle}
        onMarkComplete={() => {}}
      />
    );
    expect(screen.queryByText('Week 1: Queue worker 1')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Expand roadmap' })).toBeInTheDocument();
  });
});

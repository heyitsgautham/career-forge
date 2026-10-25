import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DAY_COLORS, progressPercent } from '../constants';
import { DayDetailModal } from '../day-detail-modal';
import { DomainForm } from '../domain-form';
import { DuolingoPath } from '../duolingo-path';
import { ProjectPicker } from '../project-picker';
import { RoadmapHistory } from '../roadmap-history';
import { SUGGESTION, makeDay, makeRoadmap } from '@/test/roadmaps';

describe('DomainForm', () => {
  it('fills the domain from a chip and suggests on Enter', async () => {
    const onDomainChange = vi.fn();
    const onSuggest = vi.fn();
    const { rerender } = render(
      <DomainForm
        domain=""
        suggesting={false}
        onDomainChange={onDomainChange}
        onSuggest={onSuggest}
      />
    );
    expect(screen.getByRole('button', { name: /Suggest 3 Projects/ })).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Machine Learning' }));
    expect(onDomainChange).toHaveBeenCalledWith('Machine Learning');

    rerender(
      <DomainForm
        domain="Machine Learning"
        suggesting={false}
        onDomainChange={onDomainChange}
        onSuggest={onSuggest}
      />
    );
    await userEvent.type(screen.getByPlaceholderText(/Web Development/), '{Enter}');
    await userEvent.click(screen.getByRole('button', { name: /Suggest 3 Projects/ }));
    expect(onSuggest).toHaveBeenCalledTimes(2);
  });

  it('shows progress while suggesting', () => {
    render(<DomainForm domain="Web" suggesting onDomainChange={() => {}} onSuggest={() => {}} />);
    expect(screen.getByRole('button', { name: /Finding projects/ })).toBeDisabled();
  });
});

describe('RoadmapHistory', () => {
  it('renders nothing without saved roadmaps', () => {
    const { container } = render(
      <RoadmapHistory history={[]} deleting={null} onOpen={() => {}} onDelete={() => {}} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('shows progress, opens a roadmap and deletes without opening it', async () => {
    const onOpen = vi.fn();
    const onDelete = vi.fn();
    render(
      <RoadmapHistory
        history={[makeRoadmap(2)]}
        deleting={null}
        onOpen={onOpen}
        onDelete={onDelete}
      />
    );
    expect(screen.getByText('Previous Roadmaps (1)')).toBeInTheDocument();
    expect(screen.getByText('2/7 days • Backend Development')).toBeInTheDocument();
    expect(screen.getByText('29%')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button'));
    expect(onDelete).toHaveBeenCalledWith('pr1');
    expect(onOpen).not.toHaveBeenCalled();

    await userEvent.click(screen.getByText('Job board API'));
    expect(onOpen).toHaveBeenCalledWith('pr1');
  });

  it('shows 0% for a roadmap that has no days', () => {
    // Regression: dividing by totalDays rendered "NaN%" and a NaN-width bar.
    render(
      <RoadmapHistory
        history={[makeRoadmap(0, { days: [], totalDays: 0 })]}
        deleting={null}
        onOpen={() => {}}
        onDelete={() => {}}
      />
    );
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.queryByText('NaN%')).not.toBeInTheDocument();
  });

  it('disables the delete button while that roadmap is deleting', () => {
    render(
      <RoadmapHistory
        history={[makeRoadmap()]}
        deleting="pr1"
        onOpen={() => {}}
        onDelete={() => {}}
      />
    );
    expect(screen.getByRole('button')).toBeDisabled();
  });
});

describe('ProjectPicker', () => {
  it('lists suggestions and picks one', async () => {
    const onPick = vi.fn();
    const onBack = vi.fn();
    render(
      <ProjectPicker
        suggestions={{ domain: 'Backend Development', projects: [SUGGESTION] }}
        onPick={onPick}
        picking={false}
        onBack={onBack}
      />
    );
    await userEvent.click(screen.getByText('Job board API'));
    expect(onPick).toHaveBeenCalledWith(SUGGESTION);
    await userEvent.click(screen.getAllByRole('button')[0]);
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('ignores picks while a plan is generating', async () => {
    const onPick = vi.fn();
    render(
      <ProjectPicker
        suggestions={{ domain: 'Web', projects: [{ ...SUGGESTION, difficulty: 'hard' }] }}
        onPick={onPick}
        picking
        onBack={() => {}}
      />
    );
    await userEvent.click(screen.getByText('Job board API'));
    expect(onPick).not.toHaveBeenCalled();
  });
});

describe('DayDetailModal', () => {
  const color = DAY_COLORS[0];

  it('lists tasks and resources and completes the day', async () => {
    const onComplete = vi.fn();
    render(
      <DayDetailModal
        day={makeDay(1)}
        color={color}
        canComplete
        onClose={() => {}}
        onComplete={onComplete}
        completing={false}
      />
    );
    expect(screen.getByText('Task 1a')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /FastAPI docs/ })).toHaveAttribute(
      'href',
      'https://fastapi.tiangolo.com'
    );
    await userEvent.click(screen.getByRole('button', { name: /Mark Day 1 Complete/ }));
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it('asks for the earlier days first when the day is not reachable', () => {
    render(
      <DayDetailModal
        day={makeDay(3)}
        color={color}
        canComplete={false}
        onClose={() => {}}
        onComplete={() => {}}
        completing={false}
      />
    );
    expect(screen.getByText('Complete previous days first to unlock this day.')).toBeVisible();
    expect(screen.queryByRole('button', { name: /Mark Day/ })).not.toBeInTheDocument();
  });

  it('hides the complete button on a finished day and closes on the backdrop', async () => {
    const onClose = vi.fn();
    const { container } = render(
      <DayDetailModal
        day={makeDay(1, { completedAt: '2026-03-01' })}
        color={color}
        canComplete
        onClose={onClose}
        onComplete={() => {}}
        completing={false}
      />
    );
    expect(screen.queryByRole('button', { name: /Mark Day/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByText('Task 1a'));
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(container.firstElementChild as Element);
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe('DuolingoPath', () => {
  it('shows progress and opens a day', async () => {
    const onDayClick = vi.fn();
    render(
      <DuolingoPath
        roadmap={makeRoadmap(2)}
        onDayClick={onDayClick}
        onBack={() => {}}
        onUnlockAll={() => {}}
        unlocking={false}
      />
    );
    expect(screen.getByText('29%')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('heading', { name: 'Day 3 build' }));
    expect(onDayClick).toHaveBeenCalledWith(expect.objectContaining({ day: 3 }));
  });

  it('shows 0% progress for a roadmap without days', () => {
    render(
      <DuolingoPath
        roadmap={makeRoadmap(0, { days: [], totalDays: 0 })}
        onDayClick={() => {}}
        onBack={() => {}}
        onUnlockAll={() => {}}
        unlocking={false}
      />
    );
    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  it('offers unlock-all until every day is unlocked', async () => {
    const onUnlockAll = vi.fn();
    const { rerender } = render(
      <DuolingoPath
        roadmap={makeRoadmap(0)}
        onDayClick={() => {}}
        onBack={() => {}}
        onUnlockAll={onUnlockAll}
        unlocking={false}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /Unlock/ }));
    expect(onUnlockAll).toHaveBeenCalledOnce();

    rerender(
      <DuolingoPath
        roadmap={makeRoadmap(0, { unlockedAll: true })}
        onDayClick={() => {}}
        onBack={() => {}}
        onUnlockAll={onUnlockAll}
        unlocking={false}
      />
    );
    expect(screen.queryByRole('button', { name: /Unlock All/ })).not.toBeInTheDocument();
  });

  it('goes back to the form', async () => {
    const onBack = vi.fn();
    render(
      <DuolingoPath
        roadmap={makeRoadmap(0)}
        onDayClick={() => {}}
        onBack={onBack}
        onUnlockAll={() => {}}
        unlocking={false}
      />
    );
    const header = screen.getAllByRole('button')[0];
    await userEvent.click(header);
    expect(onBack).toHaveBeenCalledOnce();
    expect(within(header).queryByText(/Unlock/)).not.toBeInTheDocument();
  });
});

describe('progressPercent', () => {
  it('rounds to a whole percent and treats no days as 0%', () => {
    expect(progressPercent(2, 7)).toBe(29);
    expect(progressPercent(7, 7)).toBe(100);
    expect(progressPercent(0, 0)).toBe(0);
  });
});

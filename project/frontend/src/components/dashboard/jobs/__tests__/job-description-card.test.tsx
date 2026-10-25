import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobDescriptionCard } from '../job-description-card';
import { makeJobDescription } from '@/test/job-descriptions';

function renderCard(overrides = {}, analyzing = false) {
  const handlers = { onOpen: vi.fn(), onAnalyze: vi.fn(), onDelete: vi.fn() };
  render(
    <JobDescriptionCard job={makeJobDescription(overrides)} analyzing={analyzing} {...handlers} />
  );
  return handlers;
}

describe('JobDescriptionCard', () => {
  it('shows six skills and counts the rest', () => {
    renderCard({ required_skills: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] });
    expect(screen.getByText('f')).toBeInTheDocument();
    expect(screen.queryByText('g')).not.toBeInTheDocument();
    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('names an unknown company and trims long descriptions', () => {
    renderCard({ company: '', raw_text: 'x'.repeat(400) });
    expect(screen.getByText('Unknown Company')).toBeInTheDocument();
    expect(screen.getByText(`${'x'.repeat(150)}...`)).toBeInTheDocument();
  });

  it('offers Analyze until the description is analyzed', async () => {
    const handlers = renderCard({ is_analyzed: false });
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }));
    expect(handlers.onAnalyze).toHaveBeenCalledOnce();
    expect(handlers.onOpen).not.toHaveBeenCalled();
  });

  it('disables Analyze while analyzing', () => {
    renderCard({ is_analyzed: false }, true);
    expect(screen.getByRole('button', { name: /Analyzing/ })).toBeDisabled();
  });

  it('deletes without opening the card, and opens on a card click', async () => {
    const handlers = renderCard();
    const buttons = screen.getAllByRole('button');
    await userEvent.click(buttons[buttons.length - 1]);
    expect(handlers.onDelete).toHaveBeenCalledOnce();
    expect(handlers.onOpen).not.toHaveBeenCalled();

    await userEvent.click(screen.getByText('Backend Intern'));
    expect(handlers.onOpen).toHaveBeenCalledOnce();
  });

  it('links to the source posting when there is one', () => {
    renderCard({ source_url: 'https://jobs.example.com/1' });
    expect(screen.getByRole('link')).toHaveAttribute('href', 'https://jobs.example.com/1');
  });
});

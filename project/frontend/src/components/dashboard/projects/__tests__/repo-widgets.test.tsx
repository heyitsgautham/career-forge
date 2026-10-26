import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RepoOption } from '../repo-option';
import { VisibilityFilter } from '../visibility-filter';
import type { GithubRepo } from '../github-repos';

const REPO: GithubRepo = {
  full_name: 'asha/notes',
  name: 'notes',
  description: 'Offline notes',
  html_url: '',
  stars: 3,
  forks: 1,
  language: 'TypeScript',
  is_private: true,
  is_fork: true,
};

describe('RepoOption', () => {
  it('shows badges and toggles when checked', async () => {
    const onToggle = vi.fn();
    render(<RepoOption repo={REPO} imported={false} isSelected={false} onToggle={onToggle} />);
    expect(screen.getByText('Private')).toBeInTheDocument();
    expect(screen.getByText('Fork')).toBeInTheDocument();
    expect(screen.getByText('Offline notes')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox'));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it('cannot be picked once imported', async () => {
    const onToggle = vi.fn();
    render(<RepoOption repo={REPO} imported isSelected={false} onToggle={onToggle} />);
    expect(screen.getByText('Imported')).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).toBeDisabled();
  });
});

describe('VisibilityFilter', () => {
  it('shows counts and reports the chosen visibility', async () => {
    const onChange = vi.fn();
    render(
      <VisibilityFilter
        value="all"
        onChange={onChange}
        counts={{ all: 3, public: 2, private: 1 }}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: 'Private (1)' }));
    expect(onChange).toHaveBeenCalledWith('private');
    expect(screen.getByRole('button', { name: 'All (3)' })).toBeInTheDocument();
  });
});

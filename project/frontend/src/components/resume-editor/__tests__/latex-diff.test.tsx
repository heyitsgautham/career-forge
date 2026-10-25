import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { CONTEXT, buildHunks, diffLines } from '../latex-diff';
import { LatexDiffViewer } from '../latex-diff-viewer';

describe('diffLines', () => {
  it('marks unchanged, added and removed lines', () => {
    expect(diffLines(['a', 'b', 'c'], ['a', 'x', 'c'])).toEqual([
      { kind: 'equal', text: 'a' },
      { kind: 'add', text: 'x' },
      { kind: 'remove', text: 'b' },
      { kind: 'equal', text: 'c' },
    ]);
  });

  it('handles empty inputs', () => {
    expect(diffLines([], ['a'])).toEqual([{ kind: 'add', text: 'a' }]);
    expect(diffLines(['a'], [])).toEqual([{ kind: 'remove', text: 'a' }]);
  });
});

describe('buildHunks', () => {
  it('returns nothing when nothing changed', () => {
    expect(buildHunks(diffLines(['a', 'b'], ['a', 'b']))).toEqual([]);
  });

  it('keeps context around each change and separates distant hunks', () => {
    const before = Array.from({ length: 20 }, (_, i) => `line ${i}`);
    const after = [...before];
    after[2] = 'changed 2';
    after[17] = 'changed 17';
    const hunks = buildHunks(diffLines(before, after));

    expect(hunks.filter((l) => l.kind === 'separator')).toHaveLength(1);
    expect(hunks).toContainEqual({ kind: 'equal', text: `line ${2 + CONTEXT}` });
    expect(hunks).not.toContainEqual({ kind: 'equal', text: 'line 10' });
  });
});

describe('LatexDiffViewer', () => {
  it('lists added and removed lines and collapses', async () => {
    render(<LatexDiffViewer original={'\\section{A}\nold'} modified={'\\section{A}\nnew'} />);
    expect(screen.getByText('new')).toBeInTheDocument();
    expect(screen.getByText('old')).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole('button')[0]);
    expect(screen.queryByText('new')).not.toBeInTheDocument();
  });

  it('says when the proposal changes nothing', () => {
    render(<LatexDiffViewer original="same" modified="same" />);
    expect(screen.queryByText('same')).not.toBeInTheDocument();
  });
});

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EditorLayout } from '../editor-layout';

describe('EditorLayout', () => {
  it('renders both panels', () => {
    render(<EditorLayout left={<p>code</p>} right={<p>chat</p>} />);
    expect(screen.getByText('code')).toBeInTheDocument();
    expect(screen.getByText('chat')).toBeInTheDocument();
  });
});

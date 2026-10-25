import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Portal } from '@/components/ui/portal';

describe('Portal', () => {
  it('renders its children straight into document.body', () => {
    render(
      <div className="space-y-8" data-testid="list">
        <p>first</p>
        <Portal>
          <div className="fixed inset-0" data-testid="overlay" />
        </Portal>
      </div>
    );
    const overlay = screen.getByTestId('overlay');
    expect(overlay.parentElement).toBe(document.body);
    expect(screen.getByTestId('list')).not.toContainElement(overlay);
  });

  it('keeps React events flowing to the parent tree', () => {
    let clicks = 0;
    render(
      <div onClick={() => clicks++}>
        <Portal>
          <button>inside</button>
        </Portal>
      </div>
    );
    screen.getByRole('button').click();
    expect(clicks).toBe(1);
  });
});

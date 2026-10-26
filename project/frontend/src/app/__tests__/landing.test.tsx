import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const idb = vi.hoisted(() => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }));
vi.mock('idb-keyval', () => idb);

import HomePage from '@/app/page';
import { Providers } from '@/app/providers';

describe('landing page', () => {
  it('leads every call to action to the login page', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    const links = screen.getAllByRole('link').filter((a) => a.getAttribute('href') === '/login');
    expect(links.length).toBeGreaterThanOrEqual(3);
  });
});

describe('Providers', () => {
  it('renders its children inside the query client', () => {
    render(
      <Providers>
        <p>inside</p>
      </Providers>
    );
    expect(screen.getByText('inside')).toBeInTheDocument();
  });
});

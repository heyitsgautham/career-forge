import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SidebarItem } from '@/components/dashboard/sidebar-item';

describe('SidebarItem', () => {
  it('shows its label and calls onClick when pressed', async () => {
    const onClick = vi.fn();
    render(<SidebarItem icon={<svg data-testid="icon" />} label="Projects" onClick={onClick} />);

    await userEvent.click(screen.getByRole('button', { name: 'Projects' }));

    expect(onClick).toHaveBeenCalledOnce();
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('marks the active item as the current page', () => {
    render(<SidebarItem icon={null} label="Resumes" active onClick={() => {}} />);
    expect(screen.getByRole('button', { name: 'Resumes' })).toHaveAttribute('aria-current', 'page');
  });

  it('leaves inactive items without aria-current', () => {
    render(<SidebarItem icon={null} label="Resumes" onClick={() => {}} />);
    expect(screen.getByRole('button', { name: 'Resumes' })).not.toHaveAttribute('aria-current');
  });

  it('hides the label when the sidebar is collapsed', () => {
    render(<SidebarItem icon={null} label="Roadmap" collapsed onClick={() => {}} />);
    expect(screen.queryByText('Roadmap')).not.toBeInTheDocument();
  });

  it('runs onMouseEnter so the dashboard can prefetch the tab', async () => {
    const onMouseEnter = vi.fn();
    render(
      <SidebarItem icon={null} label="Job Scout" onClick={() => {}} onMouseEnter={onMouseEnter} />
    );
    await userEvent.hover(screen.getByRole('button', { name: 'Job Scout' }));
    expect(onMouseEnter).toHaveBeenCalledOnce();
  });
});

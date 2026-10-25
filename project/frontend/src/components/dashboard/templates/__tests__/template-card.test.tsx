import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { TemplateCard } from '@/components/dashboard/templates/template-card';
import type { Template } from '@/components/dashboard/templates/types';

const TEMPLATE: Template = {
  id: 't1',
  name: 'Compact one-pager',
  description: 'Single column, tight margins',
  category: 'minimal',
  is_system: false,
  use_count: 3,
  latex_content: '',
  created_at: '2026-03-01T00:00:00Z',
};

describe('TemplateCard', () => {
  it('shows the name, category, description and use count', () => {
    render(<TemplateCard template={TEMPLATE} />);
    expect(screen.getByText('Compact one-pager')).toBeInTheDocument();
    expect(screen.getByText('minimal')).toBeInTheDocument();
    expect(screen.getByText('Single column, tight margins')).toBeInTheDocument();
    expect(screen.getByText('Used 3 times')).toBeInTheDocument();
  });

  it('counts a missing use_count as zero', () => {
    render(<TemplateCard template={{ ...TEMPLATE, use_count: undefined as unknown as number }} />);
    expect(screen.getByText('Used 0 times')).toBeInTheDocument();
  });

  it('renders the preview image when the template has one', () => {
    render(<TemplateCard template={{ ...TEMPLATE, preview_image_path: '/t1.png' }} />);
    expect(screen.getByRole('img', { name: 'Compact one-pager' })).toHaveAttribute(
      'src',
      '/t1.png'
    );
  });

  it('calls onPreview and onDelete from its buttons', async () => {
    const onPreview = vi.fn();
    const onDelete = vi.fn();
    render(<TemplateCard template={TEMPLATE} onPreview={onPreview} onDelete={onDelete} />);

    const [preview, remove] = screen.getAllByRole('button');
    await userEvent.click(preview);
    await userEvent.click(remove);

    expect(onPreview).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it('offers no delete button on system templates', () => {
    render(<TemplateCard template={TEMPLATE} isSystem onPreview={() => {}} onDelete={() => {}} />);
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });
});

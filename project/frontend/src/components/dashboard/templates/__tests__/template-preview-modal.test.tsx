import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import type { Template } from '@/components/dashboard/templates/types';

const api = vi.hoisted(() => ({ templatesApi: { get: vi.fn() } }));
vi.mock('@/lib/api', () => api);

import { TemplatePreviewModal } from '@/components/dashboard/templates/template-preview-modal';

const TEMPLATE: Template = {
  id: 't1',
  name: 'Base Resume Template',
  description: 'ATS-tested',
  category: 'professional',
  is_system: true,
  use_count: 1,
  latex_content: '',
  created_at: '2026-03-01T00:00:00Z',
};
const LATEX = [
  '{\\LARGE\\textbf{Asha Example}}',
  '\\section*{Experience}',
  'Sample Labs intern',
  '\\section*{Skills}',
  '<<SKILLS>>',
  '\\end{document}',
].join('\n');

beforeEach(() => vi.clearAllMocks());

describe('TemplatePreviewModal', () => {
  it('fetches the full template and renders an outline preview', async () => {
    api.templatesApi.get.mockResolvedValue({ data: { ...TEMPLATE, latex_content: LATEX } });
    renderWithQuery(<TemplatePreviewModal template={TEMPLATE} onClose={() => {}} />);

    expect(await screen.findByRole('heading', { name: 'Asha Example' })).toBeInTheDocument();
    expect(api.templatesApi.get).toHaveBeenCalledWith('t1');
    expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument();
    expect(screen.getByText('Sample Labs intern...')).toBeInTheDocument();
    expect(
      screen.getByText('[Content will be generated based on your projects and job description]')
    ).toBeInTheDocument();
  });

  it('switches to the raw LaTeX and copies it to the clipboard', async () => {
    api.templatesApi.get.mockResolvedValue({ data: { ...TEMPLATE, latex_content: LATEX } });
    const { user } = renderWithQuery(
      <TemplatePreviewModal template={TEMPLATE} onClose={() => {}} />
    );
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    await screen.findByRole('heading', { name: 'Asha Example' });

    await user.click(screen.getByRole('button', { name: 'LaTeX Code' }));
    expect(screen.getByText(/Sample Labs intern/).tagName).toBe('PRE');

    await user.click(screen.getByRole('button', { name: 'Copy LaTeX' }));
    expect(writeText).toHaveBeenCalledWith(LATEX);
  });

  it('shows placeholder sections when the template has no \\section', async () => {
    api.templatesApi.get.mockResolvedValue({ data: { ...TEMPLATE, latex_content: 'plain' } });
    renderWithQuery(<TemplatePreviewModal template={TEMPLATE} onClose={() => {}} />);
    expect(await screen.findByText('[Work experience will appear here]')).toBeInTheDocument();
  });

  it('disables copying and says so when the template has no content', async () => {
    api.templatesApi.get.mockResolvedValue({ data: { ...TEMPLATE, latex_content: '' } });
    renderWithQuery(<TemplatePreviewModal template={TEMPLATE} onClose={() => {}} />);
    expect(await screen.findByText('No content available')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy LaTeX' })).toBeDisabled();
  });

  it('closes on the backdrop but not on clicks inside the dialog', async () => {
    api.templatesApi.get.mockResolvedValue({ data: { ...TEMPLATE, latex_content: LATEX } });
    const onClose = vi.fn();
    const { user, container } = renderWithQuery(
      <TemplatePreviewModal template={TEMPLATE} onClose={onClose} />
    );
    await screen.findByRole('heading', { name: 'Asha Example' });

    await user.click(screen.getByText('ATS-tested'));
    expect(onClose).not.toHaveBeenCalled();

    await user.click(container.firstElementChild as Element);
    expect(onClose).toHaveBeenCalledOnce();
  });
});

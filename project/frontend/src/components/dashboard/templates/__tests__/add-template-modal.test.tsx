import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({ templatesApi: { create: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { AddTemplateModal } from '@/components/dashboard/templates/add-template-modal';
import { DEFAULT_TEMPLATE } from '@/components/dashboard/templates/default-template';

beforeEach(() => vi.clearAllMocks());

describe('AddTemplateModal', () => {
  it('starts from the default template and needs a name before it can submit', async () => {
    renderWithQuery(<AddTemplateModal onClose={() => {}} />);

    expect(screen.getByLabelText('LaTeX Content *')).toHaveValue(DEFAULT_TEMPLATE);
    expect(screen.getByLabelText('Category')).toHaveValue('professional');
    expect(screen.getByRole('button', { name: 'Create Template' })).toBeDisabled();
  });

  it('creates the template, reports success and closes', async () => {
    api.templatesApi.create.mockResolvedValue({ data: { id: 't9' } });
    const onClose = vi.fn();
    const { user } = renderWithQuery(<AddTemplateModal onClose={onClose} />);

    await user.type(screen.getByLabelText('Template Name *'), 'Two column');
    await user.type(screen.getByLabelText('Description'), 'Dense layout');
    await user.click(screen.getByRole('button', { name: 'Create Template' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(api.templatesApi.create).toHaveBeenCalledWith({
      name: 'Two column',
      description: 'Dense layout',
      latex_content: DEFAULT_TEMPLATE,
      category: 'professional',
    });
    expect(toast).toHaveBeenCalledWith({ title: 'Template created' });
  });

  it('shows the API error detail and stays open when creation fails', async () => {
    api.templatesApi.create.mockRejectedValue({ response: { data: { detail: 'Name taken' } } });
    const onClose = vi.fn();
    const { user } = renderWithQuery(<AddTemplateModal onClose={onClose} />);

    await user.type(screen.getByLabelText('Template Name *'), 'Dup');
    await user.click(screen.getByRole('button', { name: 'Create Template' }));

    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to create template', description: 'Name taken' })
      )
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes from the cancel button without calling the API', async () => {
    const onClose = vi.fn();
    const { user } = renderWithQuery(<AddTemplateModal onClose={onClose} />);
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(api.templatesApi.create).not.toHaveBeenCalled();
  });
});

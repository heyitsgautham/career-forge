import { screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({
  templatesApi: { list: vi.fn(), delete: vi.fn(), get: vi.fn(), create: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { TemplatesList } from '@/components/dashboard/templates-list';

const TEMPLATES = [
  {
    id: 'sys',
    name: 'Base Resume Template',
    description: 'ATS-tested',
    category: 'professional',
    is_system: true,
    use_count: 12,
  },
  {
    id: 'mine',
    name: 'Compact one-pager',
    description: 'Tight margins',
    category: 'minimal',
    is_system: false,
    use_count: 2,
  },
];

beforeEach(() => vi.clearAllMocks());

function section(name: string): HTMLElement {
  return screen.getByRole('heading', { name }).closest('section') as HTMLElement;
}

describe('TemplatesList', () => {
  it('groups system templates apart from the user templates', async () => {
    api.templatesApi.list.mockResolvedValue({ data: TEMPLATES });
    renderWithQuery(<TemplatesList />);

    await screen.findByText('Base Resume Template');
    expect(within(section('System Templates')).getByText('Base Resume Template')).toBeVisible();
    expect(within(section('Your Templates')).getByText('Compact one-pager')).toBeVisible();
  });

  it('invites the user to create a template when they have none', async () => {
    api.templatesApi.list.mockResolvedValue({ data: [TEMPLATES[0]] });
    renderWithQuery(<TemplatesList />);
    expect(await screen.findByText(/No custom templates yet/)).toBeInTheDocument();
  });

  it('deletes a user template and refetches the list', async () => {
    api.templatesApi.list.mockResolvedValue({ data: TEMPLATES });
    api.templatesApi.delete.mockResolvedValue({});
    const { user } = renderWithQuery(<TemplatesList />);
    await screen.findByText('Compact one-pager');

    const [, remove] = within(section('Your Templates')).getAllByRole('button');
    await user.click(remove);

    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Template deleted' }));
    expect(api.templatesApi.delete).toHaveBeenCalledWith('mine');
    expect(api.templatesApi.list).toHaveBeenCalledTimes(2);
  });

  it('opens the create modal from the header button', async () => {
    api.templatesApi.list.mockResolvedValue({ data: TEMPLATES });
    const { user } = renderWithQuery(<TemplatesList />);
    await screen.findByText('Compact one-pager');

    await user.click(screen.getAllByRole('button', { name: 'Create Template' })[0]);
    expect(screen.getByLabelText('Template Name *')).toBeInTheDocument();
  });

  it('opens the preview modal for a template', async () => {
    api.templatesApi.list.mockResolvedValue({ data: TEMPLATES });
    api.templatesApi.get.mockResolvedValue({ data: { latex_content: '\\textbf{Asha}' } });
    const { user } = renderWithQuery(<TemplatesList />);
    await screen.findByText('Base Resume Template');

    await user.click(within(section('System Templates')).getByRole('button'));
    expect(await screen.findByRole('button', { name: 'LaTeX Code' })).toBeInTheDocument();
    expect(api.templatesApi.get).toHaveBeenCalledWith('sys');
  });
});

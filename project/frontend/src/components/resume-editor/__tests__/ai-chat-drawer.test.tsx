import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ resumesApi: { aiEdit: vi.fn() } }));
vi.mock('@/lib/api', () => api);

import { AiChatDrawer } from '../ai-chat-drawer';

function sse(...events: object[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n`).join('');
  return new Response(body);
}

const ORIGINAL = '\\section{Summary}\nBuilds APIs';
const PROPOSED = '\\section{Summary}\nBuilds fast, tested APIs';

function renderDrawer() {
  const onApplyLatex = vi.fn();
  render(<AiChatDrawer resumeId="r1" getLatex={() => ORIGINAL} onApplyLatex={onApplyLatex} />);
  return onApplyLatex;
}

beforeEach(() => {
  vi.clearAllMocks();
  Element.prototype.scrollIntoView = vi.fn();
});

describe('AiChatDrawer', () => {
  it('sends the message with the current LaTeX and streams the reply', async () => {
    api.resumesApi.aiEdit.mockResolvedValue(
      sse({ text: 'Made the summary ' }, { text: 'sharper.' })
    );
    renderDrawer();

    await userEvent.type(screen.getByRole('textbox'), 'Make the summary sharper');
    await userEvent.click(screen.getAllByRole('button').at(-1)!);

    expect(await screen.findByText('Made the summary sharper.')).toBeInTheDocument();
    expect(screen.getByText('Make the summary sharper')).toBeInTheDocument();
    expect(api.resumesApi.aiEdit).toHaveBeenCalledWith('r1', 'Make the summary sharper', ORIGINAL);
    expect(screen.getByRole('textbox')).toHaveValue('');
  });

  it('shows a diff of proposed LaTeX and applies it', async () => {
    api.resumesApi.aiEdit.mockResolvedValue(sse({ text: 'Here you go.' }, { latex: PROPOSED }));
    const onApplyLatex = renderDrawer();

    await userEvent.type(screen.getByRole('textbox'), 'Improve it{Control>}{Enter}{/Control}');

    expect(await screen.findByText('Builds fast, tested APIs')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Accept/ }));
    expect(onApplyLatex).toHaveBeenCalledWith(PROPOSED);
    expect(screen.getByText('Applied to editor')).toBeInTheDocument();
  });

  it('drops a rejected proposal', async () => {
    api.resumesApi.aiEdit.mockResolvedValue(sse({ text: 'Option A.' }, { latex: PROPOSED }));
    const onApplyLatex = renderDrawer();
    await userEvent.type(screen.getByRole('textbox'), 'Try{Control>}{Enter}{/Control}');
    await userEvent.click(await screen.findByRole('button', { name: /Reject/ }));
    expect(onApplyLatex).not.toHaveBeenCalled();
    expect(screen.queryByText('Builds fast, tested APIs')).not.toBeInTheDocument();
  });

  it('hides any <latex> block that leaks into the text', async () => {
    api.resumesApi.aiEdit.mockResolvedValue(sse({ text: 'Done. <latex>\\documentclass' }));
    renderDrawer();
    await userEvent.type(screen.getByRole('textbox'), 'Go{Control>}{Enter}{/Control}');
    expect(await screen.findByText('Done.')).toBeInTheDocument();
    expect(screen.queryByText(/documentclass/)).not.toBeInTheDocument();
  });

  it('apologises when the request fails', async () => {
    api.resumesApi.aiEdit.mockRejectedValue(new Error('AI edit failed: 500'));
    renderDrawer();
    await userEvent.type(screen.getByRole('textbox'), 'Go{Control>}{Enter}{/Control}');
    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument();
  });

  it('ignores an empty message and clears the chat on reset', async () => {
    api.resumesApi.aiEdit.mockResolvedValue(sse({ text: 'Hi.' }));
    renderDrawer();
    await userEvent.type(screen.getByRole('textbox'), '   {Control>}{Enter}{/Control}');
    expect(api.resumesApi.aiEdit).not.toHaveBeenCalled();

    await userEvent.type(screen.getByRole('textbox'), 'Hello{Control>}{Enter}{/Control}');
    await screen.findByText('Hi.');
    await userEvent.click(screen.getByRole('button', { name: /Reset chat/ }));
    await waitFor(() => expect(screen.queryByText('Hi.')).not.toBeInTheDocument());
  });
});

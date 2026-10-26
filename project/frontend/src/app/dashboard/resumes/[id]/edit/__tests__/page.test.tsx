import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { makeResume } from '@/test/resumes';

vi.mock('next/navigation', () => ({ useParams: () => ({ id: 'r1' }) }));
// The real page loads Monaco through next/dynamic; a textarea stands in for it here.
// Like Monaco, it keeps its text across re-renders.
const editorText = vi.hoisted(() => ({ value: null as string | null }));
vi.mock('next/dynamic', () => ({
  default: () =>
    function FakeEditor({
      initialValue,
      onChange,
      onEditorReady,
    }: {
      initialValue: string;
      onChange: (v: string) => void;
      onEditorReady: (h: unknown) => void;
    }) {
      if (editorText.value === null) editorText.value = initialValue;
      onEditorReady({
        getValue: () => editorText.value ?? '',
        setValue: (v: string) => (editorText.value = v),
        clearMarkers: () => {},
      });
      return (
        <textarea
          aria-label="LaTeX source"
          defaultValue={initialValue}
          onChange={(e) => {
            editorText.value = e.target.value;
            onChange(e.target.value);
          }}
        />
      );
    },
}));
const api = vi.hoisted(() => ({
  resumesApi: {
    get: vi.fn(),
    getPdfUrl: vi.fn(),
    compileWithContent: vi.fn(),
    saveLaTeX: vi.fn(),
    downloadTex: vi.fn(),
    aiEdit: vi.fn(),
  },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import ResumeEditorPage from '@/app/dashboard/resumes/[id]/edit/page';

beforeEach(() => {
  vi.clearAllMocks();
  editorText.value = null;
  Element.prototype.scrollIntoView = vi.fn();
  api.resumesApi.get.mockResolvedValue({
    data: makeResume({ id: 'r1', status: 'generated', pdf_path: undefined }),
  });
  api.resumesApi.saveLaTeX.mockResolvedValue({});
  api.resumesApi.compileWithContent.mockResolvedValue({
    data: { status: 'compiled', pdf_url: '/r1.pdf', error_message: null },
  });
  api.resumesApi.getPdfUrl.mockResolvedValue({ data: { url: 'https://s3.example/r1.pdf' } });
});
afterEach(() => vi.useRealTimers());

describe('ResumeEditorPage', () => {
  it('says so when the resume does not exist', async () => {
    api.resumesApi.get.mockRejectedValue(new Error('404'));
    renderWithQuery(<ResumeEditorPage />);
    expect(await screen.findByText('Resume not found.')).toBeInTheDocument();
  });

  it('saves with Ctrl+S and compiles with Ctrl+Enter', async () => {
    renderWithQuery(<ResumeEditorPage />);
    await screen.findByLabelText('LaTeX source');

    fireEvent.keyDown(window, { key: 's', ctrlKey: true });
    await waitFor(() =>
      expect(api.resumesApi.saveLaTeX).toHaveBeenCalledWith('r1', '\\documentclass{article}')
    );

    fireEvent.keyDown(window, { key: 'Enter', metaKey: true });
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Compiled successfully' }));
    expect(screen.getByRole('button', { name: /PDF/ })).toBeEnabled();
  });

  it('auto-saves and auto-compiles a few seconds after typing', async () => {
    renderWithQuery(<ResumeEditorPage />);
    await screen.findByLabelText('LaTeX source');
    // The layout swaps its SSR-safe shell for resizable panels after mount, so query again.
    await act(async () => {});
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('LaTeX source'), {
      target: { value: '\\section{New}' },
    });
    expect(screen.getByText('● Unsaved')).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(api.resumesApi.saveLaTeX).toHaveBeenCalledWith('r1', '\\section{New}');
    expect(api.resumesApi.compileWithContent).toHaveBeenCalledWith('r1', '\\section{New}');
  });

  it('does not auto-compile once auto-compile is off', async () => {
    const { user } = renderWithQuery(<ResumeEditorPage />);
    await screen.findByLabelText('LaTeX source');
    await user.click(screen.getByRole('button', { name: /Auto-compile ON/ }));
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('LaTeX source'), { target: { value: 'x' } });
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(api.resumesApi.saveLaTeX).toHaveBeenCalled();
    expect(api.resumesApi.compileWithContent).not.toHaveBeenCalled();
  });

  it('warns when the preview is opened before any PDF exists', async () => {
    const { user } = renderWithQuery(<ResumeEditorPage />);
    await screen.findByLabelText('LaTeX source');
    await user.click(screen.getByRole('button', { name: /Preview/ }));
    expect(toast).toHaveBeenCalledWith({
      title: 'No PDF yet — compile first',
      variant: 'destructive',
    });
  });
});

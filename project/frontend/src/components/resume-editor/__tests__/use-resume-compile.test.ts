import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  resumesApi: { compileWithContent: vi.fn(), getPdfUrl: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { summarizeCompileError, useResumeCompile } from '../use-resume-compile';

const LATEX = '\\documentclass{article}\\begin{document}Hi\\end{document}';

beforeEach(() => {
  vi.clearAllMocks();
  api.resumesApi.getPdfUrl.mockResolvedValue({ data: { url: 'https://s3.example/r1.pdf?sig' } });
});

function renderCompile(resume?: { status?: string; pdf_path?: string | null }, content = LATEX) {
  const beforeCompile = vi.fn();
  const hook = renderHook(() =>
    useResumeCompile('r1-abcdefgh', resume, () => content, beforeCompile)
  );
  return { ...hook, beforeCompile };
}

describe('useResumeCompile', () => {
  it('starts idle for a resume that was never compiled', () => {
    const { result } = renderCompile({ status: 'generated' });
    expect(result.current.compileStatus).toBe('idle');
    expect(api.resumesApi.getPdfUrl).not.toHaveBeenCalled();
  });

  it('loads a signed URL for a resume that is already compiled', async () => {
    const { result } = renderCompile({ status: 'compiled' });
    await waitFor(() => expect(result.current.compileStatus).toBe('success'));
    expect(result.current.pdfUrl).toBe('https://s3.example/r1.pdf?sig');
  });

  it('falls back to the local upload path when signing fails', async () => {
    api.resumesApi.getPdfUrl.mockRejectedValue(new Error('no S3'));
    const { result } = renderCompile({ status: 'generated', pdf_path: 'u1/r1.pdf' });
    await waitFor(() => expect(result.current.compileStatus).toBe('success'));
    expect(result.current.pdfUrl).toMatch(/\/uploads\/pdfs\/r1-abcde\.pdf$/);
  });

  it('compiles the editor content and shows the signed URL', async () => {
    api.resumesApi.compileWithContent.mockResolvedValue({
      data: { status: 'compiled', pdf_url: '/raw.pdf', error_message: null },
    });
    const { result, beforeCompile } = renderCompile();

    await act(() => result.current.compile());

    expect(api.resumesApi.compileWithContent).toHaveBeenCalledWith('r1-abcdefgh', LATEX);
    expect(beforeCompile).toHaveBeenCalledOnce();
    expect(result.current.compileStatus).toBe('success');
    expect(result.current.pdfUrl).toBe('https://s3.example/r1.pdf?sig');
    expect(toast).toHaveBeenCalledWith({ title: 'Compiled successfully' });
  });

  it('keeps the raw PDF URL when signing it fails', async () => {
    api.resumesApi.compileWithContent.mockResolvedValue({
      data: { status: 'compiled', pdf_url: '/raw.pdf', error_message: null },
    });
    api.resumesApi.getPdfUrl.mockRejectedValue(new Error('no S3'));
    const { result } = renderCompile();
    await act(() => result.current.compile());
    expect(result.current.pdfUrl).toBe('/raw.pdf');
  });

  it('shows the LaTeX error in the toast when compilation fails', async () => {
    api.resumesApi.compileWithContent.mockResolvedValue({
      data: {
        status: 'error',
        pdf_url: null,
        error_message: '! Undefined control sequence.\nl.12 \\foo',
      },
    });
    const { result } = renderCompile();
    await act(() => result.current.compile());
    expect(result.current.compileStatus).toBe('error');
    expect(toast).toHaveBeenCalledWith({
      title: 'Compilation failed',
      description: '! Undefined control sequence. l.12 \\foo',
      variant: 'destructive',
    });
  });

  it('falls back to a generic reason when the backend sends none', async () => {
    api.resumesApi.compileWithContent.mockResolvedValue({
      data: { status: 'error', pdf_url: null, error_message: null },
    });
    const { result } = renderCompile();
    await act(() => result.current.compile());
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Compilation failed' })
    );
  });

  it('shows the API detail when the compile request itself fails', async () => {
    api.resumesApi.compileWithContent.mockRejectedValue({
      response: { data: { detail: 'Resume not found' } },
    });
    const { result } = renderCompile();
    await act(() => result.current.compile());
    expect(result.current.compileStatus).toBe('error');
    expect(toast).toHaveBeenCalledWith({
      title: 'Compile error',
      description: 'Resume not found',
      variant: 'destructive',
    });
  });

  it('shows the network error when there is no response', async () => {
    api.resumesApi.compileWithContent.mockRejectedValue(new Error('Network Error'));
    const { result } = renderCompile();
    await act(() => result.current.compile());
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ description: 'Network Error' }));
  });

  it('does nothing while the editor is empty', async () => {
    const { result } = renderCompile(undefined, '');
    await act(() => result.current.compile());
    expect(api.resumesApi.compileWithContent).not.toHaveBeenCalled();
    expect(result.current.compileStatus).toBe('idle');
  });
});

describe('summarizeCompileError', () => {
  it('keeps the first three non-blank lines', () => {
    expect(summarizeCompileError('a\n\n b \nc\nd')).toBe('a b c');
  });

  it('cuts long messages to 300 characters', () => {
    const summary = summarizeCompileError('x'.repeat(500));
    expect(summary).toHaveLength(300);
    expect(summary.endsWith('…')).toBe(true);
  });
});

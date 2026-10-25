import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { makeResume } from '@/test/resumes';

const api = vi.hoisted(() => ({
  resumesApi: { getPdfUrl: vi.fn(), getPdfDownloadUrl: vi.fn(), downloadTex: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { resumeDateStamp, useResumeFiles } from '../use-resume-files';

let clicked: { href: string; download: string | null }[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  clicked = [];
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement
  ) {
    clicked.push({ href: this.href, download: this.getAttribute('download') });
  });
  window.URL.createObjectURL = vi.fn(() => 'blob:tex');
  window.URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

const files = () => renderHook(() => useResumeFiles()).result.current;

describe('resumeDateStamp', () => {
  it('keeps the UTC date part', () => {
    expect(resumeDateStamp('2026-03-01T23:30:00Z')).toBe('2026-03-01');
  });
});

describe('useResumeFiles', () => {
  it('opens a signed PDF URL in a new tab', async () => {
    api.resumesApi.getPdfUrl.mockResolvedValue({ data: { url: 'https://s3.example/r1.pdf' } });
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    await files().previewPdf(makeResume());
    expect(open).toHaveBeenCalledWith('https://s3.example/r1.pdf', '_blank', 'noopener,noreferrer');
  });

  it('refuses to preview or download a resume without a PDF', async () => {
    await files().previewPdf(makeResume({ pdf_path: undefined }));
    await files().downloadPdf(makeResume({ pdf_path: undefined }));
    expect(api.resumesApi.getPdfUrl).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledTimes(2);
    expect(toast).toHaveBeenCalledWith({ title: 'PDF not available', variant: 'destructive' });
  });

  it('downloads the PDF under a dated file name', async () => {
    api.resumesApi.getPdfDownloadUrl.mockResolvedValue({
      data: { url: 'https://s3.example/r1.pdf?attachment' },
    });
    await files().downloadPdf(makeResume());
    expect(clicked).toEqual([
      { href: 'https://s3.example/r1.pdf?attachment', download: 'resume-2026-03-01.pdf' },
    ]);
  });

  it('downloads the LaTeX source as a blob and releases it', async () => {
    api.resumesApi.downloadTex.mockResolvedValue({ data: '\\documentclass{article}' });
    await files().downloadTex('r1-abcdefgh');
    expect(clicked).toEqual([{ href: 'blob:tex', download: 'resume-r1-abcde.tex' }]);
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:tex');
  });

  it('reports each failure with its own message', async () => {
    api.resumesApi.getPdfUrl.mockRejectedValue(new Error('403'));
    api.resumesApi.getPdfDownloadUrl.mockRejectedValue(new Error('403'));
    api.resumesApi.downloadTex.mockRejectedValue(new Error('404'));
    await files().previewPdf(makeResume());
    await files().downloadPdf(makeResume());
    await files().downloadTex('r1', 'x.tex');
    expect(toast.mock.calls.map(([t]) => t.title)).toEqual([
      'Failed to open PDF',
      'Failed to download PDF',
      '.tex download failed',
    ]);
  });
});

import { screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';
import { makeResume } from '@/test/resumes';

const api = vi.hoisted(() => ({
  resumesApi: {
    getPdfUrl: vi.fn(),
    getPdfDownloadUrl: vi.fn(),
    downloadTex: vi.fn(),
    compile: vi.fn(),
  },
}));
vi.mock('@/lib/api', () => api);
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

import { ResumeRow } from '../resume-row';

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

describe('ResumeRow', () => {
  it('offers preview, PDF, .tex and the editor for a compiled resume', () => {
    renderWithQuery(<ResumeRow resume={makeResume()} onDelete={() => {}} />);
    expect(screen.getByText('Ready')).toBeInTheDocument();
    for (const name of [/Preview/, /PDF/, /\.tex/, /Open in Editor/]) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByRole('link')).toHaveAttribute('href', '/dashboard/resumes/r1-abcdefgh/edit');
  });

  it('offers a compile button for a generated resume without a PDF', async () => {
    api.resumesApi.compile.mockResolvedValue({});
    const { user } = renderWithQuery(
      <ResumeRow
        resume={makeResume({ status: 'generated', pdf_path: undefined })}
        onDelete={() => {}}
      />
    );
    expect(screen.queryByRole('button', { name: /Preview/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Compile PDF/ }));
    expect(api.resumesApi.compile).toHaveBeenCalledWith('r1-abcdefgh');
  });

  it('shows the error message of a failed resume and still links to the editor', () => {
    renderWithQuery(
      <ResumeRow
        resume={makeResume({
          status: 'error',
          pdf_path: undefined,
          error_message: 'Bedrock timeout',
        })}
        onDelete={() => {}}
      />
    );
    expect(screen.getByText('Bedrock timeout')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Edit/ })).toBeInTheDocument();
  });

  it('falls back to the draft badge for an unknown status', () => {
    renderWithQuery(
      <ResumeRow
        resume={makeResume({
          status: 'queued' as never,
          latex_content: undefined,
          pdf_path: undefined,
        })}
        onDelete={() => {}}
      />
    );
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('deletes only after the user confirms', async () => {
    const onDelete = vi.fn();
    const confirm = vi
      .spyOn(window, 'confirm')
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    const { user } = renderWithQuery(<ResumeRow resume={makeResume()} onDelete={onDelete} />);
    const buttons = screen.getAllByRole('button');
    const trash = buttons[buttons.length - 1];

    await user.click(trash);
    expect(onDelete).not.toHaveBeenCalled();
    await user.click(trash);
    expect(onDelete).toHaveBeenCalledOnce();
    expect(confirm).toHaveBeenCalledWith('Delete this resume?');
  });
});

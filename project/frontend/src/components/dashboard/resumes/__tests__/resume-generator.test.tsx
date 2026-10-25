import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({
  resumesApi: { generateFromSummaries: vi.fn(), downloadTex: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { ResumeGenerator } from '../resume-generator';

const RESULT = {
  resume_id: 'r9',
  pdf_url: 'https://s3.example/r9.pdf',
  tex_url: 'https://s3.example/r9.tex',
  analysis: 'Ranked job-scout first for its FastAPI work.',
  status: 'compiled',
};

beforeEach(() => vi.clearAllMocks());

describe('ResumeGenerator', () => {
  it('generates from the pasted job description and shows the result', async () => {
    api.resumesApi.generateFromSummaries.mockResolvedValue({ data: RESULT });
    const { user } = renderWithQuery(<ResumeGenerator onClose={() => {}} onGenerated={() => {}} />);

    await user.type(screen.getByLabelText(/Job Description/), 'Backend intern, Python');
    await user.click(screen.getByRole('button', { name: /Generate Resume/ }));

    expect(await screen.findByText(/generated & compiled/)).toBeInTheDocument();
    expect(api.resumesApi.generateFromSummaries).toHaveBeenCalledWith('Backend intern, Python');
    expect(screen.getByRole('link', { name: /Download PDF/ })).toHaveAttribute(
      'href',
      RESULT.pdf_url
    );
    expect(screen.getByRole('link', { name: /Open in Editor/ })).toHaveAttribute(
      'href',
      '/dashboard/resumes/r9/edit'
    );
    expect(screen.getByRole('button', { name: /Regenerate/ })).toBeInTheDocument();
  });

  it('sends no job description when the box is empty', async () => {
    api.resumesApi.generateFromSummaries.mockResolvedValue({ data: RESULT });
    const { user } = renderWithQuery(<ResumeGenerator onClose={() => {}} onGenerated={() => {}} />);
    await user.click(screen.getByRole('button', { name: /Generate Resume/ }));
    await waitFor(() =>
      expect(api.resumesApi.generateFromSummaries).toHaveBeenCalledWith(undefined)
    );
  });

  it('shows the compile error when the LaTeX did not build', async () => {
    api.resumesApi.generateFromSummaries.mockResolvedValue({
      data: { ...RESULT, pdf_url: null, compilation_error: 'Missing \\begin{document}' },
    });
    const { user } = renderWithQuery(<ResumeGenerator onClose={() => {}} onGenerated={() => {}} />);
    await user.click(screen.getByRole('button', { name: /Generate Resume/ }));
    expect(await screen.findByText('PDF compilation failed')).toBeInTheDocument();
    expect(screen.getByText('Missing \\begin{document}')).toBeInTheDocument();
    expect(screen.getByText(/generated \(LaTeX saved\)/)).toBeInTheDocument();
  });

  it('shows the API reason when generation fails', async () => {
    api.resumesApi.generateFromSummaries.mockRejectedValue({
      response: { data: { detail: 'No projects ingested yet' } },
    });
    const { user } = renderWithQuery(<ResumeGenerator onClose={() => {}} onGenerated={() => {}} />);
    await user.click(screen.getByRole('button', { name: /Generate Resume/ }));
    expect(await screen.findByText('No projects ingested yet')).toBeInTheDocument();
  });

  it('expands the analysis and finishes with Done', async () => {
    api.resumesApi.generateFromSummaries.mockResolvedValue({ data: RESULT });
    const onGenerated = vi.fn();
    const { user } = renderWithQuery(
      <ResumeGenerator onClose={() => {}} onGenerated={onGenerated} />
    );
    await user.click(screen.getByRole('button', { name: /Generate Resume/ }));

    await user.click(await screen.findByRole('button', { name: /Step 0 Analysis/ }));
    expect(screen.getByText(RESULT.analysis)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Done' }));
    expect(onGenerated).toHaveBeenCalledOnce();
  });

  it('downloads the .tex source through the API', async () => {
    api.resumesApi.generateFromSummaries.mockResolvedValue({ data: RESULT });
    api.resumesApi.downloadTex.mockRejectedValue(new Error('404'));
    const { user } = renderWithQuery(<ResumeGenerator onClose={() => {}} onGenerated={() => {}} />);
    await user.click(screen.getByRole('button', { name: /Generate Resume/ }));
    await user.click(await screen.findByRole('button', { name: /Download .tex Source/ }));
    expect(api.resumesApi.downloadTex).toHaveBeenCalledWith('r9');
    expect(toast).toHaveBeenCalledWith({ title: '.tex download failed', variant: 'destructive' });
  });
});

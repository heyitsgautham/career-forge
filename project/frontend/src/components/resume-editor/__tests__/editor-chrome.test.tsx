import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CodePreviewPanel } from '../code-preview-panel';
import { EditorToolbar } from '../editor-toolbar';
import { SaveIndicator } from '../save-indicator';

describe('SaveIndicator', () => {
  it.each([
    ['saving', 'Saving…'],
    ['dirty', '● Unsaved'],
    ['saved', 'Saved'],
  ] as const)('shows %s', (status, text) => {
    render(<SaveIndicator saveStatus={status} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });
});

describe('EditorToolbar', () => {
  function renderToolbar(overrides = {}) {
    const props = {
      name: 'Backend resume',
      saveStatus: 'saved' as const,
      compileStatus: 'idle' as const,
      autoCompile: true,
      pdfUrl: 'https://s3.example/r1.pdf' as string | null,
      onToggleAutoCompile: vi.fn(),
      onSave: vi.fn(),
      onCompile: vi.fn(),
      onDownloadPdf: vi.fn(),
      onDownloadTex: vi.fn(),
      ...overrides,
    };
    render(<EditorToolbar {...props} />);
    return props;
  }

  it('wires every action and links back to the resumes tab', async () => {
    const props = renderToolbar();
    for (const name of [/Auto-compile ON/, /^Save$/, /Compile/, /PDF/, /\.tex/]) {
      await userEvent.click(screen.getByRole('button', { name }));
    }
    expect(props.onToggleAutoCompile).toHaveBeenCalledOnce();
    expect(props.onSave).toHaveBeenCalledOnce();
    expect(props.onCompile).toHaveBeenCalledOnce();
    expect(props.onDownloadPdf).toHaveBeenCalledOnce();
    expect(props.onDownloadTex).toHaveBeenCalledOnce();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/dashboard?tab=resumes');
    expect(screen.getByRole('heading', { name: 'Backend resume' })).toBeInTheDocument();
  });

  it('disables actions that cannot run yet', () => {
    renderToolbar({
      saveStatus: 'saving',
      compileStatus: 'compiling',
      pdfUrl: null,
      autoCompile: false,
    });
    expect(screen.getByRole('button', { name: /^Save$/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Compile$/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /PDF/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Auto-compile OFF/ })).toBeInTheDocument();
  });
});

describe('CodePreviewPanel', () => {
  it('keeps the editor mounted and shows the PDF in the preview tab', async () => {
    render(
      <CodePreviewPanel
        editor={<textarea aria-label="latex" />}
        fileName="Backend resume.tex"
        pdfUrl="https://s3.example/r1.pdf"
        onPreviewWithoutPdf={() => {}}
      />
    );
    expect(screen.getByText('Backend resume.tex')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Preview/ }));
    expect(screen.getByTitle('Resume PDF preview')).toHaveAttribute(
      'src',
      'https://s3.example/r1.pdf'
    );
    expect(screen.getByLabelText('latex', { selector: 'textarea' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Code/ }));
    expect(screen.queryByTitle('Resume PDF preview')).not.toBeInTheDocument();
  });

  it('stays on the code tab until there is a PDF', async () => {
    const onPreviewWithoutPdf = vi.fn();
    render(
      <CodePreviewPanel
        editor={<p>editor</p>}
        fileName="r.tex"
        pdfUrl={null}
        onPreviewWithoutPdf={onPreviewWithoutPdf}
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /Preview/ }));
    expect(onPreviewWithoutPdf).toHaveBeenCalledOnce();
    expect(screen.queryByTitle('Resume PDF preview')).not.toBeInTheDocument();
  });
});

import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LatexEditorHandle } from '../latex-editor';

// A stand-in for Monaco: it records what the wrapper does to the editor and model.
const monaco = vi.hoisted(() => {
  const model = {};
  let value = '';
  const editor = {
    getValue: () => value,
    setValue: (v: string) => {
      value = v;
    },
    getModel: () => model,
  };
  const registered: string[] = [];
  return {
    model,
    editor,
    registered,
    lastProps: {} as Record<string, unknown>,
    api: {
      MarkerSeverity: { Error: 8 },
      languages: {
        getLanguages: () => registered.map((id) => ({ id })),
        register: ({ id }: { id: string }) => registered.push(id),
        setMonarchTokensProvider: vi.fn(),
      },
      editor: { setModelMarkers: vi.fn() },
    },
    reset() {
      value = '';
      registered.length = 0;
    },
  };
});

vi.mock('@monaco-editor/react', () => ({
  default: (props: {
    value: string;
    onMount: (e: unknown, m: unknown) => void;
    onChange: (v?: string) => void;
  }) => {
    monaco.lastProps = props;
    monaco.editor.setValue(props.value);
    props.onMount(monaco.editor, monaco.api);
    return <div data-testid="monaco" />;
  },
}));

import { LatexEditor } from '../latex-editor';

beforeEach(() => {
  vi.clearAllMocks();
  monaco.reset();
});

function mount(onChange = vi.fn()) {
  let handle: LatexEditorHandle | undefined;
  render(
    <LatexEditor
      initialValue={'\\documentclass{article}'}
      onChange={onChange}
      onEditorReady={(h) => (handle = h)}
    />
  );
  return { handle: handle!, onChange };
}

describe('LatexEditor', () => {
  it('registers LaTeX highlighting once and loads the initial text', () => {
    const { handle } = mount();
    expect(handle.getValue()).toBe('\\documentclass{article}');
    expect(monaco.lastProps).toMatchObject({ language: 'latex', theme: 'vs-dark' });

    render(<LatexEditor />);
    expect(monaco.registered).toEqual(['latex']);
    expect(monaco.api.languages.setMonarchTokensProvider).toHaveBeenCalledOnce();
  });

  it('replaces the text through its handle', () => {
    const { handle } = mount();
    handle.setValue('\\section{Skills}');
    expect(handle.getValue()).toBe('\\section{Skills}');
  });

  it('marks error lines and skips line numbers it cannot place', () => {
    const { handle } = mount();
    handle.addErrorMarkers([
      { line: 12, message: 'Undefined control sequence' },
      { line: 0, message: 'no line' },
    ]);
    expect(monaco.api.editor.setModelMarkers).toHaveBeenCalledWith(monaco.model, 'latex-errors', [
      expect.objectContaining({
        startLineNumber: 12,
        message: 'Undefined control sequence',
        severity: 8,
      }),
    ]);

    handle.clearMarkers();
    expect(monaco.api.editor.setModelMarkers).toHaveBeenLastCalledWith(
      monaco.model,
      'latex-errors',
      []
    );
  });

  it('reports edits and ignores the undefined value Monaco sends on dispose', () => {
    const { onChange } = mount();
    const change = monaco.lastProps.onChange as (v?: string) => void;
    change('\\section{New}');
    change(undefined);
    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith('\\section{New}');
  });
});

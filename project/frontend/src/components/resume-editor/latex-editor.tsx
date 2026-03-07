'use client';

import { useRef, useCallback, useEffect } from 'react';
import Editor, { OnMount, OnChange } from '@monaco-editor/react';
import { editor as MonacoEditor } from 'monaco-editor';

export interface LatexEditorHandle {
  getValue: () => string;
  setValue: (value: string) => void;
  addErrorMarkers: (errors: Array<{ line: number; message: string }>) => void;
  clearMarkers: () => void;
}

interface LatexEditorProps {
  initialValue?: string;
  onChange?: (value: string) => void;
  onEditorReady?: (handle: LatexEditorHandle) => void;
}

/**
 * Monaco LaTeX editor wrapper.
 * Exposes getValue/setValue/addErrorMarkers via the onEditorReady callback.
 */
export function LatexEditor({ initialValue = '', onChange, onEditorReady }: LatexEditorProps) {
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import('monaco-editor') | null>(null);

  const handleMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Register LaTeX language tokens for basic syntax highlighting
      if (!monaco.languages.getLanguages().some((l: { id: string }) => l.id === 'latex')) {
        monaco.languages.register({ id: 'latex' });
        monaco.languages.setMonarchTokensProvider('latex', {
          tokenizer: {
            root: [
              [/\\[a-zA-Z@]+/, 'keyword'],
              [/%.*$/, 'comment'],
              [/\$\$?/, 'string'],
              [/\{|\}/, 'delimiter.curly'],
              [/\[|\]/, 'delimiter.square'],
              [/[0-9]+/, 'number'],
            ],
          },
        });
      }

      if (onEditorReady) {
        const handle: LatexEditorHandle = {
          getValue: () => editor.getValue(),
          setValue: (val: string) => {
            editor.setValue(val);
          },
          addErrorMarkers: (errors) => {
            const markers = errors
              .filter((e) => e.line > 0)
              .map((e) => ({
                severity: monaco.MarkerSeverity.Error,
                message: e.message,
                startLineNumber: e.line,
                startColumn: 1,
                endLineNumber: e.line,
                endColumn: 999,
              }));
            const model = editor.getModel();
            if (model) {
              monaco.editor.setModelMarkers(model, 'latex-errors', markers);
            }
          },
          clearMarkers: () => {
            const model = editor.getModel();
            if (model) {
              monaco.editor.setModelMarkers(model, 'latex-errors', []);
            }
          },
        };
        onEditorReady(handle);
      }
    },
    [onEditorReady],
  );

  const handleChange: OnChange = useCallback(
    (value) => {
      if (value !== undefined && onChange) {
        onChange(value);
      }
    },
    [onChange],
  );

  return (
    <Editor
      height="100%"
      language="latex"
      value={initialValue}
      onMount={handleMount}
      onChange={handleChange}
      theme="vs-dark"
      options={{
        minimap: { enabled: false },
        fontSize: 13,
        lineNumbers: 'on',
        wordWrap: 'on',
        automaticLayout: true,
        scrollBeyondLastLine: false,
        tabSize: 2,
        renderWhitespace: 'none',
        folding: true,
        lineDecorationsWidth: 4,
        overviewRulerLanes: 0,
        padding: { top: 12 },
      }}
    />
  );
}

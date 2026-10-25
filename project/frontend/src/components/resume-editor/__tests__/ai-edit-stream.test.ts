import { describe, expect, it, vi } from 'vitest';
import { readAiEditStream } from '../ai-edit-stream';

/** A reader that yields each string as one network chunk. */
function readerOf(...chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }).getReader();
}

describe('readAiEditStream', () => {
  it('collects text chunks in order and keeps the proposed LaTeX', async () => {
    const onText = vi.fn();
    const result = await readAiEditStream(
      readerOf(
        'data: {"text": "Tightened "}\n',
        'data: {"text": "the summary."}\n',
        'data: {"latex": "\\\\documentclass{article}"}\n'
      ),
      onText
    );
    expect(result).toEqual({ text: 'Tightened the summary.', latex: '\\documentclass{article}' });
    expect(onText.mock.calls.map(([c]) => c)).toEqual(['Tightened ', 'the summary.']);
  });

  it('joins an event split across two network chunks', async () => {
    const result = await readAiEditStream(readerOf('data: {"te', 'xt": "hello"}\n'), () => {});
    expect(result.text).toBe('hello');
  });

  it('skips comments, empty events and lines that are not JSON', async () => {
    const result = await readAiEditStream(
      readerOf(': keep-alive\n', 'data: {}\n', 'data: \n', 'data: not json\n', 'event: done\n'),
      () => {}
    );
    expect(result).toEqual({ text: '', latex: null });
  });

  it('ignores a final line without a newline', async () => {
    const result = await readAiEditStream(readerOf('data: {"text": "cut off"}'), () => {});
    expect(result.text).toBe('');
  });

  it('stops reading once aborted', async () => {
    let aborted = false;
    const onText = vi.fn(() => {
      aborted = true;
    });
    const result = await readAiEditStream(
      readerOf('data: {"text": "one"}\n', 'data: {"text": "two"}\n'),
      onText,
      () => aborted
    );
    expect(result.text).toBe('one');
  });
});

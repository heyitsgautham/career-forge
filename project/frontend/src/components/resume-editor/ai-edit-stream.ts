/**
 * Reads the server-sent events from POST /api/resumes/{id}/ai-edit.
 *
 * Each `data:` line holds JSON with either a `text` chunk of the assistant's
 * reply or the full proposed `latex`. Comments, empty events and lines that
 * are not JSON are skipped. A line split across two network chunks is joined
 * before it is parsed.
 */
export async function readAiEditStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onText: (chunk: string) => void,
  isAborted: () => boolean = () => false
): Promise<{ text: string; latex: string | null }> {
  const decoder = new TextDecoder();
  let buffer = '';
  let text = '';
  let latex: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done || isAborted()) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const rawData = line.slice(6).trim();
      if (!rawData || rawData === '{}') continue;
      try {
        const parsed = JSON.parse(rawData);
        if (parsed.text !== undefined) {
          text += parsed.text as string;
          onText(parsed.text as string);
        }
        if (parsed.latex !== undefined) {
          latex = parsed.latex;
        }
      } catch {
        // SSE comment or non-JSON line
      }
    }
  }

  return { text, latex };
}

'use client';

import { unescapeMarkdown } from './format';

export function RichDescription({ text }: { text: string }) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let bulletBuffer: string[] = [];
  let key = 0;

  const flushBullets = () => {
    if (bulletBuffer.length === 0) return;
    elements.push(
      <ul key={key++} className="list-disc list-outside pl-5 space-y-1 my-1">
        {bulletBuffer.map((b, i) => (
          <li key={i}>{renderInline(b)}</li>
        ))}
      </ul>
    );
    bulletBuffer = [];
  };

  const renderInline = (line: string): React.ReactNode => {
    const cleaned = unescapeMarkdown(line);
    const parts: React.ReactNode[] = [];
    let lastIdx = 0;
    // Match **bold** segments
    const boldRe = /\*\*([^*]+)\*\*/g;
    let m: RegExpExecArray | null;
    while ((m = boldRe.exec(cleaned)) !== null) {
      if (m.index > lastIdx) {
        parts.push(cleaned.slice(lastIdx, m.index));
      }
      parts.push(<strong key={`b${m.index}`}>{m[1]}</strong>);
      lastIdx = m.index + m[0].length;
    }
    if (lastIdx < cleaned.length) {
      parts.push(cleaned.slice(lastIdx));
    }
    return parts.length === 1 ? parts[0] : <>{parts}</>;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    // Bullet line: starts with "* " or "- "
    const bulletMatch = line.match(/^\s*(?:\*|-)\s+(.+)/);
    if (bulletMatch) {
      bulletBuffer.push(bulletMatch[1]);
      continue;
    }

    // Non-bullet line — flush any pending bullets
    flushBullets();

    // Empty line → spacing
    if (line.trim() === '') {
      elements.push(<div key={key++} className="h-2" />);
      continue;
    }

    // Heading-like: entire line is bold
    const headingMatch = line.match(/^\s*\*\*([^*]+)\*\*\s*$/);
    if (headingMatch) {
      elements.push(
        <p key={key++} className="font-semibold mt-3 mb-1">
          {unescapeMarkdown(headingMatch[1])}
        </p>
      );
      continue;
    }

    // Regular paragraph with inline bold
    elements.push(
      <p key={key++} className="my-0.5 leading-relaxed">
        {renderInline(line)}
      </p>
    );
  }

  flushBullets();

  return <div className="text-sm">{elements}</div>;
}

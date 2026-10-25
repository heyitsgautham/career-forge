import { describe, expect, it } from 'vitest';
import {
  extractName,
  extractSections,
  hasPlaceholder,
} from '@/components/dashboard/templates/latex-outline';

describe('extractName', () => {
  it('reads the first bold text as the name', () => {
    expect(extractName('{\\LARGE\\textbf{Asha Example}}')).toBe('Asha Example');
  });

  it('reads a \\LARGE group when there is no bold text', () => {
    expect(extractName('\\LARGE {Asha Example}')).toBe('Asha Example');
  });

  it('falls back to a generic name', () => {
    expect(extractName('\\documentclass{article}')).toBe('Your Name');
    expect(extractName('<<NAME>> on its own line')).toBe('Your Name');
  });
});

describe('extractSections', () => {
  it('splits starred and unstarred sections up to the end of the document', () => {
    const latex = [
      '\\section*{Experience}',
      'Intern at Sample Labs',
      '\\section{Skills}',
      'Python, Go',
      '\\end{document}',
    ].join('\n');

    expect(extractSections(latex)).toEqual([
      { title: 'Experience', content: 'Intern at Sample Labs' },
      { title: 'Skills', content: 'Python, Go' },
    ]);
  });

  it('returns no sections for LaTeX without \\section', () => {
    expect(extractSections('\\begin{document}hi\\end{document}')).toEqual([]);
  });

  it('gives the same result when called twice on the same input', () => {
    const latex = '\\section*{A}\none\n\\section*{B}\ntwo';
    expect(extractSections(latex)).toEqual(extractSections(latex));
  });
});

describe('hasPlaceholder', () => {
  it.each(['<<SKILLS>>', '{{SKILLS}}'])('detects %s', (content) => {
    expect(hasPlaceholder(content)).toBe(true);
  });

  it('ignores plain text', () => {
    expect(hasPlaceholder('Python, Go')).toBe(false);
  });
});

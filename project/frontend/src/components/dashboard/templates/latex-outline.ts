/** Pulls a rough outline out of template LaTeX for the HTML preview. It is not a LaTeX parser. */

export interface OutlineSection {
  title: string;
  content: string;
}

const NAME_PATTERN = /\\textbf\{([^}]+)\}|\\LARGE[^{]*\{([^}]+)\}|<<NAME>>|\{\{NAME\}\}/;
const SECTION_PATTERN = /\\section\*?\{([^}]+)\}([\s\S]*?)(?=\\section|\\end\{document\}|$)/g;

export function extractName(latex: string): string {
  const match = latex.match(NAME_PATTERN);
  const name = match ? match[1] || match[2] : undefined;
  // The default template wraps <<NAME>> in \textbf, so a captured slot means there is no real name.
  return name && !hasPlaceholder(name) ? name : 'Your Name';
}

export function extractSections(latex: string): OutlineSection[] {
  const sections: OutlineSection[] = [];
  for (const match of latex.matchAll(SECTION_PATTERN)) {
    sections.push({ title: match[1], content: match[2].trim() });
  }
  return sections;
}

/** True when a section still holds <<SLOT>> or {{SLOT}} placeholders for the generator. */
export function hasPlaceholder(content: string): boolean {
  return content.includes('<<') || content.includes('{{');
}

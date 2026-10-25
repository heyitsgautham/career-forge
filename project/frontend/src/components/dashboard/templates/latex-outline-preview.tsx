import { extractName, extractSections, hasPlaceholder } from './latex-outline';

const FALLBACK_SECTIONS = [
  { title: 'Summary', hint: '[Professional summary will appear here]' },
  { title: 'Experience', hint: '[Work experience will appear here]' },
  { title: 'Projects', hint: '[Selected projects will appear here]' },
  { title: 'Skills', hint: '[Technical skills will appear here]' },
];

/** A paper-styled HTML sketch of a LaTeX template: the name, then each section's opening text. */
export function LatexOutlinePreview({ latex }: { latex: string }) {
  const sections = extractSections(latex);

  return (
    <div
      className="bg-white text-black p-8 shadow-lg max-w-[8.5in] mx-auto"
      style={{ fontFamily: 'Times New Roman, serif' }}
    >
      <div className="text-center border-b-2 border-black pb-4 mb-4">
        <h1 className="text-2xl font-bold">{extractName(latex)}</h1>
        <p className="text-sm text-gray-600 mt-1">
          email@example.com | (555) 123-4567 | City, State
        </p>
      </div>

      {sections.length > 0
        ? sections.map((section, idx) => (
            <div key={idx} className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">{section.title}</h2>
              <div className="text-sm text-gray-700">
                {hasPlaceholder(section.content) ? (
                  <p className="italic text-gray-500">
                    [Content will be generated based on your projects and job description]
                  </p>
                ) : (
                  <p className="whitespace-pre-wrap">{section.content.slice(0, 200)}...</p>
                )}
              </div>
            </div>
          ))
        : FALLBACK_SECTIONS.map(({ title, hint }) => (
            <div key={title} className="mb-4">
              <h2 className="text-lg font-bold border-b border-gray-400 mb-2">{title}</h2>
              <p className="text-sm italic text-gray-500">{hint}</p>
            </div>
          ))}
    </div>
  );
}

/** Starting LaTeX for a new template, with <<PLACEHOLDER>> slots the generator fills in. */
export const DEFAULT_TEMPLATE = `\\documentclass[11pt,a4paper]{article}
\\usepackage[margin=1in]{geometry}
\\usepackage{enumitem}
\\usepackage{hyperref}

\\begin{document}

\\begin{center}
{\\LARGE\\textbf{<<NAME>>}}\\\\[0.5em]
<<EMAIL>> | <<PHONE>> | <<LOCATION>>
\\end{center}

\\section*{Summary}
<<SUMMARY>>

\\section*{Experience}
<<EXPERIENCE>>

\\section*{Projects}
<<PROJECTS>>

\\section*{Education}
<<EDUCATION>>

\\section*{Skills}
<<SKILLS>>

\\end{document}`;

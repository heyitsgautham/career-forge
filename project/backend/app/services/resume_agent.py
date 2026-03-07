"""
Resume Generation Agent
=======================
Generates ATS-friendly LaTeX resumes using Bedrock Claude with strict grounding.
Supports two flows:
  1. Template-fill: fill placeholders in a LaTeX template (legacy M1 flow)
  2. S3-summary: read project summaries from S3, run Step 0 analysis, generate full LaTeX (M2 flow)
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

from app.services.bedrock_client import bedrock_client


logger = structlog.get_logger()


@dataclass
class GenerationResult:
    """Result of resume generation."""
    latex_content: str
    warnings: List[str]
    changes_made: List[str]
    tokens_used: int


@dataclass
class M2GenerationResult:
    """Result of M2 resume generation (S3 summary-based)."""
    latex_content: str
    analysis: str
    resume_id: str
    pdf_url: Optional[str]
    tex_url: Optional[str]
    compilation_error: Optional[str] = None  # LaTeX error if compilation failed


# Anti-hallucination system prompt
SYSTEM_PROMPT = r"""You are a professional resume LaTeX formatter. Your ONLY job is to fill a LaTeX template with provided user data.

CRITICAL RULES - VIOLATION WILL CAUSE ERRORS:

1. GROUNDING REQUIREMENT:
   - ONLY use information explicitly provided in the <user_data> section
   - NEVER invent, assume, or hallucinate ANY information
   - This includes: projects, skills, companies, dates, achievements, metrics, or ANY facts
   
2. MISSING DATA HANDLING:
   - If required data is missing, output "[REQUIRED: field_name]" as placeholder
   - If optional data is missing, omit that section entirely
   - NEVER fill gaps with invented information

3. ONE-PAGE CONSTRAINT:
   - Resume MUST fit on a single page (maximum)
   - Keep descriptions concise and impactful
   - Each project should have EXACTLY 3 single-line bullet points (no more, no less)
   - Use compact LaTeX formatting (smaller margins, tight spacing if needed)
   - Prioritize most important information

4. ALLOWED TRANSFORMATIONS:
   - Rephrase for clarity and ATS optimization (but preserve ALL facts)
   - Condense bullet points to single lines (max 80-100 characters each)
   - Reorder bullet points for impact
   - Adjust formatting to match template structure
   - Fix grammar and spelling
   - Use technical terminology and industry-standard terms
   - Focus on technical implementation details and architecture
   
5. FORBIDDEN TRANSFORMATIONS:
   - Adding metrics not in original data (e.g., "improved by 50%")
   - Adding technologies not listed
   - Inventing project features
   - Creating achievements not mentioned
   - Adding company names or dates not provided

6. LATEX SYNTAX REQUIREMENTS (CRITICAL):
   - Every opening brace { MUST have a matching closing brace }
   - Never use \\\\ at the start of a line or on an empty line
   - Escape special characters: & % $ # _ { } ~ ^ \\
   - Always close all LaTeX commands properly
   - Test: Count your { and } - they MUST be equal

7. FONT CONSISTENCY (CRITICAL):
   - Use ONLY \textbf{} for bold text (NEVER use \bf, \bfseries, or {\bf })
   - Use ONLY \textit{} for italic text (NEVER use \it, \itshape, or {\it })
   - Use ONLY \texttt{} for monospace text (NEVER use \tt, \ttfamily, or {\tt })
   - DO NOT mix font commands (e.g., NEVER nest \textbf{\textit{}} - pick one)
   - DO NOT use old-style font commands: \bf, \it, \rm, \sc, \tt
   - DO NOT use declarative commands: \bfseries, \itshape, \ttfamily
   - Maintain consistent font usage throughout the entire document

8. OUTPUT FORMAT:
   - Return ONLY valid LaTeX code
   - Preserve all template commands exactly
   - Escape special LaTeX characters: & % $ # _ { } ~ ^

VERIFICATION STEP:
Before outputting, mentally verify each fact against <user_data>. 
If you cannot find the source for a claim, DO NOT include it."""


class ResumeGenerationAgent:
    """
    Agent for generating resumes using Gemini with strict anti-hallucination controls.
    """
    
    def __init__(self):
        pass
    
    async def generate_resume(
        self,
        template_latex: str,
        user_data: Dict[str, Any],
        jd_context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
    ) -> GenerationResult:
        """
        Generate a filled LaTeX resume from template and user data.
        
        Args:
            template_latex: LaTeX template with placeholders
            user_data: User data to fill placeholders
            jd_context: Optional job description context for tailoring
            temperature: LLM temperature (lower = more deterministic)
            
        Returns:
            GenerationResult with LaTeX content and metadata
        """
        # Build the prompt
        prompt = self._build_generation_prompt(
            template=template_latex,
            user_data=user_data,
            jd_context=jd_context,
        )
        
        try:
            response = await bedrock_client.generate_content(
                prompt=prompt,
                system_instruction=SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=8192,
            )
            
            # Extract LaTeX from response (handle potential markdown wrapping)
            latex_content = self._extract_latex(response)
            
            # Fix common font inconsistencies
            latex_content = self._fix_font_commands(latex_content)
            
            # Validate grounding
            warnings = self._validate_grounding(latex_content, user_data)
            
            return GenerationResult(
                latex_content=latex_content,
                warnings=warnings,
                changes_made=["Filled template with user data"],
                tokens_used=len(response.split()),  # Approximate
            )
            
        except Exception as e:
            logger.error(f"Resume generation failed: {e}")
            raise
    
    def _build_generation_prompt(
        self,
        template: str,
        user_data: Dict[str, Any],
        jd_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the generation prompt with user data."""
        
        # Format user data section
        user_data_str = self._format_user_data(user_data)
        
        # Format JD context if provided
        jd_str = ""
        if jd_context:
            jd_str = f"""
<jd_context>
Target Role: {jd_context.get('title', 'N/A')}
Company: {jd_context.get('company', 'N/A')}
Key Requirements: {', '.join(jd_context.get('required_skills', [])[:10])}

Use this context to:
- Prioritize skills matching the requirements
- Order projects by relevance
- Tailor language to the role
DO NOT add any information not in user_data.
</jd_context>
"""
        
        prompt = rf"""Fill this LaTeX resume template with the provided user data.

<template>
{template}
</template>

<user_data>
{user_data_str}
</user_data>

{jd_str}

CRITICAL FORMATTING REQUIREMENTS:
- Resume MUST fit on ONE PAGE ONLY
- Each project must have EXACTLY 3 bullet points (single line each, max 80-100 characters)
- Keep all descriptions concise and impactful
- Use compact spacing and formatting

LATEX SYNTAX RULES (MUST FOLLOW):
- Every {{ must have a matching }}
- Never start a line with \\\\
- Escape special chars: use \\& \\% \\$ \\# \\_ for & % $ # _
- Close ALL commands: \\command{{text}} not \\command{{text

FONT CONSISTENCY RULES (CRITICAL):
- Use ONLY \\textbf{{text}} for bold (NOT \\bf, \\bfseries, or {{\\bf text}})
- Use ONLY \\textit{{text}} for italics (NOT \\it, \\itshape, or {{\\it text}})
- Use ONLY \\texttt{{text}} for monospace (NOT \\tt, \\ttfamily, or {{\\tt text}})
- DO NOT mix font commands (avoid \\textbf{{\\textit{{text}}}})
- Maintain uniform font usage throughout the entire document
- When the template already has font commands (like \\textbf or \\textit), preserve them exactly

URL FORMATTING RULES (CRITICAL):
- For project URLs: Use ONLY \\href{{url}}{{Link}} format (just the word "Link")
- For personal URLs in header section: Use descriptive labels based on URL content:
  * GitHub URLs: \\href{{url}}{{GitHub}}
  * LinkedIn URLs: \\href{{url}}{{LinkedIn}}
  * Portfolio/personal websites: \\href{{url}}{{Portfolio}} or \\href{{url}}{{Website}}
- NEVER display the full URL text in the visible output
- NEVER use \\underline with URLs (hyperlinks are already underlined)
- NEVER add icons like \\faGlobe or \\faExternalLink unless template explicitly includes them
- NEVER add prefixes like "GitHub project:" or "Project:" to project titles
- Keep URL links simple and clean: \\href{{https://example.com}}{{Link}} NOT \\href{{https://example.com}}{{\\underline{{example.com}}}}

INSTRUCTIONS:
1. Replace all placeholders ({{{{PLACEHOLDER}}}}) with corresponding user data
2. For {{{{#ARRAY}}}}...{{{{/ARRAY}}}} sections, iterate over the array
3. For each PROJECT bullet point:
   - Use technical terminology (e.g., "Implemented RESTful API", "Architected microservices", "Optimized database queries")
   - Focus on technical implementation and architecture ("Built scalable X using Y", "Integrated Z with A")
   - Each point must fit on ONE LINE (max 80-100 characters)
   - Include specific technologies used (from the project's tech stack)
   - Start with strong action verbs (Developed, Architected, Implemented, Integrated, Optimized, Designed)
   - For project URLs: use \\href{{url}}{{Link}} format, do NOT display full URL text
   - NEVER add prefixes like "GitHub project:" or "Project:" to project titles - just use the title as-is
4. **CRITICAL** For missing/empty data: COMPLETELY DELETE the entire section (including headers and ALL content)
   - Check if WORK EXPERIENCE data exists - if NO, DELETE entire \\section{{Experience}} block
   - Check if EDUCATION data exists - if NO, DELETE entire \\section{{Education}} block  
   - An empty array [] means NO DATA - DELETE that section
   - NEVER leave empty commands with blank arguments
   - DO NOT show placeholders or empty structures
   - Example: if "WORK EXPERIENCE:" is not in user_data, DELETE the Experience section completely
5. For EDUCATION section:
   - Include ALL education entries from the data (if user has 2 education items, show both)
   - Use school, degree, field, dates, location, gpa fields
6. For CERTIFICATIONS section:
   - Include ALL certifications from the data
   - Use name, issuer, date, credential_id, url fields
   - If CERTIFICATIONS data exists, include it; if empty/missing, DELETE the entire section
7. Preserve all LaTeX commands and structure for sections that HAVE data
8. Maintain template alignment - do NOT modify spacing, indentation, or formatting commands
9. Ensure the final output will compile to a single-page PDF
10. VERIFY: Count all braces - they must be balanced!
11. VERIFY: No command has empty blank arguments
12. Return ONLY the filled LaTeX code, no explanations

OUTPUT: Complete, valid LaTeX code ready for compilation (single page)."""

        return prompt
    
    def _format_user_data(self, user_data: Dict[str, Any]) -> str:
        """Format user data for the prompt."""
        import json
        
        # Create a clean representation
        formatted_parts = []
        
        # Personal info
        if "personal" in user_data:
            formatted_parts.append("PERSONAL INFORMATION:")
            for key, value in user_data["personal"].items():
                formatted_parts.append(f"  {key}: {value}")
        
        # Skills
        if "skills" in user_data:
            formatted_parts.append(f"\nSKILLS: {', '.join(user_data['skills'])}")
        
        # Projects
        if "projects" in user_data:
            formatted_parts.append("\nPROJECTS:")
            for i, proj in enumerate(user_data["projects"], 1):
                formatted_parts.append(f"\n  Project {i}:")
                formatted_parts.append(f"    Title: {proj.get('title', 'N/A')}")
                formatted_parts.append(f"    Description: {proj.get('description', 'N/A')}")
                if proj.get("technologies"):
                    formatted_parts.append(f"    Technologies: {', '.join(proj['technologies'])}")
                if proj.get("highlights"):
                    formatted_parts.append(f"    Achievements:")
                    for h in proj["highlights"]:
                        formatted_parts.append(f"      - {h}")
                if proj.get("url"):
                    formatted_parts.append(f"    URL: {proj['url']}")
                if proj.get("dates"):
                    formatted_parts.append(f"    Dates: {proj['dates']}")
        
        # Experience
        if "experience" in user_data and user_data["experience"]:
            formatted_parts.append("\nWORK EXPERIENCE:")
            for i, exp in enumerate(user_data["experience"], 1):
                formatted_parts.append(f"\n  Experience {i}:")
                formatted_parts.append(f"    Company: {exp.get('company', 'N/A')}")
                formatted_parts.append(f"    Title: {exp.get('title', 'N/A')}")
                formatted_parts.append(f"    Dates: {exp.get('dates', 'N/A')}")
                if exp.get('location'):
                    formatted_parts.append(f"    Location: {exp.get('location')}")
                if exp.get("highlights"):
                    formatted_parts.append(f"    Responsibilities:")
                    for h in exp["highlights"]:
                        formatted_parts.append(f"      - {h}")
        
        # Education
        if "education" in user_data and user_data["education"]:
            formatted_parts.append("\nEDUCATION:")
            for i, edu in enumerate(user_data["education"], 1):
                formatted_parts.append(f"\n  Education {i}:")
                formatted_parts.append(f"    School: {edu.get('school', 'N/A')}")
                formatted_parts.append(f"    Degree: {edu.get('degree', 'N/A')}")
                if edu.get('field'):
                    formatted_parts.append(f"    Field: {edu.get('field')}")
                formatted_parts.append(f"    Dates: {edu.get('dates', 'N/A')}")
                if edu.get('location'):
                    formatted_parts.append(f"    Location: {edu.get('location')}")
                if edu.get('gpa'):
                    formatted_parts.append(f"    GPA: {edu.get('gpa')}")
        
        # Certifications
        if "certifications" in user_data and user_data["certifications"]:
            formatted_parts.append("\nCERTIFICATIONS:")
            for i, cert in enumerate(user_data["certifications"], 1):
                formatted_parts.append(f"\n  Certification {i}:")
                formatted_parts.append(f"    Name: {cert.get('name', 'N/A')}")
                if cert.get('issuer'):
                    formatted_parts.append(f"    Issuer: {cert.get('issuer')}")
                if cert.get('date'):
                    formatted_parts.append(f"    Date: {cert.get('date')}")
                if cert.get('credential_id'):
                    formatted_parts.append(f"    Credential ID: {cert.get('credential_id')}")
                if cert.get('url'):
                    formatted_parts.append(f"    URL: {cert.get('url')}")
        
        # Any additional fields
        for key, value in user_data.items():
            if key not in {"personal", "skills", "projects", "experience", "education", "certifications"}:
                if isinstance(value, list):
                    formatted_parts.append(f"\n{key.upper()}: {', '.join(str(v) for v in value)}")
                else:
                    formatted_parts.append(f"\n{key.upper()}: {value}")
        
        return "\n".join(formatted_parts)
    
    def _extract_latex(self, response: str) -> str:
        """Extract LaTeX content from response, handling markdown wrapping."""
        content = response.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```latex"):
            content = content[8:]
        elif content.startswith("```"):
            content = content[3:]
        
        # Remove trailing markdown if present
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        # Validate balanced braces
        if not self._validate_braces(content):
            logger.warning("Generated LaTeX has unbalanced braces!")
            # Try to find and log the issue
            open_count = content.count('{')
            close_count = content.count('}')
            logger.warning(f"Open braces: {open_count}, Close braces: {close_count}")
        
        # Remove sections containing placeholders
        content = self._remove_placeholder_sections(content)
        
        return content
    
    def _validate_braces(self, latex: str) -> bool:
        """Validate that all braces are balanced in LaTeX."""
        stack = []
        for i, char in enumerate(latex):
            if char == '{':
                # Check if it's escaped
                if i > 0 and latex[i-1] == '\\' and i > 1 and latex[i-2] == '\\':
                    continue  # \\{ is escaped
                stack.append(i)
            elif char == '}':
                if i > 0 and latex[i-1] == '\\' and i > 1 and latex[i-2] == '\\':
                    continue  # \\} is escaped
                if not stack:
                    return False
                stack.pop()
        return len(stack) == 0
    
    def _remove_placeholder_sections(self, latex: str) -> str:
        """Remove any LaTeX sections that contain [REQUIRED:] placeholders."""
        import re
        
        # Find the position of the first section and end of document
        first_section_match = re.search(r'\\section\{', latex)
        if not first_section_match:
            return latex  # No sections found
        
        doc_end_match = re.search(r'\\end\{document\}', latex)
        if not doc_end_match:
            return latex  # No end of document found
        
        # Split the document
        doc_start = latex[:first_section_match.start()]
        doc_end = latex[doc_end_match.start():]
        sections_text = latex[first_section_match.start():doc_end_match.start()]
        
        # Find all sections with their content
        section_pattern = r'(\\section\{[^}]+\}.*?)(?=\\section\{|$)'
        sections = re.findall(section_pattern, sections_text, re.DOTALL)
        
        # Filter out sections containing placeholders
        cleaned_sections = []
        for section in sections:
            if '[REQUIRED:' in section:
                # Extract section name for logging
                section_name_match = re.search(r'\\section\{([^}]+)\}', section)
                section_name = section_name_match.group(1) if section_name_match else 'Unknown'
                logger.info(f"Removed section '{section_name}' containing placeholders")
            else:
                cleaned_sections.append(section)
        
        # Reconstruct the document
        return doc_start + ''.join(cleaned_sections) + doc_end
    
    def _validate_grounding(
        self,
        latex: str,
        user_data: Dict[str, Any],
    ) -> List[str]:
        """
        Validate that generated content is grounded in user data.
        Returns list of warnings for potentially ungrounded content.
        """
        warnings = []
        
        # Check for placeholder markers that weren't filled
        import re
        unfilled = re.findall(r'\[REQUIRED: ([^\]]+)\]', latex)
        if unfilled:
            warnings.extend([f"Missing required field: {f}" for f in unfilled])
        
        # Check for common hallucination patterns
        hallucination_patterns = [
            (r'\d+%', "percentage"),
            (r'\$[\d,]+', "dollar amount"),
            (r'\d+x', "multiplier"),
        ]
        
        for pattern, desc in hallucination_patterns:
            matches = re.findall(pattern, latex)
            if matches:
                # Check if these values exist in user data
                user_data_str = str(user_data)
                for match in matches:
                    if match not in user_data_str:
                        warnings.append(f"Potential ungrounded {desc}: {match}")
        
        # Check for font consistency issues
        font_warnings = self._check_font_consistency(latex)
        warnings.extend(font_warnings)
        
        return warnings
    
    def _fix_font_commands(self, latex: str) -> str:
        r"""
        Automatically fix common font inconsistencies by replacing old-style
        and declarative font commands with modern \textXX{} commands.
        
        Note: This preserves legitimate uses of \bfseries etc. in:
        - \titleformat commands (section formatting)
        - Header blocks with size commands like {\LARGE\bfseries Name}
        
        Only fixes old-style commands in regular document content.
        """
        import re
        
        # Fix old-style font commands
        # \bf text -> \textbf{text}
        # This is tricky because old commands affect text until scope ends
        # For simplicity, we'll just warn about these - manual fix is safer
        
        # Fix simple patterns: {\bf text} -> \textbf{text}
        latex = re.sub(r'\{\\bf\s+([^}]+)\}', r'\\textbf{\1}', latex)
        latex = re.sub(r'\{\\it\s+([^}]+)\}', r'\\textit{\1}', latex)
        latex = re.sub(r'\{\\tt\s+([^}]+)\}', r'\\texttt{\1}', latex)
        latex = re.sub(r'\{\\sc\s+([^}]+)\}', r'\\textsc{\1}', latex)
        latex = re.sub(r'\{\\rm\s+([^}]+)\}', r'\\textrm{\1}', latex)
        
        # Fix patterns without braces but with space: \bf text -> \textbf{text}
        # This is less safe, so we only do it for simple word patterns
        latex = re.sub(r'\\bf\s+(\w+)', r'\\textbf{\1}', latex)
        latex = re.sub(r'\\it\s+(\w+)', r'\\textit{\1}', latex)
        latex = re.sub(r'\\tt\s+(\w+)', r'\\texttt{\1}', latex)
        
        # Fix declarative commands in document body content (not in headers or \titleformat)
        # We only fix isolated uses like {\bfseries text} not combined with size commands
        # This avoids breaking headers like {\LARGE\bfseries Name}
        
        # Fix declarative commands in document body content
        # We need to be careful not to break legitimate uses in headers/titleformat
        
        # First, preserve the preamble and header (everything before first \section)
        section_match = re.search(r'\\section\{', latex)
        if section_match:
            preamble = latex[:section_match.start()]
            content = latex[section_match.start():]
            
            # Only apply fixes to content after first section
            # Fix isolated declarative commands (not combined with size/color)
            content = re.sub(r'\{\\bfseries\s+([^}]+)\}', r'\\textbf{\1}', content)
            content = re.sub(r'\{\\itshape\s+([^}]+)\}', r'\\textit{\1}', content)
            content = re.sub(r'\{\\ttfamily\s+([^}]+)\}', r'\\texttt{\1}', content)
            content = re.sub(r'\{\\scshape\s+([^}]+)\}', r'\\textsc{\1}', content)
            
            latex = preamble + content
        else:
            # No sections found, apply fixes to isolated uses only
            # Use negative lookbehind to avoid matching combined commands
            latex = re.sub(r'(?<!\\color\{[^}]{0,20})\{\\bfseries\s+([^}]+)\}', r'\\textbf{\1}', latex)
            latex = re.sub(r'\{\\itshape\s+([^}]+)\}', r'\\textit{\1}', latex)
            latex = re.sub(r'\{\\ttfamily\s+([^}]+)\}', r'\\texttt{\1}', latex)
            latex = re.sub(r'\{\\scshape\s+([^}]+)\}', r'\\textsc{\1}', latex)
        
        # Fix URL formatting issues
        latex = self._fix_url_formatting(latex)
        
        return latex
    
    def _fix_url_formatting(self, latex: str) -> str:
        r"""
        Fix common URL formatting issues in LaTeX.
        - Remove \underline from href link text
        - Remove icons from project URLs
        - Simplify verbose URL displays
        """
        import re
        
        # Fix: \href{url}{\underline{text}} -> \href{url}{text}
        latex = re.sub(r'\\href\{([^}]+)\}\{\\underline\{([^}]+)\}\}', r'\\href{\1}{\2}', latex)
        
        # Fix: \href{url}{ \faGlobe\ \underline{full-url}} -> \href{url}{Link}
        # This pattern matches FontAwesome icons + underlined URLs
        latex = re.sub(
            r'\\href\{([^}]+)\}\{\s*\\fa\w+\s*\\?\s*\\underline\{[^}]+\}\}',
            r'\\href{\1}{Link}',
            latex
        )
        
        # Fix: \href{url}{\faExternalLink} or \href{url}{\faGlobe} -> \href{url}{Link}
        # Remove standalone icons in project URLs (but preserve in headers)
        # We only do this if it's NOT in the document header section
        latex = re.sub(
            r'(\\section\{Projects\}.*?)\\href\{([^}]+)\}\{\\fa\w+\*?\}',
            r'\1\\href{\2}{Link}',
            latex,
            flags=re.DOTALL
        )
        
        # Fix: \href{url}{full-url-text} -> \href{url}{appropriate-label}
        # Intelligently replace based on URL content
        def replace_url_text(match):
            url = match.group(1).lower()
            text = match.group(2)
            
            # If text looks like a URL, replace with appropriate label
            if '://' in text or text.startswith('www.') or text.startswith('http'):
                # Determine appropriate label based on URL
                if 'github.com' in url:
                    return f'\\href{{{match.group(1)}}}{{GitHub}}'
                elif 'linkedin.com' in url:
                    return f'\\href{{{match.group(1)}}}{{LinkedIn}}'
                elif 'twitter.com' in url or 'x.com' in url:
                    return f'\\href{{{match.group(1)}}}{{Twitter}}'
                else:
                    # For project URLs or other links, use "Link"
                    return f'\\href{{{match.group(1)}}}{{Link}}'
            return match.group(0)
        
        latex = re.sub(r'\\href\{([^}]+)\}\{([^}]+)\}', replace_url_text, latex)
        
        return latex
    
    def _check_font_consistency(self, latex: str) -> List[str]:
        """
        Check for font inconsistencies and old-style font commands.
        Returns list of warnings for font issues.
        """
        import re
        warnings = []
        
        # Check for old-style font commands (should not be used)
        old_style_patterns = [
            (r'\\bf\b', r'\bf', r'\textbf{}'),
            (r'\\it\b', r'\it', r'\textit{}'),
            (r'\\rm\b', r'\rm', r'\textrm{}'),
            (r'\\tt\b', r'\tt', r'\texttt{}'),
            (r'\\sc\b', r'\sc', r'\textsc{}'),
        ]
        
        for pattern, command, replacement in old_style_patterns:
            if re.search(pattern, latex):
                warnings.append(f"Old-style font command detected: {command} (should use {replacement})")
        
        # Check for declarative font commands (should not be used in content)
        declarative_patterns = [
            (r'\\bfseries\b', r'\bfseries', r'\textbf{}'),
            (r'\\itshape\b', r'\itshape', r'\textit{}'),
            (r'\\ttfamily\b', r'\ttfamily', r'\texttt{}'),
            (r'\\scshape\b', r'\scshape', r'\textsc{}'),
        ]
        
        # Only check for these outside of \titleformat and other formatting commands
        content_latex = re.sub(r'\\titleformat\{[^}]*\}\{[^}]*\}', '', latex)
        content_latex = re.sub(r'\\titlespacing[^\n]*\n', '', content_latex)
        # Exclude entire header section (before first \section command)
        section_match = re.search(r'\\section\{', content_latex)
        if section_match:
            # Only check content after the first section (skip header)
            content_latex = content_latex[section_match.start():]
        # Also exclude any blocks with size commands (like {\LARGE\bfseries Name})
        content_latex = re.sub(r'\{[^}]*\\(LARGE|Large|large|huge|Huge)[^}]*\}', '', content_latex)
        # Exclude \color commands that might contain font commands
        content_latex = re.sub(r'\{[^}]*\\color\{[^}]*\}[^}]*\}', '', content_latex)
        
        for pattern, command, replacement in declarative_patterns:
            if re.search(pattern, content_latex):
                warnings.append(f"Declarative font command in content: {command} (should use {replacement})")
        
        # Check for nested font commands (generally bad practice)
        nested_patterns = [
            r'\\textbf\{[^}]*\\textit\{',
            r'\\textit\{[^}]*\\textbf\{',
            r'\\textbf\{[^}]*\\texttt\{',
            r'\\texttt\{[^}]*\\textbf\{',
        ]
        
        for pattern in nested_patterns:
            if re.search(pattern, latex):
                warnings.append(f"Nested font commands detected (avoid mixing bold/italic/monospace)")
        
        # Check for URL formatting issues
        url_warnings = self._check_url_formatting(latex)
        warnings.extend(url_warnings)
        
        return warnings
    
    def _check_url_formatting(self, latex: str) -> List[str]:
        r"""
        Check for URL formatting issues.
        Returns list of warnings for URL problems.
        """
        import re
        warnings = []
        
        # Check for underlined URLs
        if re.search(r'\\href\{[^}]+\}\{[^}]*\\underline', latex):
            warnings.append("URLs with \\underline detected (hyperlinks are already underlined)")
        
        # Check for URLs displaying full URL text
        url_pattern = r'\\href\{([^}]+)\}\{([^}]+)\}'
        matches = re.findall(url_pattern, latex)
        for url, text in matches:
            # If text looks like a URL, warn
            if '://' in text or text.startswith('www.') or text.startswith('http'):
                warnings.append(f"Full URL displayed in link text: {text} (should be simplified)")
        
        return warnings
    
    async def tailor_project_description(
        self,
        project: Dict[str, Any],
        jd_keywords: List[str],
    ) -> Dict[str, Any]:
        """
        Tailor a project description for a specific job.
        Only rephrases - does not add new information.
        
        Args:
            project: Project data dict
            jd_keywords: Keywords from job description
            
        Returns:
            Project with tailored description and highlights
        """
        prompt = f"""Tailor this project for a job requiring: {', '.join(jd_keywords[:10])}

PROJECT:
Title: {project.get('title')}
Description: {project.get('description')}
Technologies: {', '.join(project.get('technologies', []))}
Highlights:
{chr(10).join('- ' + h for h in project.get('highlights', []))}

RULES:
1. ONLY rephrase existing content - DO NOT add new facts
2. Emphasize technologies that match job keywords
3. Keep same meaning, just optimize wording
4. Preserve all technical accuracy

Return JSON with "description" and "highlights" (array) keys."""

        try:
            result = await bedrock_client.generate_json(
                prompt=prompt,
                system_instruction="You are a resume optimizer. Rephrase content for relevance but NEVER add information not present in the original.",
                temperature=0.3,
            )
            
            return {
                **project,
                "description": result.get("description", project.get("description")),
                "highlights": result.get("highlights", project.get("highlights", [])),
            }
        except Exception as e:
            logger.error(f"Project tailoring failed: {e}")
            return project


# ──────────────────────────────────────────────────────────────────────────────
# M2: S3-Summary-Based Resume Generation (new-resume.prompt.md pattern)
# ──────────────────────────────────────────────────────────────────────────────

RESUME_SYSTEM_PROMPT = r"""You are an expert resume writer specializing in ATS-optimized, one-page LaTeX resumes for software engineers. You receive raw project summary Markdown files (from proj-summary/) and an optional job description.

## WORKFLOW

You MUST perform **Step 0 analysis** before generating LaTeX. Output your analysis in an `<analysis>` block, then output the LaTeX in a `<latex>` block.

### Step 0 — Analysis (MANDATORY, output in <analysis> block)

1. **Gap Check**: If a JD is provided, list which JD requirements are NOT covered by any project summary. If no JD, skip.
2. **JD Keyword Extraction**: Extract the top 15 technical keywords from the JD (languages, frameworks, tools, methodologies). If no JD, extract from project summaries instead.
3. **Project Ranking Table**: Score EVERY project on these 5 criteria (1-5 scale each):
   | Project | Unique JD Requirements | Problem-Type Match | Tech Stack Match | Role Type Match | Impact Relevance | TOTAL |
   Select the top 3-4 projects by total score. If no JD, rank by technical complexity and recency.
4. **Anchor Validation**: For each selected project, list the exact facts/metrics you will use. Every claim MUST have a source line from the summaries.

### Step 1 — LaTeX Resume Generation (output in <latex> block)

Generate a complete, compilable LaTeX resume using Jake's Resume template structure.

## TEMPLATE STRUCTURE (Jake's Resume — use this EXACTLY, do NOT deviate)

\documentclass[letterpaper,11pt]{article}
\usepackage{lmodern}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{textcomp}
\input{glyphtounicode}
\usepackage{fontawesome5}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

% Custom commands
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%% FONTAWESOME5 ICON REFERENCE — use ONLY these exact names:
%% \faPhone  \faEnvelope  \faLinkedin  \faGithub  \faGlobe
%% For project links: \faGithub\ ProjectName  OR  \faLink\ ProjectName
%% NEVER use: \faLinkedinSquare \faLinkedinIn \faPhoneAlt \faMobileAlt \faLink (unreliable)

## DOCUMENT BODY STRUCTURE (follow this EXACTLY)

After \begin{document}, the body MUST use EXACTLY these patterns.  Do NOT use \title{}, \maketitle, or any other structure.

### Header (centered, NOT \title)
\begin{center}
    \textbf{\Huge \scshape Full Name} \\ \vspace{1pt}
    \small \faPhone\ +91-XXXXXXXXXX \quad
    \href{mailto:email@example.com}{\faEnvelope\ email@example.com} \quad
    \href{https://linkedin.com/in/xxx}{\faLinkedin\ linkedin.com/in/xxx} \quad
    \href{https://github.com/xxx}{\faGithub\ github.com/xxx}
\end{center}

### Education section (uses \resumeSubHeadingListStart, NOT \resumeItemListStart)
\section{Education}
\resumeSubHeadingListStart
  \resumeSubheading
    {University Name}{GPA or Grade}
    {Degree Title}{Start Date -- End Date}
\resumeSubHeadingListEnd

### Experience section (uses \resumeSubHeadingListStart with nested \resumeItemListStart)
\section{Experience}
\resumeSubHeadingListStart
  \resumeSubheading
    {Job Title}{Start -- End}
    {Company Name}{}
    \resumeItemListStart
      \resumeItem{Bullet point about achievement}
    \resumeItemListEnd
\resumeSubHeadingListEnd

### Projects section (uses \resumeSubHeadingListStart with \resumeProjectHeading)
\section{Projects}
\resumeSubHeadingListStart
  \resumeProjectHeading
    {\textbf{\href{https://github.com/user/repo}{\faGithub\ Project Name}} $|$ \emph{Tech1, Tech2, Tech3}}{}
    \resumeItemListStart
      \resumeItem{What you built and how}
    \resumeItemListEnd
\resumeSubHeadingListEnd

### Technical Skills section (uses raw \begin{itemize}, NOT \resumeItemListStart)
\section{Technical Skills}
\begin{itemize}[leftmargin=0.15in, label={}]
  \small{\item{
    \textbf{Languages}{: Python, JavaScript, Java} \\
    \textbf{Frameworks}{: FastAPI, React, LangChain} \\
    \textbf{Tools}{: Docker, AWS, Git}
  }}
\end{itemize}

### Achievements section (uses \resumeItemListStart directly)
\section{Achievements}
\resumeItemListStart
  \resumeItem{Achievement description}
\resumeItemListEnd

## CRITICAL RULES

1. **ANTI-HALLUCINATION**: Only use data from the provided project summaries. Never fabricate metrics, experience, skills, or any facts not present in the summaries.
2. **ONE-PAGE**: Resume MUST fit on a single letter-size page. Max 3 bullet points per project (single line each, 80-100 chars). Only top 3-4 projects.
3. **FONT COMMANDS**: Use ONLY \textbf{}, \textit{}, \texttt{}. NEVER use \bf, \it, \tt, \bfseries, \itshape, \ttfamily, or old-style font commands.
4. **LaTeX SAFETY**: Every { must have a matching }. Never use \\ at the start of a line or on an empty line. Escape special characters: & % $ # _ { } ~ ^
5. **URL FORMAT**: Use \href{url}{Link} for project URLs. Never display full URL text.
6. **SECTIONS ORDER**: Header → Education (if provided) → Technical Skills → Projects → Experience (if provided)
7. **OMIT EMPTY SECTIONS**: If no education/experience data is available, completely omit that section. Do not leave empty sections.
8. **BULLET POINTS**: Start with strong action verbs (Developed, Architected, Implemented, Integrated, Optimized, Designed). Focus on technical implementation and architecture. Include specific technologies.
9. **CORRECT LIST WRAPPERS**: \resumeSubheading and \resumeProjectHeading go inside \resumeSubHeadingListStart/End. \resumeItem goes inside \resumeItemListStart/End. NEVER put \resumeSubheading inside \resumeItemListStart/End.
10. **NO \title or \maketitle**: The header MUST be a \begin{center}...\end{center} block. Never use \title{} or \maketitle.

## OUTPUT FORMAT

<analysis>
[Your Step 0 analysis here — gap check, keyword extraction, ranking table, anchor validation]
</analysis>

<latex>
[Complete, compilable LaTeX document here]
</latex>
"""


# ──────────────────────────────────────────────────────────────────────────────
# M2-v2: JSON-to-Template Resume Generation
# Claude outputs structured JSON → Python fills Jake's fixed template.
# This eliminates ALL LaTeX structural issues from freeform generation.
# ──────────────────────────────────────────────────────────────────────────────

import json as _json

RESUME_JSON_PROMPT = r"""You are an expert resume writer for software engineers. You receive raw project summary Markdown files and user profile data. Your job is to analyze the data and output structured JSON that will be used to fill a LaTeX resume template.

## WORKFLOW

### Step 0 — Analysis (MANDATORY, output in <analysis> block)

1. **Gap Check**: If a JD is provided, list which JD requirements are NOT covered by any project summary. If no JD, skip.
2. **JD Keyword Extraction**: Extract the top 15 technical keywords from the JD (languages, frameworks, tools, methodologies). If no JD, extract from project summaries instead.
3. **Project Ranking Table**: Score EVERY project on these 5 criteria (1-5 scale each):
   | Project | Unique JD Requirements | Problem-Type Match | Tech Stack Match | Role Type Match | Impact Relevance | TOTAL |
   Select the top 3-4 projects by total score. If no JD, rank by technical complexity and recency.
4. **Anchor Validation**: For each selected project, list the exact facts/metrics you will use. Every claim MUST have a source line from the summaries.

### Step 1 — Resume JSON (output in <resume_json> block)

Output a JSON object following this EXACT schema. Do NOT add extra fields. Every string value must be plain text (NO LaTeX commands, NO backslash escapes — the template engine handles all formatting).

```json
{
  "header": {
    "name": "Full Name",
    "phone": "+91-XXXXXXXXXX",
    "email": "email@example.com",
    "linkedin_url": "https://linkedin.com/in/xxx",
    "linkedin_display": "linkedin.com/in/xxx",
    "github_url": "https://github.com/xxx",
    "github_display": "github.com/xxx",
    "website_url": "https://example.com",
    "website_display": "example.com"
  },
  "education": [
    {
      "school": "University Name",
      "metric": "CGPA - 9.1",
      "degree": "Bachelor of Science in Data Science",
      "dates": "May 2023 -- May 2027"
    }
  ],
  "experience": [
    {
      "title": "Software Engineer Intern",
      "dates": "Sep 2025 -- Nov 2025",
      "company": "Presidio",
      "location": "",
      "highlights": [
        "Bullet starting with strong action verb (80-100 chars max)",
        "Another bullet point"
      ]
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "url": "https://github.com/user/repo",
      "technologies": "Python, FastAPI, Docker",
      "highlights": [
        "What you built and how",
        "Technical implementation detail",
        "Impact or outcome"
      ]
    }
  ],
  "skills": [
    {"category": "Languages", "items": "Python, SQL, JavaScript"},
    {"category": "Frameworks", "items": "FastAPI, React, LangChain"},
    {"category": "Developer Tools", "items": "Docker, AWS, Git"}
  ],
  "achievements": [
    "Achievement description (one line each)"
  ]
}
```

## CRITICAL RULES

1. **ANTI-HALLUCINATION**: Only use data from the provided project summaries and user profile. Never fabricate metrics, experience, skills, or any facts not in the source data.
2. **ONE-PAGE FIT**: Max 3 bullet points per project (single line each, 80-100 chars). Only top 3-4 projects. Keep experience bullets to 3-4 per role.
3. **PLAIN TEXT ONLY**: All string values must be plain text. NO LaTeX commands (no \textbf, no \href, no \\, no \%). The template engine adds all formatting. The ONLY exception: use -- (double hyphen) for date ranges.
4. **BULLET POINTS**: Start with strong action verbs (Developed, Architected, Implemented, Integrated, Optimized, Designed). Focus on technical implementation. Include specific technologies.
5. **SECTIONS ORDER**: Header → Education → Experience → Projects → Technical Skills → Achievements.
6. **OMIT EMPTY SECTIONS**: If no education/experience data available, use empty arrays []. Do not invent data.
7. **SKILL CATEGORIZATION**: Group skills into meaningful categories. Common categories: Languages, Frameworks, Databases, Developer Tools, Libraries, Other Skills, Certificates, Coursework.
8. **VALID JSON**: Output must be valid JSON. Use double quotes for strings. Escape any double quotes inside strings with \".

## OUTPUT FORMAT

<analysis>
[Your Step 0 analysis here]
</analysis>

<resume_json>
{...valid JSON object following the schema above...}
</resume_json>
"""


# Fixed preamble from Jake's Resume template — never changes
JAKES_PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}
\usepackage{lmodern}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{textcomp}
\input{glyphtounicode}
\usepackage{fontawesome5}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text values."""
    if not text:
        return ""
    # Order matters: backslash first to avoid double-escaping
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("$", "\\$")
    text = text.replace("#", "\\#")
    text = text.replace("_", "\\_")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("~", "\\textasciitilde{}")
    text = text.replace("^", "\\textasciicircum{}")
    return text


def _coerce_dict(val) -> dict:
    """Ensure val is a dict; parse JSON strings; return {} otherwise."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        import json as _json
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _coerce_list(val) -> list:
    """Ensure val is a list; parse JSON strings; return [] otherwise."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json as _json
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _build_header(header: dict) -> str:
    """Build the centered header block."""
    if not isinstance(header, dict):
        header = {}
    name = _escape_latex(header.get("name", ""))
    parts = []

    phone = header.get("phone", "")
    if phone:
        parts.append(f"\\small \\faPhone\\ {_escape_latex(phone)}")

    email = header.get("email", "")
    if email:
        parts.append(f"\\href{{mailto:{email}}}{{\\faEnvelope\\ {_escape_latex(email)}}}")

    linkedin_url = header.get("linkedin_url", "")
    linkedin_display = header.get("linkedin_display", "")
    if linkedin_url and linkedin_display:
        parts.append(f"\\href{{{linkedin_url}}}{{\\faLinkedin\\ {_escape_latex(linkedin_display)}}}")

    github_url = header.get("github_url", "")
    github_display = header.get("github_display", "")
    if github_url and github_display:
        parts.append(f"\\href{{{github_url}}}{{\\faGithub\\ {_escape_latex(github_display)}}}")

    website_url = header.get("website_url", "")
    website_display = header.get("website_display", "")
    if website_url and website_display:
        parts.append(f"\\href{{{website_url}}}{{\\faGlobe\\ {_escape_latex(website_display)}}}")

    contact_line = " \\quad\n    ".join(parts)

    return (
        "\\begin{center}\n"
        f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}\n"
        f"    {contact_line}\n"
        "\\end{center}"
    )


def _build_education(education: list) -> str:
    """Build the Education section."""
    if not education:
        return ""
    if not isinstance(education, list):
        return ""
    entries = []
    for edu in education:
        if not isinstance(edu, dict):
            continue
        school = _escape_latex(edu.get("school", ""))
        metric = _escape_latex(edu.get("metric", ""))
        degree = _escape_latex(edu.get("degree", ""))
        dates = _escape_latex(edu.get("dates", ""))
        entries.append(
            f"  \\resumeSubheading\n"
            f"    {{{school}}}{{{metric}}}\n"
            f"    {{{degree}}}{{{dates}}}"
        )
    body = "\n".join(entries)
    return (
        "\\section{Education}\n"
        "\\resumeSubHeadingListStart\n"
        f"{body}\n"
        "\\resumeSubHeadingListEnd"
    )


def _build_experience(experience: list) -> str:
    """Build the Experience section."""
    if not experience:
        return ""
    if not isinstance(experience, list):
        return ""
    entries = []
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        title = _escape_latex(exp.get("title", ""))
        dates = _escape_latex(exp.get("dates", ""))
        company = _escape_latex(exp.get("company", ""))
        location = _escape_latex(exp.get("location", ""))
        items = ""
        highlights = exp.get("highlights", [])
        if highlights:
            bullet_lines = "\n".join(
                f"      \\resumeItem{{{_escape_latex(h)}}}" for h in highlights
            )
            items = (
                f"\n    \\resumeItemListStart\n"
                f"{bullet_lines}\n"
                f"    \\resumeItemListEnd"
            )
        entries.append(
            f"  \\resumeSubheading\n"
            f"    {{{title}}}{{{dates}}}\n"
            f"    {{{company}}}{{{location}}}"
            f"{items}"
        )
    body = "\n\n".join(entries)
    return (
        "\\section{Experience}\n"
        "\\resumeSubHeadingListStart\n\n"
        f"{body}\n\n"
        "\\resumeSubHeadingListEnd"
    )


def _build_projects(projects: list) -> str:
    """Build the Projects section."""
    if not projects:
        return ""
    if not isinstance(projects, list):
        return ""
    entries = []
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        name = _escape_latex(proj.get("name", ""))
        url = proj.get("url", "")
        techs = _escape_latex(proj.get("technologies", ""))

        # Build the project heading: \textbf{\href{url}{\faGithub\ Name}} $|$ \emph{Tech}
        if url:
            heading = f"\\textbf{{\\href{{{url}}}{{\\faGithub\\ {name}}}}} $|$ \\emph{{{techs}}}"
        else:
            heading = f"\\textbf{{{name}}} $|$ \\emph{{{techs}}}"

        items = ""
        highlights = proj.get("highlights", [])
        if highlights:
            bullet_lines = "\n".join(
                f"      \\resumeItem{{{_escape_latex(h)}}}" for h in highlights
            )
            items = (
                f"\n    \\resumeItemListStart\n"
                f"{bullet_lines}\n"
                f"    \\resumeItemListEnd"
            )
        entries.append(
            f"  \\resumeProjectHeading\n"
            f"    {{{heading}}}{{}}"
            f"{items}"
        )
    body = "\n\n".join(entries)
    return (
        "\\section{Projects}\n"
        "\\resumeSubHeadingListStart\n\n"
        f"{body}\n\n"
        "\\resumeSubHeadingListEnd"
    )


def _build_skills(skills: list) -> str:
    """Build the Technical Skills section."""
    if not skills:
        return ""
    if not isinstance(skills, list):
        return ""
    skill_lines = []
    for i, skill in enumerate(skills):
        if not isinstance(skill, dict):
            continue
        cat = _escape_latex(skill.get("category", ""))
        items = _escape_latex(skill.get("items", ""))
        suffix = " \\\\" if i < len(skills) - 1 else ""
        skill_lines.append(f"    \\textbf{{{cat}}}{{: {items}}}{suffix}")
    body = "\n".join(skill_lines)
    return (
        "\\section{Technical Skills}\n"
        "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
        "  \\small{\\item{\n"
        f"{body}\n"
        "  }}\n"
        "\\end{itemize}"
    )


def _build_achievements(achievements: list) -> str:
    """Build the Achievements section."""
    if not achievements:
        return ""
    bullet_lines = "\n".join(
        f"  \\resumeItem{{{_escape_latex(a)}}}" for a in achievements
    )
    return (
        "\\section{Achievements}\n"
        "\\resumeItemListStart\n"
        f"{bullet_lines}\n"
        "\\resumeItemListEnd"
    )


def _fill_jakes_template(data: dict) -> str:
    """Build a complete Jake's Resume LaTeX document from structured JSON data.

    This approach is fundamentally more reliable than asking Claude to generate
    raw LaTeX because the document structure (preamble + macro definitions +
    section wrappers) is FIXED. Only text content comes from AI.
    """
    parts = [JAKES_PREAMBLE.strip(), "", "\\begin{document}", ""]

    # Header (always present)
    header = _coerce_dict(data.get("header", {}))
    parts.append(_build_header(header))

    # Education
    edu = _build_education(_coerce_list(data.get("education", [])))
    if edu:
        parts.append(edu)

    # Experience
    exp = _build_experience(_coerce_list(data.get("experience", [])))
    if exp:
        parts.append(exp)

    # Projects
    proj = _build_projects(_coerce_list(data.get("projects", [])))
    if proj:
        parts.append(proj)

    # Technical Skills
    skills = _build_skills(_coerce_list(data.get("skills", [])))
    if skills:
        parts.append(skills)

    # Achievements
    ach = _build_achievements(_coerce_list(data.get("achievements", [])))
    if ach:
        parts.append(ach)

    parts.append("\\end{document}")
    return "\n\n".join(parts) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# LaTeX Structural Sanitizer (LEGACY — kept for reference, no longer used)
# The JSON-to-template approach above makes these unnecessary.
# ──────────────────────────────────────────────────────────────────────────────

def _wrap_orphaned(
    latex: str,
    item_cmds: tuple,
    list_start: str,
    list_end: str,
    close_triggers: tuple,
) -> str:
    """
    Scan lines and wrap consecutive orphaned item_cmds in list_start / list_end.
    An orphaned command is one that appears outside list_start...list_end blocks.
    Inserts list_end before any close_trigger encountered while inside orphan list.
    """
    lines = latex.split("\n")
    result: List[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if list_start in stripped:
            in_list = True
            result.append(line)
            continue

        if list_end in stripped:
            in_list = False
            result.append(line)
            continue

        # Orphaned command — open wrapper before it
        if not in_list and any(cmd in stripped for cmd in item_cmds):
            indent = " " * (len(line) - len(line.lstrip(" ")))
            result.append(indent + list_start)
            in_list = True
            result.append(line)
            continue

        # Close trigger encountered while inside an implicit open list
        if in_list and any(t in stripped for t in close_triggers):
            result.append("    " + list_end)
            in_list = False
            result.append(line)
            continue

        result.append(line)

    # Document ended while still inside an implicitly opened list
    if in_list:
        result.append("    " + list_end)

    return "\n".join(result)


def _fix_orphaned_list_items(latex: str) -> str:
    """
    Two-pass fix for Jake's Resume macro environment issues.
    Only operates on the document BODY (after \\begin{document}) to avoid
    false-positives from \\newcommand definitions in the preamble that contain
    the same command substrings (e.g. \\resumeItem{ inside \\newcommand{\\resumeSubItem}).

    Pass 1 — wrap orphaned \\resumeProjectHeading / \\resumeSubheading in
              \\resumeSubHeadingListStart...\\resumeSubHeadingListEnd
    Pass 2 — wrap orphaned \\resumeItem / \\resumeSubItem in
              \\resumeItemListStart...\\resumeItemListEnd
    Both macros expand to \\item internally, so being outside their respective
    itemize wrappers produces the 'Lonely \\item' LaTeX error.
    """
    split_marker = r"\begin{document}"
    idx = latex.find(split_marker)
    if idx == -1:
        # No \begin{document}; apply to whole string as fallback
        preamble, body = "", latex
    else:
        preamble, body = latex[:idx + len(split_marker)], latex[idx + len(split_marker):]

    # Pass 1: SubHeading wrappers (must run before Pass 2)
    body = _wrap_orphaned(
        body,
        item_cmds=("\\resumeProjectHeading{", "\\resumeSubheading{"),
        list_start="\\resumeSubHeadingListStart",
        list_end="\\resumeSubHeadingListEnd",
        close_triggers=("\\section{", "\\end{document}"),
    )
    # Pass 2: Item wrappers
    body = _wrap_orphaned(
        body,
        item_cmds=("\\resumeItem{", "\\resumeSubItem{"),
        list_start="\\resumeItemListStart",
        list_end="\\resumeItemListEnd",
        close_triggers=(
            "\\resumeProjectHeading{",
            "\\resumeSubheading{",
            "\\resumeSubHeadingListEnd",
            "\\resumeSubHeadingListStart",
            "\\section{",
            "\\end{document}",
        ),
    )
    return preamble + body


def _strip_preamble_macro_calls(latex: str) -> str:
    """
    Remove stray resume-macro CALLS from the preamble (before \\begin{document}).

    Claude sometimes hallucinates \\resumeItemListStart / \\resumeItemListEnd
    (and similar) directly inside the preamble — before the macros are even
    defined — causing '! Undefined control sequence' on those lines.

    We split at \\begin{document}, scrub any line in the preamble that is ONLY
    a resume-environment call (not a \\newcommand / \\renewcommand definition),
    then rejoin.
    """
    # Stray-call patterns: lines whose meaningful content is one of these
    stray_pattern = re.compile(
        r"^\s*(\\resumeItemListStart|\\resumeItemListEnd"
        r"|\\resumeSubHeadingListStart|\\resumeSubHeadingListEnd"
        r"|\\resumeSubheading\b|\\resumeProjectHeading\b"
        r"|\\resumeItem\b|\\resumeSubItem\b)\s*$"
    )

    split_marker = r"\begin{document}"
    idx = latex.find(split_marker)
    if idx == -1:
        # No \begin{document} — scrub the whole thing (will be caught by fix 4)
        return latex

    preamble = latex[:idx]
    body = latex[idx:]

    cleaned_preamble_lines = []
    for line in preamble.splitlines():
        if stray_pattern.match(line):
            logger.debug("Removed stray preamble macro call", line=line.strip())
        else:
            cleaned_preamble_lines.append(line)

    return "\n".join(cleaned_preamble_lines) + "\n" + body


def _normalize_command_calls(latex: str) -> str:
    """
    Rejoin resume commands that Claude split from their opening brace onto a new line.

    Claude sometimes writes:
        \\resumeSubheading
        {arg1}{arg2}{arg3}
    instead of:
        \\resumeSubheading{arg1}{arg2}{arg3}

    This causes the _wrap_orphaned check (which looks for '\\resumeSubheading{')
    to miss the orphaned command entirely.
    """
    for cmd in (r"\\resumeSubheading", r"\\resumeProjectHeading", r"\\resumeSubSubheading"):
        # Join: <cmd>\n<optional-spaces>{ → <cmd>{
        latex = re.sub(cmd + r"\n[ \t]*\{", cmd.replace("\\\\", "\\") + "{", latex)
    return latex


def _fix_missing_subheading_arg(latex: str) -> str:
    r"""
    Pad \\resumeSubheading calls to exactly 4 arguments.

    The macro is defined as [4] (four args: institution, date, degree, location).
    When Claude emits fewer, LaTeX consumes the next token as the missing arg
    and cascades into dozens of secondary errors.
    """
    # 3-arg → add 1 empty
    latex = re.sub(
        r"(\\resumeSubheading)(\{[^{}]*\})(\{[^{}]*\})(\{[^{}]*\})(?!\{)",
        r"\1\2\3\4{}",
        latex,
    )
    # 2-arg → add 2 empty
    latex = re.sub(
        r"(\\resumeSubheading)(\{[^{}]*\})(\{[^{}]*\})(?!\{)",
        r"\1\2\3{}{}",
        latex,
    )
    return latex


def _fix_cr_encoding(latex: str) -> str:
    """Fix carriage-return corruption of backslash-r in LaTeX commands.

    The Bedrock Converse API sometimes returns `\\r` (literal backslash + r)
    as a CR character (0x0D) in Claude's generated text.  This turns
    `\\resumeSubheading` into `<CR>esumeSubheading`, which is invalid.

    Strategy:
    1. Any CR (0x0D) immediately before a lowercase letter was almost
       certainly a `\\r` LaTeX command prefix — restore the backslash.
    2. Normalise remaining CRLF / lone-CR line endings to LF.
    """
    # Step 1: CR + lowercase-letter → backslash + 'r' + letter
    latex = re.sub('\r([a-z])', lambda m: '\\r' + m.group(1), latex)
    # Step 2: normalise line endings
    latex = latex.replace('\r\n', '\n').replace('\r', '\n')
    return latex


def _extract_items_from_subheading_arg(latex: str) -> str:
    r"""
    Fix \resumeSubheading{a}{b}{c}{ \resumeItemListStart ... \resumeItemListEnd }
    and  \resumeProjectHeading{title}{ \resumeItemListStart ... \resumeItemListEnd }

    Claude sometimes nests the bullet-point list INSIDE an argument of
    \resumeSubheading (4th arg) or \resumeProjectHeading (2nd arg).
    The macros place those args inside \textit{\small ...} or tabular cells,
    so an \item there causes 'Lonely \item' or 'Not allowed in LR mode'.
    This function extracts the list environment and moves it AFTER the call.
    """
    # Fix \resumeSubheading{a}{b}{c}{ items }
    sub_pattern = re.compile(
        r"(\\resumeSubheading\s*"
        r"\{[^}]*\}\s*"           # arg 1
        r"\{[^}]*\}\s*"           # arg 2
        r"\{[^}]*\})"             # arg 3
        r"\s*\{\s*"               # opening brace of arg 4
        r"(\\resumeItemListStart.*?\\resumeItemListEnd)"  # extracted list
        r"\s*\}",                 # closing brace of arg 4
        re.DOTALL,
    )
    latex = sub_pattern.sub(r"\1{}\n\2", latex)

    # Fix \resumeProjectHeading{title}{ items }
    proj_pattern = re.compile(
        r"(\\resumeProjectHeading\s*"
        r"\{[^}]*\})"             # arg 1
        r"\s*\{\s*"               # opening brace of arg 2
        r"(\\resumeItemListStart.*?\\resumeItemListEnd)"  # extracted list
        r"\s*\}",                 # closing brace of arg 2
        re.DOTALL,
    )
    latex = proj_pattern.sub(r"\1{}\n\2", latex)

    return latex


def _fix_wrong_list_wrappers(latex: str) -> str:
    r"""
    Fix \resumeSubheading / \resumeProjectHeading inside \resumeItemListStart/End.

    Claude sometimes wraps subheading-level commands in the wrong list
    environment.  This replaces the enclosing \resumeItemListStart/End
    with \resumeSubHeadingListStart/End when the block contains
    \resumeSubheading or \resumeProjectHeading but no \resumeItem.
    """
    subheading_pat = re.compile(
        r"\\(resumeSubheading|resumeProjectHeading)\b"
    )
    item_only_pat = re.compile(r"\\resumeItem\b")

    pattern = re.compile(
        r"(\\resumeItemListStart)(.*?)(\\resumeItemListEnd)",
        re.DOTALL,
    )

    def _replace(m):
        inner = m.group(2)
        if subheading_pat.search(inner) and not item_only_pat.search(inner):
            return "\\resumeSubHeadingListStart" + inner + "\\resumeSubHeadingListEnd"
        return m.group(0)

    return pattern.sub(_replace, latex)


def _remove_empty_list_envs(latex: str) -> str:
    r"""
    Remove list environment pairs that contain no \item (directly or via macros).

    Checks \resumeItemListStart...\resumeItemListEnd and
    \resumeSubHeadingListStart...\resumeSubHeadingListEnd blocks.
    If the inner content lacks any \item, \resumeItem, \resumeSubItem,
    \resumeSubheading, or \resumeProjectHeading, the entire block is removed.
    Runs in a loop until stable (removing inner can expose outer).
    """
    item_pattern = re.compile(
        r"\\(item|resumeItem|resumeSubItem|resumeSubheading|resumeProjectHeading)\b"
    )
    # Process both kinds of list environments
    env_pairs = [
        (r"\\resumeItemListStart", r"\\resumeItemListEnd"),
        (r"\\resumeSubHeadingListStart", r"\\resumeSubHeadingListEnd"),
    ]
    changed = True
    while changed:
        changed = False
        for start_pat, end_pat in env_pairs:
            # Non-greedy match: find start...end pairs with no item inside
            pattern = re.compile(start_pat + r"(.*?)" + end_pat, re.DOTALL)
            for m in pattern.finditer(latex):
                inner = m.group(1)
                if not item_pattern.search(inner):
                    latex = latex[:m.start()] + latex[m.end():]
                    changed = True
                    break  # restart after mutation
    return latex


def _remove_unbalanced_list_ends(latex: str) -> str:
    r"""Remove unmatched \resumeItemListEnd and \resumeSubHeadingListEnd.

    After the other sanitizer passes, Claude's original wrong wrappers can
    leave behind orphaned closing commands that have no opening counterpart.
    This function walks through each list env type: if at any point the
    running balance (opens - closes) goes negative, the extra close is removed.
    """
    env_pairs = [
        (r"\resumeItemListStart", r"\resumeItemListEnd"),
        (r"\resumeSubHeadingListStart", r"\resumeSubHeadingListEnd"),
    ]
    for start_cmd, end_cmd in env_pairs:
        lines = latex.split("\n")
        result: List[str] = []
        depth = 0
        for line in lines:
            stripped = line.strip()
            if start_cmd in stripped:
                depth += 1
            if end_cmd in stripped:
                if depth <= 0:
                    # Orphaned close — skip this line
                    continue
                depth -= 1
            result.append(line)
        latex = "\n".join(result)
    return latex


def _sanitize_latex(latex: str) -> str:
    """
    Apply structural and syntactic fixes to Claude-generated Jake's Resume LaTeX
    before passing it to the compiler.

    Fixes applied:
    0. Strip stray resume-macro CALLS from the preamble (before \\begin{document})
       — prevents '! Undefined control sequence' on lines like \\resumeItemListStart
       that Claude sometimes injects before the \\newcommand definitions.
    0b. Normalize split command calls: joins \\resumeSubheading / \\resumeProjectHeading
        that Claude wrote on a separate line from their opening brace.
    0c. Add missing 4th argument to \\resumeSubheading calls that only have 3 args.
    1. Wrap orphaned \\resumeItem / \\resumeProjectHeading outside list environments
       (prevents 'Lonely \\item' errors — the most common Claude mistake).
    2. Remove empty list environments that would trigger 'Something's wrong—
       perhaps a missing \\item' errors.
    3. Remove standalone \\\\ lines (causes 'There's no line here to end').
    4. Ensure \\end{document} is present.
    """
    # Fix -1: restore CR-corrupted \r sequences from Bedrock API
    latex = _fix_cr_encoding(latex)

    # Fix 0: scrub stray macro calls from preamble
    latex = _strip_preamble_macro_calls(latex)

    # Fix 0b: normalize split command calls before wrap detection
    latex = _normalize_command_calls(latex)

    # Fix 0c: add missing 4th arg to \resumeSubheading
    latex = _fix_missing_subheading_arg(latex)

    # --- Split preamble / body to protect \newcommand definitions ---
    # Many regex fixes below use patterns like \resumeItemListStart(.*?)\resumeItemListEnd
    # which would accidentally match across \newcommand{\resumeItemListStart}...
    # \newcommand{\resumeItemListEnd} in the preamble, destroying the definitions.
    begin_doc = latex.find(r"\begin{document}")
    if begin_doc == -1:
        return latex
    preamble = latex[:begin_doc]
    body = latex[begin_doc:]

    # Fix 0d-pre: extract list environments nested inside \resumeSubheading 4th arg
    body = _extract_items_from_subheading_arg(body)

    # Fix 0d: swap wrong list wrappers (body only)
    body = _fix_wrong_list_wrappers(body)

    # Fix 1: structural list wrapping (two passes — SubHeading first, then Item)
    # _fix_orphaned_list_items already splits internally, but pass body to be safe
    body = _fix_orphaned_list_items(preamble + body)[len(preamble):]

    # Fix 2: remove empty list environments (body only, loop until stable)
    prev = None
    while prev != body:
        prev = body
        body = re.sub(
            r"\\resumeItemListStart\s*\\resumeItemListEnd", "", body)
        body = re.sub(
            r"\\resumeSubHeadingListStart\s*\\resumeSubHeadingListEnd", "", body)
        body = re.sub(
            r"\\begin\{itemize\}(?:\[[^\]]*\])?\s*\\end\{itemize\}", "", body)

    # Collapse runs of 3+ blank lines into 2
    body = re.sub(r"\n{3,}", "\n\n", body)

    # Fix 2b: structural validation (body only)
    body = _remove_empty_list_envs(body)

    # Fix 2c: remove orphaned list-end closings with no matching open
    body = _remove_unbalanced_list_ends(body)

    # Fix 3: remove standalone \\ on otherwise blank lines
    body = re.sub(r"^[ \t]*\\\\[ \t]*$", "", body, flags=re.MULTILINE)

    # Rejoin
    latex = preamble + body

    # Fix 4: ensure \end{document} exists at the end of the document
    if r"\end{document}" not in latex:
        latex = latex.rstrip() + "\n\\end{document}\n"

    return latex


async def list_project_summaries(user_id: str) -> List[str]:
    """
    List and download all project summary .md files from S3 for a user.

    Reads all {userId}/*-summary.md keys from S3 bucket.

    Args:
        user_id: The user's ID

    Returns:
        List of raw .md content strings
    """
    from app.services.s3_service import s3_service

    all_keys = await s3_service.list_objects(prefix=f"{user_id}/")
    summary_keys = [k for k in all_keys if k.endswith("-summary.md") or k.endswith("_summary.md")]

    if not summary_keys:
        # Also try .md files that might not have the -summary suffix
        summary_keys = [k for k in all_keys if k.endswith(".md")]

    if not summary_keys:
        return []

    summaries = []
    for key in summary_keys:
        try:
            content_bytes = await s3_service.download_file(key)
            summaries.append(content_bytes.decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to download summary", key=key, error=str(e))

    return summaries


async def generate_resume_from_summaries(
    user_id: str,
    jd: Optional[str] = None,
    personal_info: Optional[Dict[str, Any]] = None,
    education: Optional[List[Dict[str, Any]]] = None,
    experience: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[str]] = None,
    certifications: Optional[List[Dict[str, Any]]] = None,
) -> M2GenerationResult:
    """
    M2 pipeline: Read S3 summaries → Claude Step 0 analysis → LaTeX output → compile → upload.

    Args:
        user_id: User ID whose summaries to read
        jd: Optional job description text
        personal_info: Dict with name, email, phone, linkedin_url, website, github, location
        education: List of education dicts
        experience: List of experience dicts
        skills: List of skill strings
        certifications: List of cert dicts

    Returns:
        M2GenerationResult with latex, analysis, and URLs
    """
    from app.services.s3_service import s3_service
    from app.services.latex_service import latex_service
    from app.services.dynamo_service import dynamo_service

    # 1. Retrieve all project summaries from S3
    summaries = await list_project_summaries(user_id)
    if not summaries:
        raise ValueError("No project summaries found. Run GitHub ingestion first.")

    logger.info("Retrieved project summaries", user_id=user_id, count=len(summaries))

    # 2. Build context block
    projects_context = "\n\n---\n\n".join(summaries)

    # Build personal/education/experience context
    extra_context_parts = []
    if personal_info:
        info_lines = [f"  {k}: {v}" for k, v in personal_info.items() if v]
        if info_lines:
            extra_context_parts.append("## Personal Information\n" + "\n".join(info_lines))

    if education:
        edu_lines = []
        for i, edu in enumerate(education, 1):
            edu_lines.append(f"  Education {i}: {edu.get('degree', '')} in {edu.get('field', '')} from {edu.get('school', '')} ({edu.get('dates', '')})")
            if edu.get('gpa'):
                edu_lines.append(f"    GPA: {edu['gpa']}")
            if edu.get('location'):
                edu_lines.append(f"    Location: {edu['location']}")
        if edu_lines:
            extra_context_parts.append("## Education\n" + "\n".join(edu_lines))

    if experience:
        exp_lines = []
        for i, exp in enumerate(experience, 1):
            exp_lines.append(f"  Experience {i}: {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('dates', '')})")
            for h in exp.get("highlights", []):
                exp_lines.append(f"    - {h}")
        if exp_lines:
            extra_context_parts.append("## Work Experience\n" + "\n".join(exp_lines))

    if skills:
        extra_context_parts.append(f"## Technical Skills\n  {', '.join(skills)}")

    if certifications:
        cert_lines = []
        for cert in certifications:
            cert_lines.append(f"  - {cert.get('name', '')} ({cert.get('issuer', '')})")
        if cert_lines:
            extra_context_parts.append("## Certifications\n" + "\n".join(cert_lines))

    extra_context = "\n\n".join(extra_context_parts)

    # 3. Build user message (ask for JSON, not raw LaTeX)
    user_message = f"""## Project Summaries (from ingested GitHub repos)

{projects_context}

{extra_context}

## Job Description
{jd or 'No JD provided — generate a strong base resume ranking projects by complexity and recency.'}

Perform Step 0 analysis first (gap check → JD keyword extraction → project ranking table → anchor validation), then output the resume JSON."""

    # 4. Call Claude via Bedrock — JSON output mode
    response = await bedrock_client.generate(
        prompt=user_message,
        system_prompt=RESUME_JSON_PROMPT,
        max_tokens=8192,
        temperature=0.3,
    )

    # Normalize CR/CRLF in raw response before parsing
    response = response.replace('\r\n', '\n').replace('\r', '\n')

    # 5. Parse response — extract <analysis> and <resume_json> blocks
    analysis = ""
    resume_data = {}

    analysis_match = re.search(r"<analysis>(.*?)</analysis>", response, re.DOTALL)
    if analysis_match:
        analysis = analysis_match.group(1).strip()

    json_match = re.search(r"<resume_json>\s*(.*?)\s*</resume_json>", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Fallback: try to extract JSON from markdown code blocks
        md_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if md_match:
            json_str = md_match.group(1).strip()
        else:
            raise ValueError("Failed to extract resume JSON from Claude's response.")

    try:
        resume_data = _json.loads(json_str)
    except _json.JSONDecodeError as e:
        logger.error("Failed to parse resume JSON", error=str(e), json_preview=json_str[:500])
        raise ValueError(f"Claude returned invalid JSON: {e}")

    logger.info("Claude JSON generation complete", analysis_len=len(analysis), keys=list(resume_data.keys()))

    # 5b. Build LaTeX from JSON using Jake's fixed template
    latex_content = _fill_jakes_template(resume_data)
    logger.info("Template filled", latex_len=len(latex_content))

    # 6. Compile LaTeX → PDF
    resume_id = dynamo_service.generate_id()
    output_filename = f"resume_{resume_id[:8]}"

    compilation_result = await latex_service.compile_latex(
        latex_content=latex_content,
        output_filename=output_filename,
        use_docker=False,
    )

    pdf_url = None
    tex_url = None

    # 7. Upload to S3
    pdf_s3_key = f"{user_id}/resumes/{resume_id}.pdf"
    tex_s3_key = f"{user_id}/resumes/{resume_id}.tex"

    # Always upload .tex source
    await s3_service.upload_file(
        key=tex_s3_key,
        data=latex_content.encode("utf-8"),
        content_type="text/plain",
    )
    tex_url = await s3_service.get_presigned_url(tex_s3_key)

    if compilation_result.success and compilation_result.pdf_path:
        # Read the compiled PDF and upload to our key structure
        from pathlib import Path

        pdf_bytes = Path(compilation_result.pdf_path).read_bytes()
        await s3_service.upload_file(
            key=pdf_s3_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )
        pdf_url = await s3_service.get_presigned_url(pdf_s3_key)
        compilation_error_msg = None
    else:
        # Extract the most meaningful error from the compilation log.
        # Strategy:
        #  1. Find the first "! ..." error line in the log.
        #  2. Also grab the immediately following "l.<n> ..." line which gives the
        #     exact line number and offending content — essential for debugging.
        compilation_error_msg = None
        log_text = getattr(compilation_result, "log", "") or ""
        log_lines = log_text.splitlines()

        # Collect all unique "! …" errors and their following context lines
        error_snippets: list[str] = []
        for i, log_line in enumerate(log_lines):
            stripped = log_line.strip()
            if stripped.startswith("! "):
                snippet = stripped
                # Grab the next non-blank line (usually "l.<n> <content>")
                for j in range(i + 1, min(i + 4, len(log_lines))):
                    next_line = log_lines[j].strip()
                    if next_line:
                        snippet += f"  →  {next_line}"
                        break
                error_snippets.append(snippet)
                if len(error_snippets) >= 3:   # cap at 3 errors to keep it readable
                    break

        if error_snippets:
            compilation_error_msg = " | ".join(error_snippets)
        elif compilation_result.errors:
            compilation_error_msg = compilation_result.errors[0].message
        else:
            compilation_error_msg = "PDF compilation failed — LaTeX source saved."

        logger.warning(
            "LaTeX compilation failed",
            first_error=error_snippets[0] if error_snippets else compilation_error_msg,
            all_errors=[e.message for e in compilation_result.errors],
            log_tail=log_text[-2000:] if log_text else "",  # last 2000 chars for full context
        )

    # 8. Store resume metadata in DynamoDB
    now = dynamo_service.now_iso()
    resume_item = {
        "userId": user_id,
        "resumeId": resume_id,
        "name": f"Resume {now[:10]}",
        "status": "compiled" if compilation_result.success else "generated",
        "latexContent": latex_content,
        "analysis": analysis,
        "pdfS3Key": pdf_s3_key if compilation_result.success else None,
        "texS3Key": tex_s3_key,
        "jobDescription": jd[:500] if jd else None,
        "errorMessage": compilation_error_msg,
        "createdAt": now,
        "updatedAt": now,
    }
    await dynamo_service.put_item("Resumes", resume_item)

    return M2GenerationResult(
        latex_content=latex_content,
        analysis=analysis,
        resume_id=resume_id,
        pdf_url=pdf_url,
        tex_url=tex_url,
        compilation_error=compilation_error_msg,
    )


# Global instance
resume_agent = ResumeGenerationAgent()

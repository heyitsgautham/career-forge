"""
Resume Generation Agent
=======================
Generates ATS-friendly LaTeX resumes using Gemini with strict grounding.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

from app.services.gemini_client import gemini_client


logger = structlog.get_logger()


@dataclass
class GenerationResult:
    """Result of resume generation."""
    latex_content: str
    warnings: List[str]
    changes_made: List[str]
    tokens_used: int


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
            response = await gemini_client.generate_content(
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
            result = await gemini_client.generate_json(
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


# Global instance
resume_agent = ResumeGenerationAgent()

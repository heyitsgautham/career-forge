"""
LaTeX Compilation Service
=========================
Compiles LaTeX to PDF using Docker-sandboxed TeX Live.
"""

from typing import Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import asyncio
import tempfile
import shutil
import uuid
import re
import structlog

from app.core.config import settings


logger = structlog.get_logger()


@dataclass
class CompilationError:
    """Parsed LaTeX compilation error."""
    line: int
    column: int
    message: str
    severity: str  # "error" or "warning"
    suggestion: Optional[str] = None


@dataclass
class CompilationResult:
    """Result of LaTeX compilation."""
    success: bool
    pdf_path: Optional[str]
    log: str
    errors: List[CompilationError]
    warnings: List[str]


class LaTeXCompilationService:
    """
    Service for compiling LaTeX documents to PDF.
    Uses Docker for sandboxed compilation.
    """
    
    # Common LaTeX errors and suggestions
    ERROR_PATTERNS = [
        (r"! LaTeX Error: (.+)", "LaTeX Error"),
        (r"! Undefined control sequence\.\s*l\.(\d+)", "Undefined command"),
        (r"! Missing \$ inserted", "Math mode error - missing $"),
        (r"! Missing { inserted", "Missing opening brace"),
        (r"! Missing } inserted", "Missing closing brace"),
        (r"! Extra }, or forgotten \$", "Extra closing brace or missing $"),
        (r"! Package (.+) Error: (.+)", "Package error"),
        (r"Overfull \\hbox", "Overfull box - text too wide"),
        (r"Underfull \\hbox", "Underfull box - text too sparse"),
    ]
    
    def __init__(self):
        self.timeout = settings.LATEX_COMPILER_TIMEOUT
        self.memory_limit = settings.LATEX_COMPILER_MEMORY_LIMIT
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def compile_latex(
        self,
        latex_content: str,
        output_filename: Optional[str] = None,
        use_docker: bool = True,
    ) -> CompilationResult:
        """
        Compile LaTeX content to PDF.
        
        Args:
            latex_content: LaTeX source code
            output_filename: Optional output filename (without extension)
            use_docker: Use Docker for sandboxed compilation
            
        Returns:
            CompilationResult with success status and paths
        """
        # Generate unique filename if not provided
        if not output_filename:
            output_filename = f"resume_{uuid.uuid4().hex[:8]}"
        
        # Create temporary directory for compilation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tex_file = temp_path / f"{output_filename}.tex"
            
            # Write LaTeX content
            tex_file.write_text(latex_content, encoding="utf-8")
            
            # Compile
            if use_docker:
                result = await self._compile_with_docker(temp_path, output_filename)
            else:
                result = await self._compile_local(temp_path, output_filename)
            
            # If successful, copy PDF to permanent location
            if result.success:
                pdf_file = temp_path / f"{output_filename}.pdf"
                if pdf_file.exists():
                    permanent_path = self.upload_dir / "pdfs" / f"{output_filename}.pdf"
                    permanent_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(pdf_file, permanent_path)
                    result.pdf_path = str(permanent_path)
            
            return result
    
    async def _compile_with_docker(
        self,
        work_dir: Path,
        filename: str,
    ) -> CompilationResult:
        """Compile using Docker-sandboxed TeX Live."""
        
        # Docker command with security restrictions
        docker_cmd = [
            "docker", "run", "--rm",
            f"--memory={self.memory_limit}",
            "--cpus=1",
            "--network=none",  # No network access
            "--read-only",  # Read-only filesystem
            "--tmpfs=/tmp:rw,size=64m",  # Temporary write space
            "-v", f"{work_dir}:/data:rw",
            "-w", "/data",
            "texlive/texlive:latest",
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"{filename}.tex"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return CompilationResult(
                    success=False,
                    pdf_path=None,
                    log="Compilation timed out",
                    errors=[CompilationError(
                        line=0, column=0,
                        message="Compilation exceeded time limit",
                        severity="error",
                        suggestion="Simplify the document or check for infinite loops"
                    )],
                    warnings=[],
                )
            
            log_content = stdout.decode("utf-8", errors="replace")
            
            # Check for PDF output
            pdf_exists = (work_dir / f"{filename}.pdf").exists()
            
            # Parse errors and warnings
            errors, warnings = self._parse_log(log_content)
            
            return CompilationResult(
                success=pdf_exists and process.returncode == 0,
                pdf_path=None,  # Will be set by caller
                log=log_content,
                errors=errors,
                warnings=warnings,
            )
            
        except FileNotFoundError:
            logger.warning("Docker not found, falling back to local compilation")
            return await self._compile_local(work_dir, filename)
        except Exception as e:
            logger.error(f"Docker compilation failed: {e}")
            return CompilationResult(
                success=False,
                pdf_path=None,
                log=str(e),
                errors=[CompilationError(
                    line=0, column=0,
                    message=str(e),
                    severity="error"
                )],
                warnings=[],
            )
    
    async def _compile_local(
        self,
        work_dir: Path,
        filename: str,
    ) -> CompilationResult:
        """Compile using local pdflatex installation."""
        
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"{filename}.tex"
        ]
        
        try:
            # On Windows, asyncio subprocess doesn't work well, use online compiler directly
            import sys
            if sys.platform == 'win32':
                logger.info("Windows detected, skipping local pdflatex, using online compiler")
                raise FileNotFoundError("pdflatex not supported on Windows in async mode")
                
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return CompilationResult(
                    success=False,
                    pdf_path=None,
                    log="Compilation timed out",
                    errors=[CompilationError(
                        line=0, column=0,
                        message="Compilation exceeded time limit",
                        severity="error"
                    )],
                    warnings=[],
                )
            
            log_content = stdout.decode("utf-8", errors="replace")
            pdf_exists = (work_dir / f"{filename}.pdf").exists()
            errors, warnings = self._parse_log(log_content)
            
            return CompilationResult(
                success=pdf_exists and process.returncode == 0,
                pdf_path=None,
                log=log_content,
                errors=errors,
                warnings=warnings,
            )
            
        except FileNotFoundError:
            # Fall back to online compilation if local tools not available
            logger.info("Local pdflatex not found, using online compiler")
            return await self._compile_online(work_dir, filename)
    
    async def _compile_online(
        self,
        work_dir: Path,
        filename: str,
    ) -> CompilationResult:
        """Compile using latex.online free API."""
        import aiohttp
        
        tex_file = work_dir / f"{filename}.tex"
        latex_content = tex_file.read_text(encoding="utf-8")
        
        # Use latex.online API
        url = "https://latex.ytotech.com/builds/sync"
        
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare the request
                data = aiohttp.FormData()
                data.add_field('compiler', 'pdflatex')
                data.add_field('target', f'{filename}.tex')
                data.add_field(
                    f'{filename}.tex',
                    latex_content,
                    filename=f'{filename}.tex',
                    content_type='text/plain'
                )
                
                async with session.post(url, data=data, timeout=30) as response:
                    # Read the response content
                    content = await response.read()
                    
                    # Check if it's a PDF (starts with %PDF)
                    if content.startswith(b'%PDF'):
                        # It's a PDF! Save it
                        pdf_file = work_dir / f"{filename}.pdf"
                        pdf_file.write_bytes(content)
                        
                        return CompilationResult(
                            success=True,
                            pdf_path=None,
                            log="Compiled successfully using online service",
                            errors=[],
                            warnings=[],
                        )
                    else:
                        # Not a PDF, must be an error message (likely JSON)
                        try:
                            error_text = content.decode('utf-8', errors='replace')
                            # Try to parse as JSON to extract log
                            import json
                            try:
                                error_json = json.loads(error_text)
                                log_info = error_json.get('log_files', {})
                                error_detail = error_json.get('error', 'COMPILATION_ERROR')
                                
                                # Get the actual LaTeX error log if available
                                latex_log = log_info.get('output.log', 'No detailed log available')
                                
                                return CompilationResult(
                                    success=False,
                                    pdf_path=None,
                                    log=f"LaTeX Compilation Error:\n{latex_log}",
                                    errors=[CompilationError(
                                        line=0, column=0,
                                        message=f"{error_detail}: Check LaTeX syntax. The template may have issues.",
                                        severity="error",
                                        suggestion="Try a different template or check for LaTeX syntax errors"
                                    )],
                                    warnings=[],
                                )
                            except json.JSONDecodeError:
                                # Not JSON, return as plain text
                                pass
                        except Exception:
                            error_text = f"HTTP {response.status}: Unknown error"
                        
                        return CompilationResult(
                            success=False,
                            pdf_path=None,
                            log=f"Online compilation failed: {error_text}",
                            errors=[CompilationError(
                                line=0, column=0,
                                message=f"Compilation error: {error_text[:200]}",
                                severity="error"
                            )],
                            warnings=[],
                        )
                        
        except asyncio.TimeoutError:
            return CompilationResult(
                success=False,
                pdf_path=None,
                log="Online compilation timed out",
                errors=[CompilationError(
                    line=0, column=0,
                    message="Compilation exceeded time limit",
                    severity="error"
                )],
                warnings=[],
            )
        except Exception as e:
            logger.error(f"Online compilation failed: {e}")
            return CompilationResult(
                success=False,
                pdf_path=None,
                log=f"Online compilation error: {str(e)}",
                errors=[CompilationError(
                    line=0, column=0,
                    message=str(e),
                    severity="error",
                    suggestion="pdflatex not found. Please install TeX Live or use Docker."
                )],
                warnings=[],
            )
    
    def _parse_log(self, log: str) -> Tuple[List[CompilationError], List[str]]:
        """Parse TeX log file for errors and warnings."""
        errors = []
        warnings = []
        
        lines = log.split("\n")
        
        for i, line in enumerate(lines):
            # Check for error patterns
            for pattern, error_type in self.ERROR_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    # Try to extract line number
                    line_num = 0
                    line_match = re.search(r"l\.(\d+)", line) or re.search(r"line (\d+)", line)
                    if line_match:
                        line_num = int(line_match.group(1))
                    
                    if "Overfull" in pattern or "Underfull" in pattern:
                        warnings.append(f"{error_type}: {line.strip()}")
                    else:
                        errors.append(CompilationError(
                            line=line_num,
                            column=0,
                            message=line.strip(),
                            severity="error",
                            suggestion=self._get_error_suggestion(error_type),
                        ))
        
        return errors, warnings
    
    def _get_error_suggestion(self, error_type: str) -> Optional[str]:
        """Get suggestion for common errors."""
        suggestions = {
            "Undefined command": "Check spelling of command or add required package",
            "Math mode error - missing $": "Wrap mathematical expressions in $ symbols",
            "Missing opening brace": "Add { before the content",
            "Missing closing brace": "Add } after the content",
            "Extra closing brace or missing $": "Remove extra } or add missing $",
        }
        return suggestions.get(error_type)
    
    def validate_latex_safety(self, latex: str) -> Tuple[bool, List[str]]:
        """
        Validate LaTeX content for security issues.
        
        Args:
            latex: LaTeX source code
            
        Returns:
            (is_safe, list of issues)
        """
        issues = []
        
        # Dangerous commands that could execute arbitrary code
        dangerous_patterns = [
            (r"\\write18", "Shell escape command detected"),
            (r"\\immediate\\write18", "Immediate shell escape detected"),
            (r"\\input\|", "Shell pipe in input detected"),
            (r"\\include\|", "Shell pipe in include detected"),
            (r"\\openin", "File input operation detected"),
            (r"\\openout", "File output operation detected"),
            (r"\\catcode", "Category code manipulation detected"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, latex, re.IGNORECASE):
                issues.append(message)
        
        return len(issues) == 0, issues


# Global instance
latex_service = LaTeXCompilationService()

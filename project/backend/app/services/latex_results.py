"""
LaTeX compilation results
=========================
The result types every compile path returns, the common failure results, and
the pdflatex log parser that turns a log into errors with line numbers.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


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


def failure(message: str, log: str, suggestion: Optional[str] = None) -> CompilationResult:
    """A failed compile with one error and no line number."""
    return CompilationResult(
        success=False,
        pdf_path=None,
        log=log,
        errors=[
            CompilationError(
                line=0, column=0, message=message, severity="error", suggestion=suggestion
            )
        ],
        warnings=[],
    )


def timed_out(log: str = "Compilation timed out", suggestion: Optional[str] = None):
    """The result for a compile that ran past its time limit."""
    return failure("Compilation exceeded time limit", log, suggestion)


# Common LaTeX errors and the label each gets in the parsed result
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

_SUGGESTIONS = {
    "Undefined command": "Check spelling of command or add required package",
    "Math mode error - missing $": "Wrap mathematical expressions in $ symbols",
    "Missing opening brace": "Add { before the content",
    "Missing closing brace": "Add } after the content",
    "Extra closing brace or missing $": "Remove extra } or add missing $",
}


def error_suggestion(error_type: str) -> Optional[str]:
    """A fix to try for a known error label."""
    return _SUGGESTIONS.get(error_type)


def parse_log(log: str) -> Tuple[List[CompilationError], List[str]]:
    """Errors (with line numbers where the log has them) and box warnings from a TeX log."""
    errors: List[CompilationError] = []
    warnings: List[str] = []
    for line in log.split("\n"):
        for pattern, error_type in ERROR_PATTERNS:
            if not re.search(pattern, line):
                continue
            if "Overfull" in pattern or "Underfull" in pattern:
                warnings.append(f"{error_type}: {line.strip()}")
                continue
            line_match = re.search(r"l\.(\d+)", line) or re.search(r"line (\d+)", line)
            errors.append(
                CompilationError(
                    line=int(line_match.group(1)) if line_match else 0,
                    column=0,
                    message=line.strip(),
                    severity="error",
                    suggestion=error_suggestion(error_type),
                )
            )
    return errors, warnings

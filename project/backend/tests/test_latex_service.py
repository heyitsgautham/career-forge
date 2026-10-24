"""LaTeX log parsing and the safety check run before user LaTeX is compiled."""

import pytest

from app.services.latex_service import latex_service

SAFE_DOC = r"""\documentclass{article}
\usepackage{hyperref}
\begin{document}
\section{Projects} Built a FastAPI service \href{https://example.com}{demo}.
\end{document}
"""


def test_safe_resume_passes():
    assert latex_service.validate_latex_safety(SAFE_DOC) == (True, [])


@pytest.mark.parametrize(
    "snippet,issue",
    [
        (r"\immediate\write18{rm -rf /}", "Immediate shell escape detected"),
        (r"\write18{ls}", "Shell escape command detected"),
        (r"\input|ls", "Shell pipe in input detected"),
        (r"\openin\myfile=secret.txt", "File input operation detected"),
        (r"\openout\f=out.txt", "File output operation detected"),
        (r"\catcode`\@=11", "Category code manipulation detected"),
    ],
)
def test_dangerous_commands_are_flagged(snippet, issue):
    is_safe, issues = latex_service.validate_latex_safety(SAFE_DOC + snippet)
    assert not is_safe
    assert issue in issues


def test_log_errors_carry_line_numbers_and_suggestions():
    log = "\n".join(
        [
            "This is pdfTeX",
            "! Undefined control sequence. l.42 \\foo",
            "! LaTeX Error: File `missing.sty' not found.",
            "Overfull \\hbox (12.0pt too wide) in paragraph at lines 10--11",
        ]
    )
    errors, warnings = latex_service._parse_log(log)
    assert [e.line for e in errors] == [42, 0]
    assert errors[0].suggestion == "Check spelling of command or add required package"
    assert errors[1].suggestion is None
    assert all(e.severity == "error" for e in errors)
    assert warnings == [
        "Overfull box - text too wide: Overfull \\hbox (12.0pt too wide) in paragraph at lines 10--11"
    ]


def test_clean_log_has_no_findings():
    assert latex_service._parse_log("Output written on resume.pdf (1 page).") == ([], [])


@pytest.mark.parametrize(
    "snippet",
    [
        r"\input{/etc/passwd}",
        r"\include{../../.env}",
        r"\input {~/.aws/credentials}",
        r"\InputIfFileExists{/etc/hosts}{}{}",
    ],
)
def test_reading_files_outside_the_build_dir_is_flagged(snippet):
    is_safe, issues = latex_service.validate_latex_safety(SAFE_DOC + snippet)
    assert not is_safe
    assert "Input from an absolute or parent path detected" in issues


def test_relative_input_inside_the_build_dir_is_allowed():
    assert latex_service.validate_latex_safety(SAFE_DOC + r"\input{sections/projects}")[0]

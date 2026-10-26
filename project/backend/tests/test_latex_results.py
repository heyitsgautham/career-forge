"""Failure result helpers and the log parser's line numbers."""

from app.services.latex_results import error_suggestion, failure, parse_log, timed_out


def test_failure_carries_one_error_without_a_line():
    result = failure("pdflatex crashed", log="segfault", suggestion="Retry")
    assert not result.success and result.pdf_path is None
    assert result.log == "segfault"
    assert [(e.line, e.message, e.suggestion) for e in result.errors] == [
        (0, "pdflatex crashed", "Retry")
    ]


def test_timed_out_names_the_time_limit():
    result = timed_out(log="Online compilation timed out")
    assert result.errors[0].message == "Compilation exceeded time limit"
    assert result.log == "Online compilation timed out"


def test_parse_log_reads_line_numbers_in_either_form():
    errors, _ = parse_log("! LaTeX Error: Missing \\begin{document} on input line 7.")
    assert errors[0].line == 7
    assert error_suggestion("Missing closing brace") == "Add } after the content"
    assert error_suggestion("Something new") is None

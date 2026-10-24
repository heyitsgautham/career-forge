"""LinkedIn URL validation and the Playwright scripts built from it.

The scraper writes a Python script that embeds the profile URL and runs it in
a subprocess, so the URL must never be able to change that script's code.
"""

import ast
import subprocess

import pytest

from app.services import linkedin_scraper
from app.services.linkedin_scraper import parse_linkedin_url

INJECTION = 'https://www.linkedin.com/in/x"\nimport os; os.system("touch /tmp/pwned")\n#'


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.linkedin.com/in/asha-example/", "https://www.linkedin.com/in/asha-example"),
        ("https://linkedin.com/in/asha-example", "https://www.linkedin.com/in/asha-example"),
        (
            "http://in.linkedin.com/in/asha_example-123",
            "https://www.linkedin.com/in/asha_example-123",
        ),
        ("asha-example", "https://www.linkedin.com/in/asha-example"),
        ("linkedin.com/in/asha-example", "https://www.linkedin.com/in/asha-example"),
        (
            "https://www.linkedin.com/in/asha-example?utm_source=share&utm_medium=android",
            "https://www.linkedin.com/in/asha-example",
        ),
    ],
)
def test_valid_profiles_are_normalised(raw, expected):
    assert parse_linkedin_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        None,
        "https://example.com/in/asha",
        "https://evil.example/?next=linkedin.com/in/asha",
        "https://www.linkedin.com/company/sample-labs",
        INJECTION,
        'https://www.linkedin.com/in/asha"\nimport os',
        'asha"; import os',
        "https://www.linkedin.com/in/a",
    ],
)
def test_anything_else_is_rejected(raw):
    assert parse_linkedin_url(raw) is None


@pytest.fixture
def captured_scripts(monkeypatch):
    scripts = []

    def fake_run(args, **kwargs):
        with open(args[1], encoding="utf-8") as f:
            scripts.append(f.read())
        return subprocess.CompletedProcess(args, 0, stdout='{"ok": true}' + " " * 200, stderr="")

    monkeypatch.setattr(linkedin_scraper.subprocess, "run", fake_run)
    monkeypatch.setattr(linkedin_scraper, "_get_chrome_user_data_dir", lambda: 'C:\\Users\\a"b')
    return scripts


def assigned_strings(script):
    tree = ast.parse(script)
    return {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


@pytest.mark.parametrize("runner", ["_run_playwright_script", "_run_playwright_profile_script"])
def test_urls_are_embedded_as_string_literals(captured_scripts, runner):
    getattr(linkedin_scraper, runner)(INJECTION)
    script = captured_scripts[0]
    values = assigned_strings(script)
    assert values["profile_url"] == INJECTION
    assert values["chrome_user_data"] == 'C:\\Users\\a"b'
    system_calls = [
        node
        for node in ast.walk(ast.parse(script))
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "system"
    ]
    assert system_calls == []


def test_import_route_rejects_a_crafted_url_before_scraping(client, auth, monkeypatch):
    called = []

    async def fake_scrape(url):
        called.append(url)
        return {}

    monkeypatch.setattr(linkedin_scraper, "scrape_linkedin_profile", fake_scrape)
    response = client.post(
        "/api/auth/linkedin/import-profile",
        json={"linkedin_url": INJECTION},
        headers=auth["headers"],
    )
    assert response.status_code == 400
    assert called == []

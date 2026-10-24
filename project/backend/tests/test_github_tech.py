"""Technology detection from dependency manifests and summary rendering."""

import json

import pytest

from app.services.github_tech import (
    parse_package_json,
    parse_pyproject_toml,
    parse_repo_url,
    parse_requirements_txt,
    render_summary_md,
)


def test_package_json_maps_dependencies_and_adds_node():
    manifest = json.dumps(
        {"dependencies": {"react": "^18", "next": "14"}, "devDependencies": {"tailwindcss": "3"}}
    )
    techs = parse_package_json(manifest)
    assert {"React", "Next.js", "Node.js", "JavaScript"} <= set(techs)
    assert len(techs) == len(set(techs))


def test_invalid_package_json_yields_nothing():
    assert parse_package_json("{not json") == []


def test_requirements_txt_skips_comments_and_pins():
    techs = parse_requirements_txt(
        "# web\nfastapi==0.110.0\nuvicorn[standard]>=0.24\n\nunknown-pkg==1\n"
    )
    assert set(techs) == {"Python", "FastAPI"}


def test_pyproject_detects_known_packages():
    techs = parse_pyproject_toml('[project]\ndependencies = ["fastapi>=0.100", "pydantic"]\n')
    assert "Python" in techs
    assert "FastAPI" in techs


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/asha-example/job-scout", "asha-example/job-scout"),
        ("https://github.com/asha-example/job-scout.git", "asha-example/job-scout"),
        ("https://github.com/asha-example/job-scout/tree/main/src/", "asha-example/job-scout"),
    ],
)
def test_repo_url_parses_owner_and_name(url, expected):
    assert parse_repo_url(url) == expected


@pytest.mark.parametrize("url", ["https://gitlab.com/a/b", "https://github.com/only-owner"])
def test_repo_url_rejects_other_urls(url):
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        parse_repo_url(url)


def test_summary_markdown_lists_every_section():
    md = render_summary_md(
        "job-scout",
        {
            "oneLiner": "Ranks internship postings",
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "capabilities": ["Scrapes 4 portals"],
            "highlights": ["500 postings a day"],
        },
    )
    lines = md.split("\n")
    assert lines[0] == "# job-scout"
    assert "- **One-Liner:** Ranks internship postings" in lines
    assert "- **Frameworks:** FastAPI" in lines
    assert "- **Infrastructure/Tools:** " in lines
    assert lines[-1] == "- 500 postings a day"
    assert "- Scrapes 4 portals" in lines


@pytest.mark.parametrize(
    "line",
    [
        "fastapi~=0.110",
        "fastapi>0.100",
        "fastapi!=0.99",
        "fastapi ; python_version >= '3.11'",
        "FastAPI==0.110.0",
        "fastapi @ git+https://github.com/tiangolo/fastapi",
    ],
)
def test_requirements_txt_understands_every_version_specifier(line):
    assert "FastAPI" in parse_requirements_txt(line)

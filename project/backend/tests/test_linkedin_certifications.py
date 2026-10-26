"""Parsing the LinkedIn certifications page, offline, from synthetic markup."""

import asyncio

from app.services import linkedin_certifications
from app.services.linkedin_certifications import parse_certifications_html


def cert_item(name, issuer, issued, credential_id=None, url=None):
    credential = (
        f'<div class="t-14"><span aria-hidden="true">Credential ID {credential_id}</span></div>'
        if credential_id
        else ""
    )
    link = f'<a href="{url}"><span>Show credential</span></a>' if url else ""
    return f"""
    <li class="pvs-list__paged-list-item artdeco-list__item">
      <div class="display-flex flex-column">
        <div class="display-flex align-items-center mr1 t-bold"><span aria-hidden="true">{name}</span></div>
        <span class="t-14 t-normal"><span aria-hidden="true">{issuer}</span></span>
        <span class="t-14 t-normal t-black--light">
          <span class="pvs-entity__caption-wrapper" aria-hidden="true">Issued {issued}</span>
        </span>
        {credential}
        {link}
      </div>
    </li>"""


PAGE = (
    "<html><title>Certifications | LinkedIn</title><body><ul>"
    + cert_item(
        "AWS  Cloud   Practitioner",
        "Amazon Web Services",
        "Jan 2025",
        "ABC-123",
        "https://aws.example/c/1",
    )
    + cert_item("CKA", "CNCF", "Mar 2024")
    + cert_item("ab", "Too short to be a name", "Mar 2024")
    + "</ul></body></html>"
)


def test_reads_name_issuer_date_credential_and_link():
    certs = parse_certifications_html(PAGE)
    assert certs[0] == {
        "name": "AWS Cloud Practitioner",
        "issuer": "Amazon Web Services",
        "date": "Jan 2025",
        "credential_id": "ABC-123",
        "url": "https://aws.example/c/1",
    }


def test_skips_names_too_short_to_be_real():
    assert [c["name"] for c in parse_certifications_html(PAGE)] == ["AWS Cloud Practitioner", "CKA"]


def test_entries_without_a_credential_have_no_credential_fields():
    cka = parse_certifications_html(PAGE)[1]
    assert "credential_id" not in cka and "url" not in cka


def test_falls_back_to_certification_blocks_when_the_list_markup_changes():
    html = """<div class="certification-card"><p>Terraform Associate</p><p>HashiCorp</p>
    <p>Issued Feb 2025</p></div>"""
    assert parse_certifications_html(html) == [
        {"name": "Terraform Associate", "issuer": "HashiCorp", "date": "Issued Feb 2025"}
    ]


def test_an_empty_page_has_no_certifications():
    assert parse_certifications_html("<html><body></body></html>") == []


def test_scrape_runs_the_browser_script_and_parses_its_html(monkeypatch):
    monkeypatch.setattr(linkedin_certifications, "_run_playwright_script", lambda url: PAGE)
    certs = asyncio.run(
        linkedin_certifications.scrape_linkedin_certifications("https://www.linkedin.com/in/x")
    )
    assert len(certs) == 2

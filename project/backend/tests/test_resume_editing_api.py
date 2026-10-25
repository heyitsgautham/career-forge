"""Resume compile, LaTeX editing, AI edit streaming and downloads on both backends."""

import asyncio
import json
from types import SimpleNamespace

import boto3
import pytest

from app.core.config import settings
from app.services import latex_service as latex_module
from app.services.dynamo_service import dynamo_service
from app.services.latex_service import CompilationError

DOC = "\\documentclass{article}\\begin{document}Asha\\end{document}"


@pytest.fixture
def compiler(monkeypatch, tmp_path):
    state = {"mode": "ok", "latex": []}

    async def compile_latex(latex_content, output_filename=None, use_docker=True):
        state["latex"].append(latex_content)
        if state["mode"] == "missing":
            raise FileNotFoundError("pdflatex")
        if state["mode"] == "crash":
            raise RuntimeError("disk full")
        if state["mode"] == "fail":
            return SimpleNamespace(
                success=False,
                pdf_path=None,
                log="log",
                warnings=[],
                errors=[
                    CompilationError(3, 0, "Missing }", "error"),
                    CompilationError(4, 0, "Extra $", "error"),
                ],
            )
        pdf = tmp_path / f"{output_filename}.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return SimpleNamespace(
            success=True, pdf_path=str(pdf), log="ok", warnings=["Overfull"], errors=[]
        )

    monkeypatch.setattr(latex_module.latex_service, "compile_latex", compile_latex)
    return state


def dynamo_resume(user_id, **fields):
    item = {
        "userId": user_id,
        "resumeId": "r1",
        "name": "My Resume",
        "status": "generated",
        **fields,
    }
    asyncio.run(dynamo_service.put_item("Resumes", item))
    return "r1"


def stored(user_id):
    return asyncio.run(dynamo_service.get_item("Resumes", {"userId": user_id, "resumeId": "r1"}))


# ── DynamoDB backend ────────────────────────────────────────────────────────


def test_dynamo_compile_success_records_the_pdf_key(dynamo_client, dynamo_auth, compiler):
    uid, h = dynamo_auth["user_id"], dynamo_auth["headers"]
    dynamo_resume(uid, latexContent=DOC)
    body = dynamo_client.post("/api/resumes/r1/compile", headers=h).json()
    assert body["status"] == "compiled"
    assert "compiled/resume_r1.pdf" in body["pdf_url"]
    assert stored(uid)["pdfS3Key"] == "compiled/resume_r1.pdf"


def test_dynamo_compile_uses_the_body_latex_when_given(dynamo_client, dynamo_auth, compiler):
    dynamo_resume(dynamo_auth["user_id"], latexContent=DOC)
    dynamo_client.post(
        "/api/resumes/r1/compile",
        json={"latex_content": "OVERRIDE"},
        headers=dynamo_auth["headers"],
    )
    assert compiler["latex"] == ["OVERRIDE"]


@pytest.mark.parametrize(
    "mode,status,message",
    [
        ("fail", "error", "Missing }; Extra $"),
        ("missing", "error", "LaTeX compiler not available. Install TeX Live or use Overleaf."),
        ("crash", "error", "disk full"),
    ],
)
def test_dynamo_compile_failures(dynamo_client, dynamo_auth, compiler, mode, status, message):
    dynamo_resume(dynamo_auth["user_id"], latexContent=DOC)
    compiler["mode"] = mode
    body = dynamo_client.post("/api/resumes/r1/compile", headers=dynamo_auth["headers"]).json()
    assert (body["status"], body["error_message"]) == (status, message)


def test_dynamo_compile_rejects_unsafe_or_missing_latex(dynamo_client, dynamo_auth, compiler):
    uid, h = dynamo_auth["user_id"], dynamo_auth["headers"]
    dynamo_resume(uid)
    assert dynamo_client.post("/api/resumes/r1/compile", headers=h).status_code == 400
    r = dynamo_client.post(
        "/api/resumes/r1/compile", json={"latex_content": DOC + "\\write18{ls}"}, headers=h
    )
    assert r.status_code == 400
    assert "Unsafe LaTeX" in r.json()["detail"]
    assert compiler["latex"] == []
    assert dynamo_client.post("/api/resumes/missing/compile", headers=h).status_code == 404


def test_dynamo_latex_edits_sync_to_s3(dynamo_client, dynamo_auth):
    uid, h = dynamo_auth["user_id"], dynamo_auth["headers"]
    dynamo_resume(uid, latexContent="old", texS3Key="u/resumes/r1.tex", pdfS3Key="u/resumes/r1.pdf")
    body = dynamo_client.put(
        "/api/resumes/r1/latex", json={"latex_content": "new"}, headers=h
    ).json()
    assert body["id"] == "r1"
    assert stored(uid)["latexContent"] == "new"
    s3 = boto3.client("s3", region_name="us-east-1")
    assert s3.get_object(Bucket=settings.S3_BUCKET, Key="u/resumes/r1.tex")["Body"].read() == b"new"

    assert dynamo_client.patch("/api/resumes/r1/latex?latex_content=patched", headers=h).json() == {
        "message": "LaTeX updated"
    }
    item = stored(uid)
    assert item["latexContent"] == "patched"
    assert "pdfS3Key" not in item


def test_dynamo_edits_of_missing_resumes_are_404(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    assert (
        dynamo_client.put(
            "/api/resumes/nope/latex", json={"latex_content": "x"}, headers=h
        ).status_code
        == 404
    )
    assert (
        dynamo_client.patch("/api/resumes/nope/latex?latex_content=x", headers=h).status_code == 404
    )


def test_dynamo_tex_download_prefers_s3_then_stored_latex(dynamo_client, dynamo_auth):
    uid, h = dynamo_auth["user_id"], dynamo_auth["headers"]
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket=settings.S3_BUCKET, Key="k.tex", Body=b"from s3"
    )
    dynamo_resume(uid, texS3Key="k.tex", latexContent="from dynamo")
    r = dynamo_client.get("/api/resumes/r1/tex", headers=h)
    assert r.content == b"from s3"
    assert 'filename="My_Resume.tex"' in r.headers["content-disposition"]

    dynamo_resume(uid, texS3Key="missing.tex", latexContent="from dynamo")
    assert dynamo_client.get("/api/resumes/r1/tex", headers=h).content == b"from dynamo"

    dynamo_resume(uid)
    assert dynamo_client.get("/api/resumes/r1/tex", headers=h).status_code == 404


def test_dynamo_pdf_links(dynamo_client, dynamo_auth):
    uid, h = dynamo_auth["user_id"], dynamo_auth["headers"]
    dynamo_resume(uid)
    assert dynamo_client.get("/api/resumes/r1/pdf-url", headers=h).status_code == 400
    dynamo_resume(uid, pdfS3Key="u/r1.pdf")
    url = dynamo_client.get("/api/resumes/r1/pdf-url", headers=h).json()["url"]
    assert "u/r1.pdf" in url and "inline" in url
    r = dynamo_client.get("/api/resumes/r1/pdf", headers=h, follow_redirects=False)
    assert r.status_code == 307
    assert "u/r1.pdf" in r.headers["location"]
    dynamo_resume(uid, pdfS3Key="/local/r1.pdf")
    assert dynamo_client.get("/api/resumes/r1/pdf-url", headers=h).status_code == 400


def sse_events(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_ai_edit_streams_the_explanation_then_the_latex(dynamo_client, dynamo_auth, bedrock):
    dynamo_resume(dynamo_auth["user_id"])
    bedrock.reply("I shortened your summary to one line.\n<latex>\\documentclass{article}</latex>")
    r = dynamo_client.post(
        "/api/resumes/r1/ai-edit",
        json={"message": "shorten", "latex_content": DOC},
        headers=dynamo_auth["headers"],
    )
    events = sse_events(r.text)
    text = "".join(d["text"] for e, d in events if e == "delta")
    assert text == "I shortened your summary to one line.\n"
    assert "<latex" not in text
    assert ("latex", {"latex": "\\documentclass{article}"}) in events
    assert events[-1][0] == "done"
    assert 'resume named "My Resume"' in bedrock.calls[0]["system"][0]["text"]
    assert "User instruction: shorten" in bedrock.prompts[0]


def test_ai_edit_without_a_latex_block_sends_all_text(client, auth, bedrock):
    rid = client.post("/api/resumes", json={"name": "Mine"}, headers=auth["headers"]).json()["id"]
    bedrock.reply("I could not find a summary section.")
    events = sse_events(
        client.post(
            f"/api/resumes/{rid}/ai-edit",
            json={"message": "m", "latex_content": DOC},
            headers=auth["headers"],
        ).text
    )
    assert (
        "".join(d["text"] for e, d in events if e == "delta")
        == "I could not find a summary section."
    )
    assert [e for e, _ in events if e == "latex"] == []


def test_ai_edit_reports_stream_errors(dynamo_client, dynamo_auth, bedrock):
    dynamo_resume(dynamo_auth["user_id"])
    bedrock.reply(RuntimeError("throttled"))
    events = sse_events(
        dynamo_client.post(
            "/api/resumes/r1/ai-edit",
            json={"message": "m", "latex_content": DOC},
            headers=dynamo_auth["headers"],
        ).text
    )
    assert events == [("error", {"message": "throttled"}), ("done", {})]
    assert (
        dynamo_client.post(
            "/api/resumes/x/ai-edit",
            json={"message": "m", "latex_content": DOC},
            headers=dynamo_auth["headers"],
        ).status_code
        == 404
    )


# ── SQLite backend ──────────────────────────────────────────────────────────


def sqlite_resume(client, auth):
    h = auth["headers"]
    rid = client.post("/api/resumes", json={"name": "My Resume"}, headers=h).json()["id"]
    client.put(f"/api/resumes/{rid}/latex", json={"latex_content": DOC}, headers=h)
    return rid


def test_sqlite_compile_and_download(client, auth, compiler):
    h = auth["headers"]
    rid = sqlite_resume(client, auth)
    body = client.post(f"/api/resumes/{rid}/compile", headers=h).json()
    assert body["status"] == "compiled"
    assert body["pdf_url"].startswith("/uploads/pdfs/resume_")
    assert client.get(f"/api/resumes/{rid}", headers=h).json()["status"] == "compiled"
    r = client.get(f"/api/resumes/{rid}/tex", headers=h)
    assert r.content == DOC.encode()


@pytest.mark.parametrize(
    "mode,message",
    [
        ("fail", "Missing }; Extra $"),
        ("missing", "LaTeX compiler not available"),
        ("crash", "disk full"),
    ],
)
def test_sqlite_compile_failures(client, auth, compiler, mode, message):
    rid = sqlite_resume(client, auth)
    compiler["mode"] = mode
    body = client.post(f"/api/resumes/{rid}/compile", headers=auth["headers"]).json()
    assert body["status"] == "error"
    assert body["error_message"].startswith(message)


def test_sqlite_edits_and_missing_content(client, auth):
    h = auth["headers"]
    rid = client.post("/api/resumes", json={"name": "Blank"}, headers=h).json()["id"]
    assert client.post(f"/api/resumes/{rid}/compile", headers=h).status_code == 400
    assert client.get(f"/api/resumes/{rid}/tex", headers=h).status_code == 404
    assert client.patch(f"/api/resumes/{rid}/latex?latex_content=x", headers=h).json() == {
        "message": "LaTeX updated"
    }
    assert client.get(f"/api/resumes/{rid}", headers=h).json()["latex_content"] == "x"
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        client.put(
            f"/api/resumes/{missing}/latex", json={"latex_content": "x"}, headers=h
        ).status_code
        == 404
    )
    assert (
        client.patch(f"/api/resumes/{missing}/latex?latex_content=x", headers=h).status_code == 404
    )
    assert client.get(f"/api/resumes/{missing}/tex", headers=h).status_code == 404
    assert client.post(f"/api/resumes/{missing}/compile", headers=h).status_code == 404
    assert client.get(f"/api/resumes/{rid}/pdf-url", headers=h).status_code == 501

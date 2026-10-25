"""LaTeX compilation paths with the subprocess and the online compiler faked."""

import asyncio
import json
from pathlib import Path

import aiohttp
import boto3
import pytest

from app.core.config import settings
from app.services import latex_service as latex_module
from app.services.latex_service import LaTeXCompilationService

DOC = r"\documentclass{article}\begin{document}Hi\end{document}"


class FakeProcess:
    def __init__(self, returncode=0, stdout=b"Output written on resume.pdf", hang=False):
        self.returncode = returncode
        self._stdout = stdout
        self.hang = hang
        self.killed = False

    async def communicate(self):
        if self.hang:
            await asyncio.sleep(10)
        return self._stdout, b""

    def kill(self):
        self.killed = True


@pytest.fixture
def subprocess_exec(monkeypatch):
    """Fake create_subprocess_exec. Set state['missing'] to a program name to raise FileNotFoundError."""
    state = {"calls": [], "missing": set(), "process": FakeProcess(), "write_pdf": True}

    async def fake_exec(*cmd, cwd=None, **kwargs):
        state["calls"].append((cmd, cwd))
        if cmd[0] in state["missing"]:
            raise FileNotFoundError(cmd[0])
        work_dir = Path(cwd) if cwd else Path(cmd[cmd.index("-v") + 1].split(":")[0])
        if state["write_pdf"]:
            name = cmd[-1].removesuffix(".tex")
            (work_dir / f"{name}.pdf").write_bytes(b"%PDF-1.4 synthetic")
        return state["process"]

    monkeypatch.setattr(latex_module.asyncio, "create_subprocess_exec", fake_exec)
    return state


@pytest.fixture
def service(tmp_path, aws):
    # Successful compiles upload to S3, so the service always runs against moto
    svc = LaTeXCompilationService()
    svc.upload_dir = tmp_path / "uploads"
    return svc


async def test_docker_compile_is_sandboxed_and_uploads_to_s3(service, subprocess_exec, aws):
    result = await service.compile_latex(DOC, output_filename="resume_test")
    assert result.success
    assert Path(result.pdf_path).read_bytes() == b"%PDF-1.4 synthetic"

    cmd, _ = subprocess_exec["calls"][0]
    assert cmd[:3] == ("docker", "run", "--rm")
    assert "--network=none" in cmd and "--read-only" in cmd

    s3 = boto3.client("s3", region_name="us-east-1")
    keys = {o["Key"] for o in s3.list_objects_v2(Bucket=settings.S3_BUCKET)["Contents"]}
    assert keys == {"compiled/resume_test.pdf", "compiled/resume_test.tex"}


async def test_s3_failure_does_not_fail_the_compile(service, subprocess_exec, monkeypatch):
    from app.services.s3_service import s3_service

    async def broken(**kwargs):
        raise RuntimeError("no bucket")

    monkeypatch.setattr(s3_service, "upload_file", broken)
    assert (await service.compile_latex(DOC, use_docker=False)).success


async def test_local_compile_runs_pdflatex_in_the_work_dir(service, subprocess_exec):
    result = await service.compile_latex(DOC, use_docker=False)
    cmd, cwd = subprocess_exec["calls"][0]
    assert cmd[0] == "pdflatex" and "-halt-on-error" in cmd
    assert cwd is not None
    assert result.success
    assert result.pdf_path.endswith(".pdf")


async def test_errors_in_the_log_fail_the_compile(service, subprocess_exec):
    subprocess_exec["process"] = FakeProcess(returncode=1, stdout=b"! Missing $ inserted.\nl.4")
    subprocess_exec["write_pdf"] = False
    result = await service.compile_latex(DOC, use_docker=False)
    assert not result.success
    assert result.pdf_path is None
    assert result.errors[0].suggestion == "Wrap mathematical expressions in $ symbols"


@pytest.mark.parametrize("use_docker", [True, False])
async def test_timeouts_kill_the_process(service, subprocess_exec, use_docker):
    service.timeout = 0.01
    subprocess_exec["process"] = FakeProcess(hang=True)
    result = await service.compile_latex(DOC, use_docker=use_docker)
    assert not result.success
    assert result.log == "Compilation timed out"
    assert subprocess_exec["process"].killed


async def test_missing_docker_falls_back_to_local_then_online(
    service, subprocess_exec, monkeypatch
):
    online = []

    async def fake_online(work_dir, filename):
        online.append(filename)
        return latex_module.CompilationResult(
            success=False, pdf_path=None, log="online", errors=[], warnings=[]
        )

    monkeypatch.setattr(service, "_compile_online", fake_online)
    subprocess_exec["missing"] = {"docker"}
    assert (await service.compile_latex(DOC, output_filename="r1")).success
    assert [c[0][0] for c in subprocess_exec["calls"]] == ["docker", "pdflatex"]

    subprocess_exec["missing"] = {"docker", "pdflatex"}
    result = await service.compile_latex(DOC, output_filename="r2")
    assert result.log == "online"
    assert online == ["r2"]


async def test_unexpected_docker_errors_are_reported(service, monkeypatch):
    async def boom(*cmd, **kwargs):
        raise PermissionError("docker socket")

    monkeypatch.setattr(latex_module.asyncio, "create_subprocess_exec", boom)
    result = await service.compile_latex(DOC)
    assert not result.success
    assert result.errors[0].message == "docker socket"


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    async def read(self):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.posted = []

    def post(self, url, data=None, timeout=None):
        self.posted.append(url)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def online(monkeypatch, tmp_path):
    def use(response):
        session = FakeSession(response)
        monkeypatch.setattr(aiohttp, "ClientSession", lambda: session)
        (tmp_path / "r.tex").write_text(DOC)
        return session

    return use


async def test_online_compile_saves_the_returned_pdf(service, online, tmp_path):
    session = online(FakeResponse(b"%PDF-1.5 online"))
    result = await service._compile_online(tmp_path, "r")
    assert result.success
    assert (tmp_path / "r.pdf").read_bytes() == b"%PDF-1.5 online"
    assert session.posted == ["https://latex.ytotech.com/builds/sync"]


async def test_online_compile_reports_json_errors(service, online, tmp_path):
    body = json.dumps(
        {"error": "COMPILATION_ERROR", "log_files": {"output.log": "! Undefined"}}
    ).encode()
    online(FakeResponse(body, status=400))
    result = await service._compile_online(tmp_path, "r")
    assert not result.success
    assert "! Undefined" in result.log
    assert result.errors[0].message.startswith("COMPILATION_ERROR")


async def test_online_compile_reports_plain_text_errors(service, online, tmp_path):
    online(FakeResponse(b"Bad gateway", status=502))
    result = await service._compile_online(tmp_path, "r")
    assert result.log == "Online compilation failed: Bad gateway"


@pytest.mark.parametrize(
    "exc,log",
    [
        (asyncio.TimeoutError(), "Online compilation timed out"),
        (OSError("dns"), "Online compilation error: dns"),
    ],
)
async def test_online_compile_network_failures(service, online, tmp_path, exc, log):
    online(exc)
    assert (await service._compile_online(tmp_path, "r")).log == log

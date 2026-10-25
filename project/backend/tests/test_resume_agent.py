"""Resume generation pipeline with Bedrock, S3, DynamoDB and the LaTeX compiler faked."""

import json
from types import SimpleNamespace

import boto3
import pytest

from app.core.config import settings
from app.services import latex_service as latex_module
from app.services import resume_agent
from app.services.dynamo_service import dynamo_service
from app.services.latex_service import CompilationError

RESUME_JSON = {
    "header": {"name": "Asha Example", "email": "asha@example.com"},
    "education": [{"school": "Example Institute", "degree": "B.Tech", "dates": "2022 -- 2026"}],
    "projects": [{"name": "job-scout", "tech": "Python", "bullets": ["Ranks 500 postings a day"]}],
    "skills": {"Languages": "Python, SQL"},
}


def claude_reply(data=RESUME_JSON, analysis="Picked job-scout for the JD"):
    return f"<analysis>{analysis}</analysis>\r\n<resume_json>\n{json.dumps(data)}\n</resume_json>"


@pytest.fixture(autouse=True)
def fresh_cache():
    resume_agent.clear_analysis_cache()
    yield
    resume_agent.clear_analysis_cache()


def put_summary(key, text):
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket=settings.S3_BUCKET, Key=key, Body=text.encode()
    )


@pytest.fixture
def compiler(monkeypatch, tmp_path):
    state = {"success": True, "calls": []}

    async def compile_latex(latex_content, output_filename=None, use_docker=True):
        state["calls"].append((latex_content, output_filename, use_docker))
        if state["success"]:
            pdf = tmp_path / f"{output_filename}.pdf"
            pdf.write_bytes(b"%PDF-1.4 synthetic")
            return SimpleNamespace(success=True, pdf_path=str(pdf), log="", errors=[], warnings=[])
        return SimpleNamespace(
            success=False,
            pdf_path=None,
            log="This is pdfTeX\n! Undefined control sequence.\n\nl.12 \\foo\n",
            errors=[],
            warnings=[],
        )

    monkeypatch.setattr(latex_module.latex_service, "compile_latex", compile_latex)
    return state


async def test_summaries_prefer_summary_files(aws):
    put_summary("u1/job-scout-summary.md", "# job-scout")
    put_summary("u1/notes.md", "# notes")
    put_summary("u2/other-summary.md", "# theirs")
    assert await resume_agent.list_project_summaries("u1") == ["# job-scout"]


async def test_summaries_fall_back_to_any_markdown(aws):
    put_summary("u1/notes.md", "# notes")
    assert await resume_agent.list_project_summaries("u1") == ["# notes"]
    assert await resume_agent.list_project_summaries("nobody") == []


async def test_full_pipeline_stores_pdf_tex_and_metadata(aws, bedrock, compiler):
    put_summary("u1/job-scout-summary.md", "# job-scout\nRanks postings")
    bedrock.reply(claude_reply())

    result = await resume_agent.generate_resume_from_summaries(
        "u1",
        jd="Backend intern, Python",
        personal_info={"name": "Asha Example", "phone": ""},
        education=[
            {
                "degree": "B.Tech",
                "field": "CSE",
                "school": "Example Institute",
                "gpa": "8.7",
                "location": "Chennai",
            }
        ],
        experience=[{"title": "Intern", "company": "Sample Labs", "highlights": ["Built APIs"]}],
        skills=["Python"],
        certifications=[{"name": "AWS CCP", "issuer": "AWS"}, "not a dict"],
        achievements=["Won a hackathon", "  "],
    )

    assert result.analysis == "Picked job-scout for the JD"
    assert result.compilation_error is None
    assert "Asha Example" in result.latex_content
    assert result.pdf_url and result.tex_url

    prompt = bedrock.prompts[0]
    for expected in [
        "# job-scout",
        "GPA: 8.7",
        "- Built APIs",
        "AWS CCP (AWS)",
        "- Won a hackathon",
        "select 3 projects",
        "Backend intern",
    ]:
        assert expected in prompt
    assert "phone" not in prompt

    item = await dynamo_service.get_item("Resumes", {"userId": "u1", "resumeId": result.resume_id})
    assert item["status"] == "compiled"
    assert item["pdfS3Key"] == f"u1/resumes/{result.resume_id}.pdf"
    s3 = boto3.client("s3", region_name="us-east-1")
    assert (
        s3.get_object(Bucket=settings.S3_BUCKET, Key=item["pdfS3Key"])["Body"].read()
        == b"%PDF-1.4 synthetic"
    )
    assert compiler["calls"][0][2] is False


async def test_same_inputs_reuse_the_cached_analysis(aws, bedrock, compiler):
    put_summary("u1/job-scout-summary.md", "# job-scout")
    bedrock.reply(claude_reply(), claude_reply())
    await resume_agent.generate_resume_from_summaries("u1", jd="JD")
    await resume_agent.generate_resume_from_summaries("u1", jd="JD")
    assert len(bedrock.prompts) == 1
    await resume_agent.generate_resume_from_summaries("u1", jd="Different JD")
    assert len(bedrock.prompts) == 2


async def test_failed_compile_keeps_the_tex_and_reports_the_error(aws, bedrock, compiler):
    compiler["success"] = False
    put_summary("u1/job-scout-summary.md", "# job-scout")
    bedrock.reply(claude_reply())
    result = await resume_agent.generate_resume_from_summaries("u1")
    assert result.pdf_url is None
    assert result.tex_url
    assert result.compilation_error == "! Undefined control sequence.  →  l.12 \\foo"
    item = await dynamo_service.get_item("Resumes", {"userId": "u1", "resumeId": result.resume_id})
    assert item["status"] == "generated"
    assert "pdfS3Key" not in item
    assert "select 4 projects" in bedrock.prompts[0]


async def test_no_summaries_is_a_clear_error(aws):
    with pytest.raises(ValueError, match="No project summaries found"):
        await resume_agent.generate_resume_from_summaries("u1")


async def test_markdown_fenced_json_is_accepted(bedrock):
    bedrock.reply("Some notes\n```json\n" + json.dumps({"name": "A"}) + "\n```")
    analysis, data = await resume_agent._call_claude_for_resume(
        ["s"], None, None, None, None, None, None
    )
    assert analysis == ""
    assert data == {"name": "A"}


@pytest.mark.parametrize(
    "reply,message",
    [
        ("No JSON at all", "Failed to extract resume JSON"),
        ("<resume_json>{bad</resume_json>", "invalid JSON"),
    ],
)
async def test_unparseable_replies_raise(bedrock, reply, message):
    bedrock.reply(reply)
    with pytest.raises(ValueError, match=message):
        await resume_agent._call_claude_for_resume(["s"], None, None, None, None, None, None)


def test_compilation_error_falls_back_to_parsed_errors_then_a_default():
    parsed = SimpleNamespace(log="", errors=[CompilationError(1, 0, "Missing }", "error")])
    assert resume_agent._extract_compilation_error(parsed) == "Missing }"
    assert resume_agent._extract_compilation_error(SimpleNamespace(log=None, errors=[])) == (
        "PDF compilation failed — LaTeX source saved."
    )
    many = SimpleNamespace(log="! a\n! b\n! c\n! d", errors=[])
    assert resume_agent._extract_compilation_error(many).split(" | ") == [
        "! a  →  ! b",
        "! b  →  ! c",
        "! c  →  ! d",
    ]


async def test_legacy_agent_strips_fences_and_formats_user_data(bedrock):
    bedrock.reply("```latex\n\\documentclass{article}\n```")
    agent = resume_agent.ResumeGenerationAgent()
    user_data = {
        "personal": {"name": "Asha Example"},
        "skills": ["Python"],
        "projects": [
            {
                "title": "job-scout",
                "technologies": ["Python"],
                "highlights": ["h1"],
                "url": "https://x",
            }
        ],
        "experience": [{"company": "Sample Labs", "title": "Intern", "highlights": ["APIs"]}],
        "education": [
            {"school": "Example Institute", "degree": "B.Tech", "field": "CSE", "gpa": "8.7"}
        ],
        "certifications": [{"name": "AWS CCP", "issuer": "AWS"}],
    }
    result = await agent.generate_resume(
        "\\documentclass{article}",
        user_data,
        jd_context={"title": "SDE", "required_skills": ["Python"]},
    )
    assert result.latex_content == "\\documentclass{article}"
    prompt = bedrock.prompts[0]
    for expected in [
        "name: Asha Example",
        "SKILLS: Python",
        "URL: https://x",
        "Company: Sample Labs",
        "Field: CSE",
        "AWS CCP (AWS)",
        "Target Role: SDE",
    ]:
        assert expected in prompt


async def test_legacy_agent_reraises_bedrock_errors(bedrock):
    bedrock.reply(RuntimeError("down"))
    with pytest.raises(RuntimeError):
        await resume_agent.ResumeGenerationAgent().generate_resume("t", {})

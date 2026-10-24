"""PDF download for resumes stored in SQLite."""

import asyncio
import uuid

from app.core.database import AsyncSessionLocal
from app.models.resume import Resume
from app.models.template import Template


def add_resume(user_id, pdf_path):
    async def _add():
        async with AsyncSessionLocal() as db:
            template = Template(name="Test template", latex_content="\\documentclass{article}")
            db.add(template)
            await db.flush()
            resume = Resume(
                user_id=user_id, template_id=template.id, name="My Resume", pdf_path=pdf_path
            )
            db.add(resume)
            await db.commit()
            return resume.id

    return asyncio.run(_add())


def test_missing_resume_returns_404(client, auth):
    response = client.get(f"/api/resumes/{uuid.uuid4()}/pdf", headers=auth["headers"])
    assert response.status_code == 404


def test_uncompiled_resume_returns_400(client, auth):
    resume_id = add_resume(auth["user_id"], None)
    response = client.get(f"/api/resumes/{resume_id}/pdf", headers=auth["headers"])
    assert response.status_code == 400
    assert response.json()["detail"] == "PDF not available. Compile first."


def test_compiled_resume_streams_the_pdf(client, auth, tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-1.4 synthetic")
    resume_id = add_resume(auth["user_id"], str(pdf))
    response = client.get(f"/api/resumes/{resume_id}/pdf", headers=auth["headers"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "My_Resume.pdf" in response.headers["content-disposition"]
    assert response.content == b"%PDF-1.4 synthetic"

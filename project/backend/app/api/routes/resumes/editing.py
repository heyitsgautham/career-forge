"""
Resume routes: editing
======================
Saving edited LaTeX and AI-assisted edits.
"""

from datetime import datetime

import structlog
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.ids import path_uuid
from app.api.routes.resumes.common import router
from app.core.config import settings
from app.core.database import get_db
from app.models.resume import Resume, ResumeStatus
from app.models.user import User
from app.schemas.resumes import (
    AiEditRequest,
    LatexUpdateRequest,
    LatexUpdateResponse,
)

logger = structlog.get_logger()


@router.patch("/{resume_id}/latex")
async def update_latex(
    resume_id: str,
    latex_content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update resume LaTeX content directly."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        await dynamo_service.update_item(
            "Resumes",
            {"userId": str(current_user.id), "resumeId": resume_id},
            {
                "latexContent": latex_content,
                "status": "generated",
                "pdfS3Key": None,
                "updatedAt": dynamo_service.now_iso(),
            },
        )
        return {"message": "LaTeX updated"}

    result = await db.execute(
        select(Resume).where(
            Resume.id == path_uuid(resume_id, "Resume"),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume.latex_content = latex_content
    resume.status = ResumeStatus.GENERATED
    resume.pdf_path = None  # Invalidate old PDF

    await db.commit()

    return {"message": "LaTeX updated"}


@router.put("/{resume_id}/latex", response_model=LatexUpdateResponse)
async def save_latex(
    resume_id: str,
    body: LatexUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    M2.5 — Save updated LaTeX content.
    Also syncs to S3 if a tex_s3_key exists.
    """
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        now = dynamo_service.now_iso()
        updates: dict = {
            "latexContent": body.latex_content,
            "status": "generated",
            "updatedAt": now,
        }

        # Sync updated .tex to S3 if we have an existing key
        tex_key = item.get("texS3Key")
        if tex_key and not tex_key.startswith("/"):
            try:
                from app.services.s3_service import s3_service

                await s3_service.upload_file(
                    key=tex_key,
                    data=body.latex_content.encode("utf-8"),
                    content_type="text/plain; charset=utf-8",
                )
            except Exception as e:
                logger.warning("s3_tex_update_failed", error=str(e))

        await dynamo_service.update_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, updates
        )
        return LatexUpdateResponse(id=resume_id, updated_at=now)

    result = await db.execute(
        select(Resume).where(
            Resume.id == path_uuid(resume_id, "Resume"),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume.latex_content = body.latex_content
    resume.status = ResumeStatus.GENERATED
    resume.pdf_path = None  # Invalidate old PDF
    resume.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(resume)
    return LatexUpdateResponse(id=str(resume.id), updated_at=resume.updated_at.isoformat())


@router.post("/{resume_id}/ai-edit")
async def ai_edit_resume(
    resume_id: str,
    body: AiEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    M2.5 — SSE streaming AI edit.
    Streams Claude's conversational response as 'delta' events; emits a final
    'latex' event with the full updated .tex extracted from a <latex>...</latex> block.
    """
    import asyncio

    from fastapi.responses import StreamingResponse

    from app.services.bedrock_client import bedrock_client

    # Verify ownership
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_name = item.get("name", "resume")
    else:
        result = await db.execute(
            select(Resume).where(
                Resume.id == path_uuid(resume_id, "Resume"),
                Resume.user_id == current_user.id,
            )
        )
        resume_obj = result.scalar_one_or_none()
        if not resume_obj:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_name = resume_obj.name

    system_prompt = f"""You are an expert LaTeX resume editor assistant.
The user is editing their resume named "{resume_name}".

You will receive:
1. The current full LaTeX source of the resume
2. A natural language instruction from the user

Your task:
1. Respond conversationally (2-3 sentences) explaining what change you made and why.
2. After your explanation, output the complete modified LaTeX wrapped in <latex> and </latex> tags.
   The user will apply this with one click.

Rules:
- ALWAYS include the full updated LaTeX in <latex>...</latex> tags, even for small changes.
- Keep all existing sections unless explicitly told to remove them.
- Preserve all LaTeX packages and preamble unless there's a good reason to change them.
- Your conversational explanation must come BEFORE the <latex> block.
- Do not include any text after the closing </latex> tag.
"""

    user_message = f"""Current LaTeX source:
```latex
{body.latex_content}
```

User instruction: {body.message}"""

    async def event_stream():
        import json as _json
        import re as _re

        full_response = ""
        emitted_up_to = 0  # char index up to which we have already sent deltas
        latex_started = False
        # "<latex>" is 7 chars — hold back that many chars from the end of the
        # buffer so a partial opening tag never leaks to the client.
        LATEX_TAG_LEN = len("<latex>")

        try:
            async for chunk in bedrock_client.stream_generate(
                prompt=user_message,
                system_prompt=system_prompt,
                max_tokens=8192,
            ):
                full_response += chunk

                if latex_started:
                    # Past the <latex> marker — collect silently for extraction
                    pass
                else:
                    latex_pos = full_response.find("<latex>")
                    if latex_pos != -1:
                        # Emit everything before the tag that we haven't sent yet
                        latex_started = True
                        safe_text = full_response[emitted_up_to:latex_pos]
                        if safe_text:
                            yield f"event: delta\ndata: {_json.dumps({'text': safe_text})}\n\n"
                        emitted_up_to = latex_pos
                    else:
                        # No <latex> yet — emit up to (len - LATEX_TAG_LEN) to
                        # guarantee no partial tag sneaks through
                        safe_end = max(emitted_up_to, len(full_response) - LATEX_TAG_LEN)
                        safe_text = full_response[emitted_up_to:safe_end]
                        if safe_text:
                            yield f"event: delta\ndata: {_json.dumps({'text': safe_text})}\n\n"
                            emitted_up_to = safe_end

                await asyncio.sleep(0)  # yield control

            # Stream ended — flush any remaining safe conversational text
            if not latex_started and emitted_up_to < len(full_response):
                # No <latex> block came at all — emit the rest
                remaining = full_response[emitted_up_to:]
                if remaining:
                    yield f"event: delta\ndata: {_json.dumps({'text': remaining})}\n\n"

            # Extract the <latex>...</latex> block from the full response
            latex_match = _re.search(r"<latex>(.*?)</latex>", full_response, _re.DOTALL)
            if latex_match:
                new_latex = latex_match.group(1).strip()
                yield f"event: latex\ndata: {_json.dumps({'latex': new_latex})}\n\n"

            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

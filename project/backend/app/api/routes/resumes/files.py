"""
Resume routes: files
====================
PDF and .tex downloads.
"""

import uuid

import structlog
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.routes.resumes.common import router
from app.core.config import settings
from app.core.database import get_db
from app.models.resume import Resume
from app.models.user import User

logger = structlog.get_logger()


@router.get("/{resume_id}/pdf")
async def download_pdf(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download compiled PDF. Returns presigned S3 URL or local file."""
    if settings.USE_DYNAMO:
        from fastapi.responses import RedirectResponse

        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Try S3 presigned URL first (M2 flow stores full key)
        pdf_key = item.get("pdfS3Key")
        if not pdf_key:
            raise HTTPException(status_code=400, detail="PDF not available. Compile first.")

        # If it's an S3 key (not a local path), generate presigned URL
        if not pdf_key.startswith("/"):
            url = await s3_service.get_presigned_url(pdf_key)
            return RedirectResponse(url=url)

        # Legacy: local file path
        return FileResponse(
            path=pdf_key,
            filename=f"{item.get('name','resume').replace(' ','_')}.pdf",
            media_type="application/pdf",
        )

    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if not resume.pdf_path:
        raise HTTPException(status_code=400, detail="PDF not available. Compile first.")

    return FileResponse(
        path=resume.pdf_path,
        filename=f"{resume.name.replace(' ', '_')}.pdf",
        media_type="application/pdf",
    )


@router.get("/{resume_id}/pdf-url")
async def get_pdf_url(
    resume_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return presigned S3 URL as JSON for iframe preview (avoids redirect + auth header issues)."""
    if not settings.USE_DYNAMO:
        raise HTTPException(status_code=501, detail="Only available with DynamoDB backend")

    from app.services.dynamo_service import dynamo_service
    from app.services.s3_service import s3_service

    item = await dynamo_service.get_item(
        "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
    )
    if not item:
        raise HTTPException(status_code=404, detail="Resume not found")

    pdf_key = item.get("pdfS3Key")
    if not pdf_key:
        raise HTTPException(status_code=400, detail="PDF not available. Compile first.")

    if pdf_key.startswith("/"):
        raise HTTPException(status_code=400, detail="Local file preview not supported via URL")

    resume_name = item.get("name", "resume").replace(" ", "_")
    url = await s3_service.get_presigned_url(pdf_key, filename=f"{resume_name}.pdf", inline=True)
    return {"url": url}


@router.get("/{resume_id}/tex")
async def download_tex(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download .tex source with Content-Disposition: attachment so the browser saves the file."""
    from fastapi.responses import Response as FastAPIResponse

    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        tex_key = item.get("texS3Key")
        latex_content = item.get("latexContent")
        safe_name = item.get("name", "resume").replace(" ", "_")
        filename = f"{safe_name}.tex"

        if tex_key and not tex_key.startswith("/"):
            try:
                content_bytes = await s3_service.download_file(tex_key)
                return FastAPIResponse(
                    content=content_bytes,
                    media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            except Exception as e:
                logger.warning("s3_tex_download_failed", error=str(e), falling_back="latexContent")

        if latex_content:
            return FastAPIResponse(
                content=latex_content.encode("utf-8"),
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        raise HTTPException(status_code=404, detail="LaTeX source not available")

    db_result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = db_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if not resume.latex_content:
        raise HTTPException(status_code=404, detail="LaTeX source not available")

    return FastAPIResponse(
        content=resume.latex_content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{resume.name.replace(" ", "_")}.tex"'
        },
    )

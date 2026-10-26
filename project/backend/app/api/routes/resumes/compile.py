"""
Resume routes: compile
======================
On-demand LaTeX to PDF compilation.
"""

from datetime import datetime
from typing import Optional

import structlog
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.ids import path_uuid
from app.api.routes.resumes.common import router
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import internal_error
from app.models.resume import Resume, ResumeStatus
from app.models.user import User
from app.schemas.resumes import (
    CompileOnDemandRequest,
    CompileOnDemandResponse,
)
from app.services.latex_service import latex_service

logger = structlog.get_logger()


@router.post("/{resume_id}/compile", response_model=CompileOnDemandResponse)
async def compile_resume(
    resume_id: str,
    body: Optional[CompileOnDemandRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compile resume LaTeX to PDF. Optional body allows overriding latex_content."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        latex_to_compile = (
            body.latex_content if body and body.latex_content else None
        ) or item.get("latexContent")
        if not latex_to_compile:
            raise HTTPException(
                status_code=400, detail="No LaTeX content to compile. Generate first."
            )
        await dynamo_service.update_item(
            "Resumes",
            {"userId": str(current_user.id), "resumeId": resume_id},
            {"status": "compiling", "updatedAt": dynamo_service.now_iso()},
        )
        try:
            is_safe, issues = latex_service.validate_latex_safety(latex_to_compile)
            if not is_safe:
                raise HTTPException(status_code=400, detail=f"Unsafe LaTeX: {', '.join(issues)}")
            output_filename = f"resume_{resume_id[:8]}"
            try:
                compilation_result = await latex_service.compile_latex(
                    latex_content=latex_to_compile,
                    output_filename=output_filename,
                    use_docker=False,
                )
            except FileNotFoundError:
                await dynamo_service.update_item(
                    "Resumes",
                    {"userId": str(current_user.id), "resumeId": resume_id},
                    {"status": "generated", "updatedAt": dynamo_service.now_iso()},
                )
                return CompileOnDemandResponse(
                    status="error",
                    pdf_url=None,
                    error_message="LaTeX compiler not available. Install TeX Live or use Overleaf.",
                )
            except Exception as e:
                await dynamo_service.update_item(
                    "Resumes",
                    {"userId": str(current_user.id), "resumeId": resume_id},
                    {
                        "status": "error",
                        "errorMessage": str(e),
                        "updatedAt": dynamo_service.now_iso(),
                    },
                )
                return CompileOnDemandResponse(status="error", pdf_url=None, error_message=str(e))
            if compilation_result.success:
                # latex_service uploads to "compiled/{output_filename}.pdf" — use that same key
                pdf_s3_key = f"compiled/{output_filename}.pdf"
                await dynamo_service.update_item(
                    "Resumes",
                    {"userId": str(current_user.id), "resumeId": resume_id},
                    {
                        "status": "compiled",
                        "pdfS3Key": pdf_s3_key,
                        "updatedAt": dynamo_service.now_iso(),
                    },
                )
                try:
                    presigned_url = await s3_service.get_presigned_url(pdf_s3_key)
                except Exception:
                    presigned_url = None
                return CompileOnDemandResponse(
                    status="compiled", pdf_url=presigned_url, error_message=None
                )
            else:
                error_msg = "; ".join(e.message for e in compilation_result.errors)
                await dynamo_service.update_item(
                    "Resumes",
                    {"userId": str(current_user.id), "resumeId": resume_id},
                    {
                        "status": "error",
                        "errorMessage": error_msg,
                        "updatedAt": dynamo_service.now_iso(),
                    },
                )
                return CompileOnDemandResponse(
                    status="error", pdf_url=None, error_message=error_msg
                )
        except HTTPException:
            raise
        except Exception as e:
            await dynamo_service.update_item(
                "Resumes",
                {"userId": str(current_user.id), "resumeId": resume_id},
                {"status": "error", "errorMessage": str(e), "updatedAt": dynamo_service.now_iso()},
            )
            logger.error("resume_compile_failed", resume_id=resume_id, error=str(e))
            raise internal_error("Resume compilation failed. Please try again.") from e

    # Get resume
    result = await db.execute(
        select(Resume).where(
            Resume.id == path_uuid(resume_id, "Resume"),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Allow overriding latex content from request body
    latex_to_compile = (
        body.latex_content if body and body.latex_content else None
    ) or resume.latex_content

    if not latex_to_compile:
        raise HTTPException(status_code=400, detail="No LaTeX content to compile. Generate first.")

    resume.status = ResumeStatus.COMPILING
    await db.commit()

    try:
        # Validate LaTeX safety
        is_safe, issues = latex_service.validate_latex_safety(latex_to_compile)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"LaTeX content contains unsafe commands: {', '.join(issues)}",
            )

        output_filename = f"resume_{resume.id.hex[:8]}"
        try:
            compilation_result = await latex_service.compile_latex(
                latex_content=latex_to_compile,
                output_filename=output_filename,
                use_docker=False,
            )
        except FileNotFoundError:
            resume.status = ResumeStatus.GENERATED
            await db.commit()
            return CompileOnDemandResponse(
                status="error",
                pdf_url=None,
                error_message="LaTeX compiler not available. Install TeX Live or use Overleaf.",
            )
        except Exception as e:
            logger.error(f"LaTeX compilation error: {e}")
            resume.status = ResumeStatus.ERROR
            resume.error_message = str(e)
            await db.commit()
            return CompileOnDemandResponse(status="error", pdf_url=None, error_message=str(e))

        if compilation_result.success:
            resume.pdf_path = compilation_result.pdf_path
            resume.status = ResumeStatus.COMPILED
            resume.compiled_at = datetime.utcnow()
            resume.compilation_log = compilation_result.log
            resume.compilation_warnings = compilation_result.warnings
            resume.error_message = None
            await db.commit()
            return CompileOnDemandResponse(
                status="compiled",
                pdf_url=f"/uploads/pdfs/{output_filename}.pdf",
                error_message=None,
            )
        else:
            error_msg = "; ".join(e.message for e in compilation_result.errors)
            resume.status = ResumeStatus.ERROR
            resume.error_message = error_msg
            resume.compilation_log = compilation_result.log
            await db.commit()
            return CompileOnDemandResponse(status="error", pdf_url=None, error_message=error_msg)

    except HTTPException:
        # The unsafe-LaTeX 400 must reach the client as a 400, as on DynamoDB
        resume.status = ResumeStatus.GENERATED
        await db.commit()
        raise
    except Exception as e:
        logger.error("resume_compile_failed", resume_id=str(resume.id), exc_info=e)
        resume.status = ResumeStatus.ERROR
        resume.error_message = str(e)
        await db.commit()
        raise internal_error("Resume compilation failed. Please try again.") from e

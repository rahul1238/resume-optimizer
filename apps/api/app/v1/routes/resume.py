from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.services.resume_upload_service import ResumeUploadService
from app.v1.schemas.resume import ResumeUploadResponse

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> ResumeUploadResponse:
    try:
        content = await file.read(settings.max_resume_upload_bytes + 1)
        parsed_resume = ResumeUploadService.process(
            filename=file.filename or "resume",
            content=content,
        )
    finally:
        await file.close()

    return ResumeUploadResponse(
        filename=parsed_resume.filename,
        file_type=parsed_resume.file_type,
        page_count=parsed_resume.page_count,
        character_count=len(parsed_resume.text),
        text=parsed_resume.text,
    )

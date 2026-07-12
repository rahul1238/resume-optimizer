from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.services.resume_service import ResumeService
from app.services.resume_upload_service import ResumeUploadService
from app.v1.schemas.resume import ResumeSummaryResponse, ResumeUploadResponse

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeSummaryResponse])
async def list_resumes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ResumeSummaryResponse]:
    records = await run_in_threadpool(ResumeService.list, current_user.uid)
    return [
        ResumeSummaryResponse(
            resume_id=record.resume_id,
            filename=record.filename,
            file_type=record.file_type,
            page_count=record.page_count,
            character_count=record.character_count,
            created_at=record.created_at,
        )
        for record in records
    ]


@router.get("/{resume_id}", response_model=ResumeUploadResponse)
async def get_resume(
    resume_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ResumeUploadResponse:
    resume = await run_in_threadpool(ResumeService.get, current_user.uid, resume_id)
    return ResumeUploadResponse(
        resume_id=resume.resume_id,
        filename=resume.filename,
        file_type=resume.file_type,
        page_count=resume.page_count,
        storage_path=resume.storage_path,
        character_count=len(resume.text),
        text=resume.text,
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    await run_in_threadpool(ResumeService.delete, current_user.uid, resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> ResumeUploadResponse:
    try:
        content = await file.read(settings.max_resume_upload_bytes + 1)
        parsed_resume = ResumeUploadService.process(
            owner_uid=current_user.uid,
            filename=file.filename or "resume",
            content=content,
        )
    finally:
        await file.close()

    return ResumeUploadResponse(
        resume_id=parsed_resume.resume_id,
        filename=parsed_resume.filename,
        file_type=parsed_resume.file_type,
        page_count=parsed_resume.page_count,
        storage_path=parsed_resume.storage_path,
        character_count=len(parsed_resume.text),
        text=parsed_resume.text,
    )

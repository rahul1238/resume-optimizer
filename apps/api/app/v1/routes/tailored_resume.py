from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import CurrentUser, get_current_user
from app.models.improvement import ImprovementRecord
from app.models.resume import ResumeRecord
from app.services.improvement_service import ImprovementService
from app.services.resume_service import ResumeService
from app.v1.schemas.tailored_resume import TailoredResumeSummaryResponse

router = APIRouter(prefix="/tailored-resumes", tags=["tailored-resumes"])


@router.get("", response_model=list[TailoredResumeSummaryResponse])
async def list_tailored_resumes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    resume_id: Annotated[str | None, Query(max_length=100)] = None,
) -> list[TailoredResumeSummaryResponse]:
    improvements, resumes = await run_in_threadpool(
        _list_with_resumes,
        current_user.uid,
        resume_id,
    )
    titles = {resume.resume_id: resume.title for resume in resumes}
    return [
        TailoredResumeSummaryResponse(
            analysis_id=record.analysis_id,
            resume_id=record.resume_id,
            base_resume_title=titles.get(record.resume_id, "Base resume"),
            company_name=record.company_name,
            role_name=record.role_name,
            application_date=record.application_date,
            revision=record.revision,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in improvements
    ]


def _list_with_resumes(
    owner_uid: str,
    resume_id: str | None,
) -> tuple[list[ImprovementRecord], list[ResumeRecord]]:
    return (
        ImprovementService.list(owner_uid, resume_id),
        ResumeService.list(owner_uid),
    )

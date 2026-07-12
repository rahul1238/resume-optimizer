from typing import Annotated

from fastapi import APIRouter, Depends, status
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import CurrentUser, get_current_user
from app.services.analysis_service import AnalysisService
from app.v1.schemas.analysis import AnalysisCreateRequest, AnalysisCreateResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post(
    "",
    response_model=AnalysisCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis(
    request: AnalysisCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AnalysisCreateResponse:
    analysis_id, provider, model, result = await run_in_threadpool(
        AnalysisService.analyze,
        current_user.uid,
        request.resume_id,
        request.job_description,
        request.job_title,
        request.company_name,
    )
    return AnalysisCreateResponse(
        analysis_id=analysis_id,
        resume_id=request.resume_id,
        status="completed",
        provider=provider,
        model=model,
        result=result,
    )

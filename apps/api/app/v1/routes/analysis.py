from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.ai.schemas import ResumeAnalysisResult
from app.auth.dependencies import CurrentUser, get_current_user
from app.services.analysis_service import AnalysisService
from app.v1.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisDetailResponse,
    AnalysisSummaryResponse,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])


def detail_response(record) -> AnalysisDetailResponse:
    result = ResumeAnalysisResult.model_validate(record.result)
    return AnalysisDetailResponse(
        analysis_id=record.analysis_id,
        resume_id=record.resume_id,
        job_title=record.job_title,
        company_name=record.company_name,
        match_score=result.match_score,
        status=record.status,
        provider=record.provider,
        model=record.model,
        created_at=record.created_at,
        job_description=record.job_description,
        result=result,
    )


@router.get("", response_model=list[AnalysisSummaryResponse])
async def list_analyses(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    resume_id: Annotated[str | None, Query(max_length=100)] = None,
) -> list[AnalysisSummaryResponse]:
    records = await run_in_threadpool(
        AnalysisService.list,
        current_user.uid,
        resume_id,
    )
    return [
        AnalysisSummaryResponse(
            analysis_id=record.analysis_id,
            resume_id=record.resume_id,
            job_title=record.job_title,
            company_name=record.company_name,
            match_score=ResumeAnalysisResult.model_validate(record.result).match_score,
            status=record.status,
            provider=record.provider,
            model=record.model,
            created_at=record.created_at,
        )
        for record in records
    ]


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AnalysisDetailResponse:
    record = await run_in_threadpool(
        AnalysisService.get,
        current_user.uid,
        analysis_id,
    )
    return detail_response(record)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    await run_in_threadpool(
        AnalysisService.delete,
        current_user.uid,
        analysis_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

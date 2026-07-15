from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.ai.schemas import ResumeAnalysisResult
from app.auth.dependencies import CurrentUser, get_current_user
from app.services.analysis_service import AnalysisService
from app.services.export_service import ResumeExportService
from app.services.improvement_service import ImprovementService
from app.v1.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisDetailResponse,
    AnalysisSummaryResponse,
    KeywordCoverageRequest,
    KeywordCoverageResponse,
    ResumePreviewRequest,
)
from app.v1.schemas.improvement import (
    ImprovementGenerateRequest,
    ImprovementLayoutUpdateRequest,
    ImprovementResponse,
    ImprovementSaveRequest,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])


def improvement_response(record) -> ImprovementResponse:
    return ImprovementResponse(
        analysis_id=record.analysis_id,
        resume_id=record.resume_id,
        provider=record.provider,
        model=record.model,
        created_at=record.created_at,
        updated_at=record.updated_at,
        company_name=record.company_name,
        role_name=record.role_name,
        application_date=record.application_date,
        revision=record.revision,
        layout=record.layout_settings or {},
        result=ImprovementService.result(record),
    )


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


@router.post("/{analysis_id}/coverage", response_model=KeywordCoverageResponse)
async def calculate_keyword_coverage(
    analysis_id: str,
    request: KeywordCoverageRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> KeywordCoverageResponse:
    score, covered, missing = await run_in_threadpool(
        AnalysisService.coverage,
        current_user.uid,
        analysis_id,
        request.draft,
    )
    return KeywordCoverageResponse(
        coverage_score=score,
        covered_keywords=covered,
        missing_keywords=missing,
    )


@router.post("/{analysis_id}/preview/pdf")
async def preview_pdf(
    analysis_id: str,
    request: ResumePreviewRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    # Confirm ownership without requiring the draft to be persisted before previewing.
    await run_in_threadpool(
        AnalysisService.get,
        current_user.uid,
        analysis_id,
    )
    content, page_count = await run_in_threadpool(
        ResumeExportService.to_pdf_preview,
        request.draft,
        request.layout,
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="resume-preview.pdf"',
            "X-Resume-Page-Count": str(page_count),
        },
    )


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


@router.get("/{analysis_id}/improvements", response_model=ImprovementResponse)
async def get_improvements(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ImprovementResponse:
    record = await run_in_threadpool(
        ImprovementService.get,
        current_user.uid,
        analysis_id,
    )
    return improvement_response(record)


@router.post("/{analysis_id}/improvements", response_model=ImprovementResponse)
async def generate_improvements(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    request: ImprovementGenerateRequest | None = None,
) -> ImprovementResponse:
    payload = request or ImprovementGenerateRequest()
    record = await run_in_threadpool(
        ImprovementService.generate,
        current_user.uid,
        analysis_id,
        payload.current_result,
        payload.feedback,
    )
    return improvement_response(record)


@router.put("/{analysis_id}/improvements", response_model=ImprovementResponse)
async def save_improvements(
    analysis_id: str,
    request: ImprovementSaveRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ImprovementResponse:
    record = await run_in_threadpool(
        ImprovementService.save,
        current_user.uid,
        analysis_id,
        request.result,
    )
    return improvement_response(record)


@router.put("/{analysis_id}/improvements/layout", response_model=ImprovementResponse)
async def update_improvement_layout(
    analysis_id: str,
    request: ImprovementLayoutUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ImprovementResponse:
    record = await run_in_threadpool(
        ImprovementService.update_layout,
        current_user.uid,
        analysis_id,
        request.layout,
    )
    return improvement_response(record)


@router.get("/{analysis_id}/export/pdf")
async def export_pdf(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    context = await run_in_threadpool(
        ResumeExportService.get_context,
        current_user.uid,
        analysis_id,
    )
    content = await run_in_threadpool(
        ResumeExportService.to_pdf,
        context.draft,
        context.layout,
    )
    filename = ResumeExportService.export_filename(context)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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

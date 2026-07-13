import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.ai.provider import AIProviderError
from app.auth.errors import AuthenticationError
from app.core.config import settings
from app.repositories.analysis_repository import (
    AnalysisNotFoundError,
    AnalysisRepositoryError,
)
from app.repositories.improvement_repository import (
    ImprovementNotFoundError,
    ImprovementRepositoryError,
)
from app.repositories.resume_repository import (
    ResumeNotFoundError,
    ResumeRepositoryError,
)
from app.services.export_service import ResumeExportError
from app.services.resume_storage_service import ResumeStorageError
from app.services.resume_upload_service import ResumeUploadError
from app.v1.router import router as v1_router

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)


def service_error_response(error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=getattr(error, "status_code", 503),
        content={
            "detail": getattr(error, "message", "Service unavailable."),
            "code": getattr(error, "code", "service_unavailable"),
        },
    )


@app.exception_handler(ResumeUploadError)
@app.exception_handler(ResumeExportError)
async def resume_upload_error_handler(
    request: Request,
    error: ResumeUploadError | ResumeExportError,
) -> JSONResponse:
    logger.warning(
        "Resume upload rejected: %s %s",
        request.method,
        request.url.path,
        extra={"error_code": error.code},
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message, "code": error.code},
    )


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    request: Request,
    error: AuthenticationError,
) -> JSONResponse:
    logger.warning(
        "Authentication rejected: %s %s",
        request.method,
        request.url.path,
        extra={"error_code": error.code},
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message, "code": error.code},
    )


@app.exception_handler(ResumeStorageError)
async def resume_storage_error_handler(
    request: Request,
    error: ResumeStorageError,
) -> JSONResponse:
    logger.exception(
        "Resume storage failed: %s %s",
        request.method,
        request.url.path,
        extra={"error_code": error.code},
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message, "code": error.code},
    )


@app.exception_handler(ResumeRepositoryError)
async def resume_repository_error_handler(
    request: Request,
    error: ResumeRepositoryError,
) -> JSONResponse:
    log = logger.warning if isinstance(error, ResumeNotFoundError) else logger.exception
    log(
        "Resume repository request failed: %s %s",
        request.method,
        request.url.path,
        extra={"error_code": error.code},
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message, "code": error.code},
    )


@app.exception_handler(AnalysisRepositoryError)
@app.exception_handler(AIProviderError)
@app.exception_handler(ImprovementRepositoryError)
async def analysis_service_error_handler(
    request: Request,
    error: AnalysisRepositoryError | AIProviderError | ImprovementRepositoryError,
) -> JSONResponse:
    log = (
        logger.warning
        if isinstance(error, (AnalysisNotFoundError, ImprovementNotFoundError))
        else logger.error
    )
    log(
        "Analysis request failed: %s %s",
        request.method,
        request.url.path,
        extra={"error_code": error.code},
    )
    return service_error_response(error)


app.include_router(v1_router)

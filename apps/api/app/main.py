import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.auth.errors import AuthenticationError
from app.core.config import settings
from app.services.resume_storage_service import ResumeStorageError
from app.services.resume_upload_service import ResumeUploadError
from app.v1.router import router as v1_router

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.exception_handler(ResumeUploadError)
async def resume_upload_error_handler(
    request: Request,
    error: ResumeUploadError,
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

app.include_router(v1_router)

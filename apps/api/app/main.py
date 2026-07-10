import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.errors import AuthenticationError
from app.core.config import settings
from app.services.resume_upload_service import ResumeUploadError
from app.v1.router import router as v1_router

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


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

app.include_router(v1_router)

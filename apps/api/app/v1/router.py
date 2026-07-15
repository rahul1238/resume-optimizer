from fastapi import APIRouter

from app.v1.routes.analysis import router as analysis_router
from app.v1.routes.health import router as health_router
from app.v1.routes.resume import router as resume_router
from app.v1.routes.tailored_resume import router as tailored_resume_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(resume_router)
router.include_router(analysis_router)
router.include_router(tailored_resume_router)

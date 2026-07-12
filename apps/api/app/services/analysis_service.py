from uuid import uuid4

from app.ai.factory import get_ai_provider
from app.ai.schemas import ResumeAnalysisResult
from app.models.analysis import AnalysisRecord
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.resume_storage_service import ResumeStorageService


class AnalysisService:
    @staticmethod
    def analyze(
        owner_uid: str,
        resume_id: str,
        job_description: str,
        job_title: str | None,
        company_name: str | None,
    ) -> tuple[str, str, str, ResumeAnalysisResult]:
        resume = ResumeRepository.get_owned(resume_id, owner_uid)
        resume_text = ResumeStorageService.read_text(resume.text_storage_path)
        provider = get_ai_provider()
        result = provider.analyze_resume(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            company_name=company_name,
        )
        analysis_id = str(uuid4())
        AnalysisRepository.create(
            AnalysisRecord(
                analysis_id=analysis_id,
                owner_uid=owner_uid,
                resume_id=resume_id,
                job_description=job_description,
                job_title=job_title,
                company_name=company_name,
                provider=provider.name,
                model=provider.model,
                status="completed",
                result=result.model_dump(),
            )
        )
        return analysis_id, provider.name, provider.model, result

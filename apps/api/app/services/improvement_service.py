from app.ai.factory import get_ai_provider
from app.ai.schemas import ResumeImprovementResult
from app.models.improvement import ImprovementRecord
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.improvement_repository import (
    ImprovementNotFoundError,
    ImprovementRepository,
)
from app.repositories.resume_repository import ResumeRepository
from app.services.resume_storage_service import ResumeStorageService


class ImprovementService:
    @staticmethod
    def get(owner_uid: str, analysis_id: str) -> ImprovementRecord:
        return ImprovementRepository.get_owned(analysis_id, owner_uid)

    @staticmethod
    def generate(
        owner_uid: str,
        analysis_id: str,
        current_result: ResumeImprovementResult | None = None,
        feedback: list[str] | None = None,
    ) -> ImprovementRecord:
        if current_result is None and not feedback:
            try:
                return ImprovementRepository.get_owned(analysis_id, owner_uid)
            except ImprovementNotFoundError:
                pass

        analysis = AnalysisRepository.get_owned(analysis_id, owner_uid)
        resume = ResumeRepository.get_owned(analysis.resume_id, owner_uid)
        resume_text = ResumeStorageService.read_text(resume.text_storage_path)
        provider = get_ai_provider()
        result = provider.improve_resume(
            resume_text=resume_text,
            job_description=analysis.job_description,
            job_title=analysis.job_title,
            company_name=analysis.company_name,
            current_result=current_result,
            feedback=feedback,
        )
        record = ImprovementRecord(
            analysis_id=analysis_id,
            owner_uid=owner_uid,
            resume_id=analysis.resume_id,
            provider=provider.name,
            model=provider.model,
            result=result.model_dump(),
        )
        ImprovementRepository.save(record)
        return record

    @staticmethod
    def result(record: ImprovementRecord) -> ResumeImprovementResult:
        return ResumeImprovementResult.model_validate(record.result)

    @staticmethod
    def save(
        owner_uid: str,
        analysis_id: str,
        result: ResumeImprovementResult,
    ) -> ImprovementRecord:
        existing = ImprovementRepository.get_owned(analysis_id, owner_uid)
        record = ImprovementRecord(
            analysis_id=existing.analysis_id,
            owner_uid=existing.owner_uid,
            resume_id=existing.resume_id,
            provider=existing.provider,
            model=existing.model,
            result=result.model_dump(),
            created_at=existing.created_at,
        )
        ImprovementRepository.save(record)
        return record

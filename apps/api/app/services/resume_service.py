from app.models.resume import ResumeRecord
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.improvement_repository import ImprovementRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.resume_storage_service import ResumeStorageService
from app.services.resume_upload_service import ParsedResume


class ResumeService:
    @staticmethod
    def list(owner_uid: str) -> list[ResumeRecord]:
        return ResumeRepository.list_owned(owner_uid)

    @staticmethod
    def get(owner_uid: str, resume_id: str) -> ParsedResume:
        record = ResumeRepository.get_owned(resume_id, owner_uid)
        text = ResumeStorageService.read_text(record.text_storage_path)
        return ParsedResume(
            resume_id=record.resume_id,
            filename=record.filename,
            file_type=record.file_type,
            page_count=record.page_count,
            storage_path=record.original_storage_path,
            text_storage_path=record.text_storage_path,
            text=text,
        )

    @staticmethod
    def delete(owner_uid: str, resume_id: str) -> None:
        record = ResumeRepository.get_owned(resume_id, owner_uid)
        ResumeStorageService.delete_paths(
            record.original_storage_path,
            record.text_storage_path,
        )
        analysis_ids = AnalysisRepository.delete_for_resume(resume_id, owner_uid)
        for analysis_id in analysis_ids:
            ImprovementRepository.delete(analysis_id)
        ResumeRepository.delete(resume_id)

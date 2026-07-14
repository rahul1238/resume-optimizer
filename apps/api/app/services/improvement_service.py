import hashlib
import re

from app.ai.factory import get_ai_provider
from app.ai.schemas import (
    ResumeChange,
    ResumeImprovementResult,
    StructuredResumeDocument,
    StructuredResumeSection,
)
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
        result = ImprovementService.normalize(result)
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
        return ImprovementService.normalize(
            ResumeImprovementResult.model_validate(record.result)
        )

    @staticmethod
    def save(
        owner_uid: str,
        analysis_id: str,
        result: ResumeImprovementResult,
    ) -> ImprovementRecord:
        existing = ImprovementRepository.get_owned(analysis_id, owner_uid)
        result = ImprovementService.normalize(result)
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

    @staticmethod
    def normalize(result: ResumeImprovementResult) -> ResumeImprovementResult:
        document = result.structured_resume or ImprovementService._structure_draft(
            result.optimized_resume_draft
        )
        changes = result.change_set or ImprovementService._legacy_changes(result)
        normalized_changes = []
        for change in changes:
            evidence = change.evidence or ([change.original] if change.original else [])
            normalized_changes.append(
                change.model_copy(
                    update={
                        "change_id": change.change_id
                        or ImprovementService._change_id(change),
                        "evidence": evidence,
                    }
                )
            )
        return result.model_copy(
            update={
                "structured_resume": document,
                "change_set": normalized_changes,
            }
        )

    @staticmethod
    def _legacy_changes(result: ResumeImprovementResult) -> list[ResumeChange]:
        changes = [
            ResumeChange(
                change_type="summary",
                target_section="Professional Summary",
                suggested=result.suggested_summary,
                reason=result.summary_reason,
                evidence=result.skills_to_emphasize[:5],
                confidence=0.8,
            )
        ]
        changes.extend(
            ResumeChange(
                change_type="bullet",
                target_section="Experience",
                original=rewrite.original,
                suggested=rewrite.suggested,
                reason=rewrite.reason,
                evidence=[rewrite.original],
                confidence=0.95,
            )
            for rewrite in result.bullet_rewrites
        )
        return changes

    @staticmethod
    def _change_id(change: ResumeChange) -> str:
        content = "\x1f".join(
            (
                change.change_type,
                change.target_section,
                change.original,
                change.suggested,
            )
        )
        return f"change-{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    @staticmethod
    def _structure_draft(draft: str) -> StructuredResumeDocument:
        known_headings = {
            "summary",
            "professional summary",
            "experience",
            "professional experience",
            "work experience",
            "education",
            "skills",
            "technical skills",
            "projects",
            "certifications",
            "awards",
            "publications",
            "languages",
        }
        header: list[str] = []
        sections: list[StructuredResumeSection] = []
        heading = ""
        items: list[str] = []

        def add_section() -> None:
            if not heading or not items:
                return
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            sections.append(
                StructuredResumeSection(
                    section_id=f"section-{slug or len(sections) + 1}",
                    heading=heading,
                    items=items.copy(),
                )
            )

        for raw_line in draft.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            candidate = re.sub(r"^#{1,6}\s*", "", line).rstrip(":").strip()
            is_heading = line.startswith("#") or candidate.lower() in known_headings
            if is_heading:
                add_section()
                heading = candidate
                items = []
            elif heading:
                items.append(line)
            else:
                header.append(line)
        add_section()
        if not sections and header:
            sections.append(
                StructuredResumeSection(
                    section_id="section-resume",
                    heading="Resume",
                    items=header[1:],
                )
            )
            header = header[:1]
        return StructuredResumeDocument(header=header, sections=sections)

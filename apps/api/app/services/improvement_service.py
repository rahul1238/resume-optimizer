from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from app.ai.factory import get_ai_provider
from app.ai.schemas import (
    ClarificationQuestion,
    ResumeChange,
    ResumeImprovementResult,
    StructuredResumeDocument,
    StructuredResumeSection,
    TailoringDecision,
)
from app.models.improvement import ImprovementRecord
from app.models.layout import ResumeLayoutSettings
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.improvement_repository import (
    ImprovementNotFoundError,
    ImprovementRepository,
)
from app.repositories.resume_repository import ResumeRepository
from app.services.resume_storage_service import ResumeStorageService


class ImprovementService:
    @staticmethod
    def list(
        owner_uid: str,
        resume_id: str | None = None,
    ) -> list[ImprovementRecord]:
        return ImprovementRepository.list_owned(owner_uid, resume_id)

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
        try:
            existing = ImprovementRepository.get_owned(analysis_id, owner_uid)
        except ImprovementNotFoundError:
            existing = None
        record = ImprovementRecord(
            analysis_id=analysis_id,
            owner_uid=owner_uid,
            resume_id=analysis.resume_id,
            provider=provider.name,
            model=provider.model,
            result=result.model_dump(),
            company_name=analysis.company_name,
            role_name=analysis.job_title,
            application_date=(
                existing.application_date
                if existing
                else datetime.now(UTC).date().isoformat()
            ),
            layout_settings=(
                existing.layout_settings
                if existing
                else ResumeLayoutSettings().model_dump()
            ),
            revision=existing.revision + 1 if existing else 1,
            created_at=existing.created_at if existing else None,
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
            company_name=existing.company_name,
            role_name=existing.role_name,
            application_date=existing.application_date,
            layout_settings=existing.layout_settings,
            revision=existing.revision + 1,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        ImprovementRepository.save(record)
        return record

    @staticmethod
    def update_layout(
        owner_uid: str,
        analysis_id: str,
        layout: ResumeLayoutSettings,
    ) -> ImprovementRecord:
        existing = ImprovementRepository.get_owned(analysis_id, owner_uid)
        record = ImprovementRecord(
            **{
                **existing.__dict__,
                "layout_settings": layout.model_dump(),
                "revision": existing.revision + 1,
            }
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
        normalized_decisions = []
        for decision in result.tailoring_decisions:
            action = decision.action
            if decision.content_type == "employment" and action == "omit":
                action = "condense"
            normalized_decisions.append(
                decision.model_copy(
                    update={
                        "decision_id": decision.decision_id
                        or ImprovementService._decision_id(decision),
                        "action": action,
                    }
                )
            )
        normalized_questions = [
            question.model_copy(
                update={
                    "question_id": question.question_id
                    or ImprovementService._question_id(question)
                }
            )
            for question in result.clarification_questions
        ]
        return result.model_copy(
            update={
                "structured_resume": document,
                "change_set": normalized_changes,
                "clarification_questions": normalized_questions,
                "tailoring_decisions": normalized_decisions,
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
    def _decision_id(decision: TailoringDecision) -> str:
        content = "\x1f".join(
            (
                decision.content_type,
                decision.source_text,
                decision.action,
                decision.relevance,
            )
        )
        return f"decision-{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    @staticmethod
    def _question_id(question: ClarificationQuestion) -> str:
        content = "\x1f".join(
            (question.requirement, question.question, question.target_section)
        )
        return f"question-{hashlib.sha256(content.encode()).hexdigest()[:16]}"

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

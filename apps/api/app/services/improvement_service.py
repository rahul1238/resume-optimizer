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
        result = ImprovementService.normalize(result, resume_text)
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
        resume = ResumeRepository.get_owned(existing.resume_id, owner_uid)
        resume_text = ResumeStorageService.read_text(resume.text_storage_path)
        result = ImprovementService.normalize(result, resume_text)
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
    def normalize(
        result: ResumeImprovementResult,
        source_text: str | None = None,
    ) -> ResumeImprovementResult:
        draft = ImprovementService._preserve_projects(
            result.optimized_resume_draft,
            source_text,
        )
        document = ImprovementService._structure_draft(draft)
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
            if decision.content_type in {"employment", "project"} and action == "omit":
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
                "optimized_resume_draft": draft,
                "structured_resume": document,
                "change_set": normalized_changes,
                "clarification_questions": normalized_questions,
                "tailoring_decisions": normalized_decisions,
            }
        )

    @staticmethod
    def _preserve_projects(draft: str, source_text: str | None) -> str:
        if not source_text or not draft.strip():
            return draft

        source = ImprovementService._structure_draft(source_text)
        source_sections = [
            section
            for section in source.sections
            if ImprovementService._is_project_heading(section.heading)
        ]
        if not source_sections:
            return draft

        document = ImprovementService._structure_draft(draft)
        project_indices = [
            index
            for index, section in enumerate(document.sections)
            if ImprovementService._is_project_heading(section.heading)
        ]
        if not project_indices:
            document.sections.extend(
                section.model_copy(deep=True) for section in source_sections
            )
            return ImprovementService._serialize_document(document)

        target_index = project_indices[0]
        target = document.sections[target_index]
        target_blocks = ImprovementService._project_blocks(target.items)
        present_titles = {
            ImprovementService._project_title_key(block[0])
            for block in target_blocks
            if block
        }
        missing_blocks: list[list[str]] = []
        for section in source_sections:
            for block in ImprovementService._project_blocks(section.items):
                if not block:
                    continue
                title = ImprovementService._project_title_key(block[0])
                if title and title not in present_titles:
                    missing_blocks.append(block)
                    present_titles.add(title)

        if not missing_blocks:
            return draft

        merged_items = target.items.copy()
        for block in missing_blocks:
            merged_items.extend(block)
        document.sections[target_index] = target.model_copy(
            update={"items": merged_items}
        )
        return ImprovementService._serialize_document(document)

    @staticmethod
    def _is_project_heading(heading: str) -> bool:
        normalized = re.sub(r"[^a-z]+", " ", heading.lower()).strip()
        return normalized in {
            "projects",
            "academic projects",
            "key projects",
            "personal projects",
            "selected projects",
        }

    @staticmethod
    def _project_blocks(items: list[str]) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        has_bullet = False
        for item in items:
            is_bullet = bool(re.match(r"^\s*[-*\u2022]\s+", item))
            if current and has_bullet and not is_bullet:
                blocks.append(current)
                current = []
                has_bullet = False
            current.append(item)
            has_bullet = has_bullet or is_bullet
        if current:
            blocks.append(current)
        return blocks

    @staticmethod
    def _project_title_key(title: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()

    @staticmethod
    def _serialize_document(document: StructuredResumeDocument) -> str:
        groups: list[str] = []
        if document.header:
            groups.append("\n".join(document.header))
        groups.extend(
            "\n".join([section.heading, *section.items])
            for section in document.sections
        )
        return "\n\n".join(group for group in groups if group.strip()).strip()

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
            "academic projects",
            "key projects",
            "personal projects",
            "selected projects",
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
        header = [line for line in header if re.search(r"\w", line)]
        if not sections and header:
            sections.append(
                StructuredResumeSection(
                    section_id="section-resume",
                    heading="Resume",
                    items=["\n".join(header[1:])] if len(header) > 1 else [],
                )
            )
            header = header[:1]
        elif len(header) > 20:
            sections.insert(
                0,
                StructuredResumeSection(
                    section_id="section-additional-information",
                    heading="Additional Information",
                    items=["\n".join(header[20:])],
                ),
            )
            header = header[:20]
        return StructuredResumeDocument(header=header, sections=sections)

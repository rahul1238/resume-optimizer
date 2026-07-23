import re
from datetime import UTC, datetime
from types import SimpleNamespace

from app.ai.schemas import (
    BulletRewrite,
    ClarificationQuestion,
    ResumeImprovementResult,
    TailoringDecision,
)
from app.models.improvement import ImprovementRecord
from app.models.layout import ResumeLayoutSettings
from app.repositories.improvement_repository import ImprovementRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.improvement_service import ImprovementService
from app.services.resume_storage_service import ResumeStorageService


def legacy_result() -> ResumeImprovementResult:
    return ResumeImprovementResult(
        optimized_resume_draft=(
            "Rahul Kumar\nrahul@example.com\n\n"
            "PROFESSIONAL SUMMARY\nBackend engineer building Python APIs.\n\n"
            "EXPERIENCE\n- Built APIs.\n"
        ),
        suggested_summary="Backend engineer building reliable Python APIs.",
        summary_reason="Aligns the summary with the target role.",
        bullet_rewrites=[
            BulletRewrite(
                original="Built APIs.",
                suggested="Built reliable Python APIs for internal services.",
                reason="Adds supported technical context.",
            )
        ],
        skills_to_emphasize=["Python"],
        ats_recommendations=["Use standard section headings."],
    )


def test_normalize_builds_structured_document_and_atomic_changes() -> None:
    normalized = ImprovementService.normalize(legacy_result())

    assert normalized.structured_resume is not None
    assert normalized.structured_resume.header[0] == "Rahul Kumar"
    assert [section.heading for section in normalized.structured_resume.sections] == [
        "PROFESSIONAL SUMMARY",
        "EXPERIENCE",
    ]
    assert len(normalized.change_set) == 2
    assert normalized.change_set[1].evidence == ["Built APIs."]
    assert normalized.change_set[1].change_id.startswith("change-")


def test_normalize_assigns_stable_change_ids() -> None:
    first = ImprovementService.normalize(legacy_result())
    second = ImprovementService.normalize(legacy_result())

    assert [item.change_id for item in first.change_set] == [
        item.change_id for item in second.change_set
    ]


def test_normalize_assigns_stable_section_aware_question_ids() -> None:
    result = legacy_result().model_copy(
        update={
            "clarification_questions": [
                ClarificationQuestion(
                    requirement="Kubernetes",
                    question="Have you deployed services to Kubernetes?",
                    target_section="Experience",
                )
            ]
        }
    )

    first = ImprovementService.normalize(result)
    second = ImprovementService.normalize(result)

    assert first.clarification_questions[0].question_id.startswith("question-")
    assert first.clarification_questions[0].question_id == (
        second.clarification_questions[0].question_id
    )


def test_normalize_never_allows_employment_to_be_omitted() -> None:
    result = legacy_result().model_copy(
        update={
            "tailoring_decisions": [
                TailoringDecision(
                    content_type="employment",
                    source_text="Support Engineer | Example Ltd | 2023-Present",
                    action="omit",
                    relevance="irrelevant",
                    reason="The role is not aligned with the target role.",
                )
            ]
        }
    )

    normalized = ImprovementService.normalize(result)

    assert normalized.tailoring_decisions[0].action == "condense"
    assert normalized.tailoring_decisions[0].decision_id.startswith("decision-")


def test_normalize_never_allows_projects_to_be_omitted() -> None:
    result = legacy_result().model_copy(
        update={
            "tailoring_decisions": [
                TailoringDecision(
                    content_type="project",
                    source_text="Resume Optimizer",
                    action="omit",
                    relevance="irrelevant",
                    reason="The project is less relevant to the target role.",
                )
            ]
        }
    )

    normalized = ImprovementService.normalize(result)

    assert normalized.tailoring_decisions[0].action == "condense"


def test_normalize_restores_projects_missing_from_generated_draft() -> None:
    source = (
        "Rahul Kumar\n\n"
        "PROJECTS\n"
        "Resume Optimizer | Python, FastAPI\n"
        "- Built an ATS-focused resume editor.\n"
        "Expense Tracker | Flutter, SQLite\n"
        "- Implemented offline transaction tracking.\n"
        "Chat Platform | WebSockets, Redis\n"
        "- Added real-time messaging and presence.\n\n"
        "EDUCATION\nB.Tech in Computer Science"
    )
    result = legacy_result().model_copy(
        update={
            "optimized_resume_draft": (
                "Rahul Kumar\n\n"
                "PROJECTS\n"
                "Resume Optimizer | Python, FastAPI\n"
                "- Built a production ATS-focused resume editor.\n\n"
                "EDUCATION\nB.Tech in Computer Science"
            )
        }
    )

    normalized = ImprovementService.normalize(result, source)

    assert (
        "Built a production ATS-focused resume editor"
        in normalized.optimized_resume_draft
    )
    assert "Expense Tracker | Flutter, SQLite" in normalized.optimized_resume_draft
    assert "Chat Platform | WebSockets, Redis" in normalized.optimized_resume_draft
    assert normalized.structured_resume is not None
    project_section = next(
        section
        for section in normalized.structured_resume.sections
        if section.heading == "PROJECTS"
    )
    assert (
        sum("Tracker" in item or "Platform" in item for item in project_section.items)
        == 2
    )


def test_normalize_rejects_merged_employment_entries() -> None:
    source = (
        "Rahul Kumar\n\n"
        "EXPERIENCE\n"
        "Junior Support Engineer | Alpha Ltd\n"
        "Jan 2023 - Dec 2023\n"
        "- Resolved customer incidents.\n"
        "- Documented support procedures.\n"
        "Software Engineer Intern | Beta Labs\n"
        "Jun 2022 - Dec 2022\n"
        "- Built Python API endpoints.\n"
        "- Added automated tests.\n\n"
        "EDUCATION\nB.Tech in Computer Science"
    )
    result = legacy_result().model_copy(
        update={
            "optimized_resume_draft": (
                "Rahul Kumar\n\n"
                "EXPERIENCE\n"
                "Junior Support Engineer / Software Engineer Intern | Alpha and Beta\n"
                "Jan 2023 - Dec 2023 / Jun 2022 - Dec 2022\n"
                "- Combined support work with Python development.\n\n"
                "EDUCATION\nB.Tech in Computer Science"
            )
        }
    )

    normalized = ImprovementService.normalize(result, source)

    assert "Junior Support Engineer / Software Engineer Intern" not in (
        normalized.optimized_resume_draft
    )
    assert "Junior Support Engineer | Alpha Ltd" in normalized.optimized_resume_draft
    assert "Software Engineer Intern | Beta Labs" in normalized.optimized_resume_draft
    assert "- Resolved customer incidents." in normalized.optimized_resume_draft
    assert "- Built Python API endpoints." in normalized.optimized_resume_draft


def test_normalize_keeps_generated_bullets_with_their_original_role() -> None:
    source = (
        "Rahul Kumar\n\n"
        "WORK EXPERIENCE\n"
        "Junior Support Engineer | Alpha Ltd\n"
        "Jan 2023 - Dec 2023\n"
        "- Resolved customer incidents.\n"
        "Software Engineer Intern | Beta Labs\n"
        "Jun 2022 - Dec 2022\n"
        "- Built Python API endpoints."
    )
    result = legacy_result().model_copy(
        update={
            "optimized_resume_draft": (
                "Rahul Kumar\n\n"
                "WORK EXPERIENCE\n"
                "Junior Support Engineer | Alpha Ltd\n"
                "2023\n"
                "- Resolved priority incidents and documented resolutions.\n"
                "Software Engineer Intern | Beta Labs\n"
                "2022\n"
                "- Built tested Python API endpoints."
            )
        }
    )

    normalized = ImprovementService.normalize(result, source)
    document = normalized.structured_resume

    assert document is not None
    experience = next(
        section for section in document.sections if section.heading == "WORK EXPERIENCE"
    )
    groups = ImprovementService._entry_blocks(experience.items)
    assert len(groups) == 2
    assert groups[0][:2] == [
        "Junior Support Engineer | Alpha Ltd",
        "Jan 2023 - Dec 2023",
    ]
    assert groups[0][2] == ("- Resolved priority incidents and documented resolutions.")
    assert groups[1][:2] == [
        "Software Engineer Intern | Beta Labs",
        "Jun 2022 - Dec 2022",
    ]
    assert groups[1][2] == "- Built tested Python API endpoints."


def test_normalize_repairs_bulletless_pdf_experience_without_moving_bullets() -> None:
    source = (
        "Rahul Kumar\n\n"
        "PROFESSIONAL EXPERIENCE\n"
        "Junior Support Engineer – GoApptiv Private Limited\n"
        "07/2024\n"
        "present\n"
        "Hyderabad, India\n"
        "Designed scalable Node.js and NestJS microservices serving 350K+ users.\n"
        "Engineered Google Pub/Sub synchronization across 3 platforms.\n"
        "Software Engineer Intern – GoApptiv Private Limited\n"
        "12/2023\n"
        "06/2024\n"
        "Hyderabad\n"
        "Enhanced SQL query performance, reducing API response times by 20-30%.\n"
        "Automated onboarding workflows using Python scripts."
    )
    result = legacy_result().model_copy(
        update={
            "optimized_resume_draft": (
                "Rahul Kumar\n\n"
                "PROFESSIONAL EXPERIENCE\n"
                "Junior Support Engineer – GoApptiv Private Limited\n"
                "07/2024\n"
                "present\n"
                "Hyderabad, India\n"
                "Designed production-grade Node.js and NestJS microservices serving "
                "350K+ users.\n"
                "Engineered Google Pub/Sub synchronization across 3 platforms.\n"
                "Software Engineer Intern – GoApptiv Private Limited\n"
                "12/2023\n"
                "06/2024\n"
                "Hyderabad\n"
                "Enhanced SQL query performance, reducing API response times by "
                "20-30%.\n"
                "Automated onboarding workflows using Python scripts.\n"
                "- Designed scalable Node.js and NestJS microservices serving 350K+ "
                "users.\n"
                "- Engineered Google Pub/Sub synchronization across 3 platforms."
            )
        }
    )

    normalized = ImprovementService.normalize(result, source)
    document = normalized.structured_resume

    assert document is not None
    experience = next(
        section
        for section in document.sections
        if section.heading == "PROFESSIONAL EXPERIENCE"
    )
    groups = ImprovementService._entry_blocks(experience.items)
    assert len(groups) == 2
    assert groups[0][0] == "Junior Support Engineer – GoApptiv Private Limited"
    assert groups[1][0] == "Software Engineer Intern – GoApptiv Private Limited"
    assert sum("Designed production-grade Node.js" in item for item in groups[0]) == 1
    assert not any("Designed production-grade Node.js" in item for item in groups[1])
    assert any("Enhanced SQL query performance" in item for item in groups[1])
    assert any("Automated onboarding workflows" in item for item in groups[1])


def test_result_migrates_saved_v1_draft_from_immutable_source(monkeypatch) -> None:
    source = (
        "Rahul Kumar\n\n"
        "EXPERIENCE\n"
        "Support Engineer | Alpha Ltd\n"
        "2024 - present\n"
        "- Resolved production incidents.\n"
        "Software Engineer Intern | Alpha Ltd\n"
        "2023 - 2024\n"
        "- Built Python APIs."
    )
    corrupt = legacy_result().model_copy(
        update={
            "optimized_resume_draft": (
                "Rahul Kumar\n\n"
                "EXPERIENCE\n"
                "Support Engineer / Software Engineer Intern | Alpha Ltd\n"
                "2023 - present\n"
                "- Combined all responsibilities."
            )
        }
    )
    corrupt = corrupt.model_copy(
        update={
            "structured_resume": ImprovementService._structure_draft(
                corrupt.optimized_resume_draft
            )
        }
    )
    record = ImprovementRecord(
        analysis_id="analysis-id",
        owner_uid="user-id",
        resume_id="resume-id",
        provider="gemini",
        model="gemini",
        result=corrupt.model_dump(),
    )
    monkeypatch.setattr(
        ResumeRepository,
        "get_owned",
        lambda *_args: SimpleNamespace(text_storage_path="resume/source.txt"),
    )
    monkeypatch.setattr(ResumeStorageService, "read_text", lambda *_args: source)

    migrated = ImprovementService.result(record)

    assert migrated.structured_resume is not None
    assert migrated.structured_resume.schema_version == 2
    assert "Support Engineer / Software Engineer Intern" not in (
        migrated.optimized_resume_draft
    )
    assert "Support Engineer | Alpha Ltd" in migrated.optimized_resume_draft
    assert "Software Engineer Intern | Alpha Ltd" in migrated.optimized_resume_draft
    assert "- Resolved production incidents." in migrated.optimized_resume_draft
    assert "- Built Python APIs." in migrated.optimized_resume_draft


def test_structure_draft_ignores_pdf_header_separators_and_preserves_overflow() -> None:
    meaningful_header = [f"Profile detail {index}" for index in range(22)]
    draft = "\n".join(
        [
            "Rahul Kumar",
            *[value for pair in zip(["–"] * 21, ["|"] * 21) for value in pair],
            *meaningful_header,
            "LinkedIn: https://linkedin.com/in/rahul51",
            "PROJECTS",
            "Resume Optimizer",
            "- Built an ATS-focused resume editor.",
        ]
    )

    document = ImprovementService._structure_draft(draft)

    assert all(re.search(r"\w", line) for line in document.header)
    assert len(document.header) == 20
    assert document.header[0] == "Rahul Kumar"
    overflow = document.sections[0]
    assert overflow.heading == "Additional Information"
    assert "Profile detail 21" in overflow.items[0]
    assert "linkedin.com/in/rahul51" in overflow.items[0]
    assert document.sections[1].heading == "PROJECTS"


def test_update_layout_preserves_draft_metadata_and_increments_revision(
    monkeypatch,
) -> None:
    created_at = datetime(2026, 7, 15, tzinfo=UTC)
    existing = ImprovementRecord(
        analysis_id="analysis-id",
        owner_uid="user-id",
        resume_id="resume-id",
        provider="gemini",
        model="gemini-3.1-flash-lite",
        result=legacy_result().model_dump(),
        company_name="Example Tech",
        role_name="Backend Engineer",
        application_date="2026-07-15",
        layout_settings=ResumeLayoutSettings().model_dump(),
        revision=3,
        created_at=created_at,
    )
    saved: list[ImprovementRecord] = []
    monkeypatch.setattr(
        ImprovementRepository,
        "get_owned",
        lambda *_args: existing,
    )
    monkeypatch.setattr(ImprovementRepository, "save", saved.append)

    layout = ResumeLayoutSettings(body_size=11, margin_left=0.7)
    updated = ImprovementService.update_layout("user-id", "analysis-id", layout)

    assert updated.result == existing.result
    assert updated.company_name == "Example Tech"
    assert updated.created_at == created_at
    assert updated.revision == 4
    assert updated.layout_settings == layout.model_dump()
    assert saved == [updated]

from app.ai.schemas import BulletRewrite, ResumeImprovementResult, TailoringDecision
from app.services.improvement_service import ImprovementService


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

from types import SimpleNamespace

from app.ai.schemas import (
    BulletOptimizationResult,
    OptimizedBullet,
    ResumeAnalysisResult,
    SkillIntegrationSuggestion,
    StructuredResumeDocument,
    StructuredResumeSection,
)
from app.repositories.analysis_repository import AnalysisRepository
from app.services import bullet_optimization_service as service_module
from app.services.bullet_optimization_service import BulletOptimizationService
from app.services.improvement_service import ImprovementService


def tailored_result():
    return SimpleNamespace(
        structured_resume=StructuredResumeDocument(
            header=["Rahul Kumar"],
            sections=[
                StructuredResumeSection(
                    section_id="section-experience",
                    heading="EXPERIENCE",
                    items=[
                        "Backend Engineer | Example Tech | 2022-Present",
                        "- Built Python and FastAPI services.",
                        "- Improved API reliability through testing.",
                        "- Reduced deployment time by 40%.",
                        "Support Engineer | Earlier Co | 2020-2022",
                        "- Resolved customer incidents.",
                    ],
                ),
                StructuredResumeSection(
                    section_id="section-skills",
                    heading="SKILLS",
                    items=[
                        "Languages: Python, Java",
                        "Automation: n8n, R",
                    ],
                ),
            ],
        )
    )


def analysis_result() -> ResumeAnalysisResult:
    return ResumeAnalysisResult(
        match_score=80,
        summary="Strong backend alignment.",
        strengths=["Python"],
        matched_keywords=["Python", "FastAPI"],
        missing_keywords=["Kubernetes"],
        recommendations=["Prioritize relevant backend achievements."],
    )


def configure(
    monkeypatch,
    optimized: BulletOptimizationResult,
    calls: dict | None = None,
) -> None:
    monkeypatch.setattr(ImprovementService, "get", lambda *_args: object())
    monkeypatch.setattr(
        ImprovementService,
        "result",
        lambda _record: tailored_result(),
    )
    monkeypatch.setattr(
        AnalysisRepository,
        "get_owned",
        lambda *_args: SimpleNamespace(
            job_description="Build Python and FastAPI services.",
            result=analysis_result().model_dump(),
        ),
    )
    def optimize_bullets(**kwargs):
        if calls is not None:
            calls.update(kwargs)
        return optimized

    provider = SimpleNamespace(optimize_bullets=optimize_bullets)
    monkeypatch.setattr(service_module, "get_ai_provider", lambda: provider)


def test_proposal_targets_one_entry_and_preserves_keywords(monkeypatch) -> None:
    configure(
        monkeypatch,
        BulletOptimizationResult(
            bullets=[
                OptimizedBullet(
                    text="Built Python and FastAPI services with reliable testing.",
                    source_indices=[0, 1],
                ),
                OptimizedBullet(
                    text="Reduced deployment time by 40%.",
                    source_indices=[2],
                ),
            ],
            rationale="Consolidates overlapping API evidence.",
        ),
    )

    proposal = BulletOptimizationService.propose(
        "user-id",
        "analysis-id",
        "section-experience",
        0,
        2,
        "consolidate",
    )

    assert proposal.item_indices == [1, 2, 3]
    assert proposal.entry_label.startswith("Backend Engineer")
    assert len(proposal.proposed_bullets) == 2
    assert proposal.protected_keywords == ["Python", "FastAPI"]
    assert proposal.can_apply is True


def test_proposal_blocks_when_supported_keyword_is_lost(monkeypatch) -> None:
    configure(
        monkeypatch,
        BulletOptimizationResult(
            bullets=[
                OptimizedBullet(
                    text="Improved API reliability through testing.",
                    source_indices=[1],
                )
            ],
            rationale="Prioritizes reliability evidence.",
        ),
    )

    proposal = BulletOptimizationService.propose(
        "user-id",
        "analysis-id",
        "section-experience",
        0,
        1,
        "prioritize",
    )

    assert proposal.can_apply is False
    assert proposal.lost_keywords == ["Python", "FastAPI"]


def test_rewrite_keeps_count_and_surfaces_confirmed_skill_candidates(
    monkeypatch,
) -> None:
    calls: dict = {}
    configure(
        monkeypatch,
        BulletOptimizationResult(
            bullets=[
                OptimizedBullet(
                    text="Built job-aligned Python and FastAPI services.",
                    source_indices=[0],
                ),
                OptimizedBullet(
                    text="Strengthened API reliability through automated testing.",
                    source_indices=[1],
                ),
                OptimizedBullet(
                    text="Reduced deployment time by 40%.",
                    source_indices=[2],
                ),
            ],
            skill_integrations=[
                SkillIntegrationSuggestion(
                    bullet_index=1,
                    skills=["n8n"],
                    suggested_text=(
                        "Strengthened API reliability through n8n-based automation "
                        "and testing."
                    ),
                    reason="Confirm that n8n powered this automation.",
                )
            ],
            rationale="Rewrites each bullet for the target role.",
        ),
        calls,
    )

    proposal = BulletOptimizationService.propose(
        "user-id",
        "analysis-id",
        "section-experience",
        0,
        3,
        "rewrite",
    )

    assert proposal.mode == "rewrite"
    assert proposal.target_count == len(proposal.original_bullets)
    assert calls["candidate_skills"] == ["Python", "Java", "n8n", "R"]
    assert proposal.skill_integrations[0].skills == ["n8n"]
    assert "n8n-based automation" in (
        proposal.skill_integrations[0].suggested_bullet
    )
    assert proposal.can_apply is True


def test_rewrite_keeps_original_when_ai_changes_source_evidence(monkeypatch) -> None:
    configure(
        monkeypatch,
        BulletOptimizationResult(
            bullets=[
                OptimizedBullet(
                    text="Built scalable APIs for customers.",
                    source_indices=[0],
                ),
                OptimizedBullet(
                    text="Improved API reliability through testing.",
                    source_indices=[1],
                ),
                OptimizedBullet(
                    text="Reduced deployment time by 40 percent.",
                    source_indices=[2],
                ),
            ],
            rationale="Rewrites each bullet for the role.",
        ),
    )

    proposal = BulletOptimizationService.propose(
        "user-id",
        "analysis-id",
        "section-experience",
        0,
        3,
        "rewrite",
    )

    assert proposal.proposed_bullets[0] == "- Built Python and FastAPI services."
    assert proposal.proposed_bullets[2] == "- Reduced deployment time by 40%."
    assert "kept unchanged" in proposal.rationale


def test_rewrite_does_not_request_confirmation_for_source_backed_skill(
    monkeypatch,
) -> None:
    configure(
        monkeypatch,
        BulletOptimizationResult(
            bullets=[
                OptimizedBullet(
                    text="Built Python and FastAPI services.",
                    source_indices=[0],
                ),
                OptimizedBullet(
                    text="Improved API reliability through testing.",
                    source_indices=[1],
                ),
                OptimizedBullet(
                    text="Reduced deployment time by 40%.",
                    source_indices=[2],
                ),
            ],
            skill_integrations=[
                SkillIntegrationSuggestion(
                    bullet_index=0,
                    skills=["Python"],
                    suggested_text="Built Python services with FastAPI.",
                    reason="Confirm Python usage.",
                )
            ],
            rationale="Rewrites each bullet for the role.",
        ),
    )

    proposal = BulletOptimizationService.propose(
        "user-id",
        "analysis-id",
        "section-experience",
        0,
        3,
        "rewrite",
    )

    assert proposal.skill_integrations == []


def test_rewrite_fidelity_rejects_rounded_metrics_and_ranges() -> None:
    source = (
        "- Supported 350K+ users, reducing duplicate accounts by 5-6% and "
        "turnaround time from 2-3 business days to 2-3 hours."
    )
    proposed = (
        "- Supported 350,000 users, reducing duplicate accounts by 6% and "
        "turnaround time from days to hours."
    )

    assert BulletOptimizationService._rewrite_preserves_evidence(
        source,
        proposed,
        [],
    ) is False
    assert BulletOptimizationService._rewrite_preserves_evidence(
        source,
        source,
        [],
    ) is True


def test_skill_detection_accepts_source_backed_architecture_phrase() -> None:
    assert BulletOptimizationService._contains_skill(
        "Engineered an event-driven synchronization framework.",
        "Event-Driven Architecture",
    )


def test_groups_do_not_mix_bullets_between_entries() -> None:
    section = tailored_result().structured_resume.sections[0]

    groups = BulletOptimizationService.groups(section.items)

    assert len(groups) == 2
    assert groups[0][1] == [1, 2, 3]
    assert groups[1][1] == [5]


def test_groups_use_role_line_when_entry_has_separate_metadata() -> None:
    groups = BulletOptimizationService.groups(
        [
            "Junior Support Engineer | Alpha Ltd",
            "Jan 2023 - Dec 2023",
            "Remote",
            "- Resolved customer incidents.",
            "Software Engineer Intern | Beta Labs",
            "Jun 2022 - Dec 2022",
            "- Built Python API endpoints.",
        ]
    )

    assert [group[0] for group in groups] == [
        "Junior Support Engineer | Alpha Ltd",
        "Software Engineer Intern | Beta Labs",
    ]
    assert groups[0][1] == [3]
    assert groups[1][1] == [6]

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.ai.schemas import ResumeAnalysisResult
from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app
from app.models.analysis import AnalysisRecord
from app.models.improvement import ImprovementRecord
from app.models.layout import ResumeLayoutSettings
from app.repositories.analysis_repository import AnalysisNotFoundError
from app.services.analysis_service import AnalysisService
from app.services.bullet_optimization_service import (
    BulletOptimizationProposal,
    BulletOptimizationService,
    SkillIntegrationProposal,
)
from app.services.export_service import ResumeExportService
from app.services.improvement_service import ImprovementService

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_authentication() -> None:
    async def get_test_user() -> CurrentUser:
        return CurrentUser("test-user-id", "test@example.com", True)

    app.dependency_overrides[get_current_user] = get_test_user
    yield
    app.dependency_overrides.clear()


def test_create_analysis_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = ResumeAnalysisResult(
        match_score=82,
        summary="Strong backend alignment with a few missing platform skills.",
        strengths=["Python", "FastAPI"],
        gaps=["No Kubernetes evidence"],
        matched_keywords=["Python", "REST APIs"],
        missing_keywords=["Kubernetes"],
        recommendations=["Add measurable API reliability outcomes."],
    )

    def analyze(*_args: object) -> tuple[str, str, str, ResumeAnalysisResult]:
        return "analysis-id", "gemini", "gemini-3.5-flash", result

    monkeypatch.setattr(AnalysisService, "analyze", analyze)
    response = client.post(
        "/api/v1/analyses",
        json={
            "resume_id": "resume-id",
            "job_title": "Backend Engineer",
            "job_description": "Build reliable Python APIs and distributed systems. "
            * 3,
        },
    )

    assert response.status_code == 201
    assert response.json()["provider"] == "gemini"
    assert response.json()["result"]["match_score"] == 82


def test_create_analysis_rejects_short_job_description() -> None:
    response = client.post(
        "/api/v1/analyses",
        json={"resume_id": "resume-id", "job_description": "Too short"},
    )

    assert response.status_code == 422


def test_create_analysis_requires_authentication() -> None:
    app.dependency_overrides.pop(get_current_user)
    response = client.post(
        "/api/v1/analyses",
        json={
            "resume_id": "resume-id",
            "job_description": "Build reliable Python APIs and distributed systems. "
            * 3,
        },
    )

    assert response.status_code == 401
    assert response.json()["code"] == "missing_authentication"


def stored_analysis() -> AnalysisRecord:
    return AnalysisRecord(
        analysis_id="analysis-id",
        owner_uid="test-user-id",
        resume_id="resume-id",
        job_description="Build reliable Python APIs and distributed systems. " * 3,
        job_title="Backend Engineer",
        company_name="Example Tech",
        provider="gemini",
        model="gemini-3.5-flash",
        status="completed",
        result={
            "match_score": 82,
            "summary": "Strong alignment.",
            "strengths": ["Python"],
            "gaps": ["Kubernetes"],
            "matched_keywords": ["Python"],
            "missing_keywords": ["Kubernetes"],
            "recommendations": ["Add measurable outcomes."],
        },
        created_at=datetime(2026, 7, 12, tzinfo=UTC),
    )


def test_list_analyses_returns_compact_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AnalysisService, "list", lambda *_args: [stored_analysis()])

    response = client.get("/api/v1/analyses?resume_id=resume-id")

    assert response.status_code == 200
    assert response.json()[0]["match_score"] == 82
    assert "result" not in response.json()[0]
    assert "job_description" not in response.json()[0]


def test_get_analysis_returns_stored_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AnalysisService, "get", lambda *_args: stored_analysis())

    response = client.get("/api/v1/analyses/analysis-id")

    assert response.status_code == 200
    assert response.json()["result"]["match_score"] == 82
    assert response.json()["job_title"] == "Backend Engineer"


def test_delete_analysis_returns_no_content(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        AnalysisService,
        "delete",
        lambda owner_uid, analysis_id: deleted.append((owner_uid, analysis_id)),
    )

    response = client.delete("/api/v1/analyses/analysis-id")

    assert response.status_code == 204
    assert deleted == [("test-user-id", "analysis-id")]


def test_get_analysis_hides_unowned_records(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_found(*_args: object) -> AnalysisRecord:
        raise AnalysisNotFoundError()

    monkeypatch.setattr(AnalysisService, "get", not_found)

    response = client.get("/api/v1/analyses/private-analysis")

    assert response.status_code == 404
    assert response.json()["code"] == "analysis_not_found"


def test_keyword_coverage_is_calculated_without_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        AnalysisService,
        "coverage",
        lambda *_args: (67, ["Python", "C++"], ["Kubernetes"]),
    )

    response = client.post(
        "/api/v1/analyses/analysis-id/coverage",
        json={"draft": "Built Python and C++ services."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "coverage_score": 67,
        "covered_keywords": ["Python", "C++"],
        "missing_keywords": ["Kubernetes"],
    }


def test_layout_update_returns_persisted_tailored_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ResumeLayoutSettings(body_size=11, margin_left=0.7)
    result = {
        "optimized_resume_draft": "Rahul Kumar\n\nEXPERIENCE\n- Built APIs.",
        "suggested_summary": "Backend engineer.",
        "summary_reason": "Relevant to the role.",
        "bullet_rewrites": [],
        "skills_to_emphasize": ["Python"],
        "ats_recommendations": ["Use standard headings."],
    }
    record = ImprovementRecord(
        analysis_id="analysis-id",
        owner_uid="test-user-id",
        resume_id="resume-id",
        provider="gemini",
        model="gemini-3.1-flash-lite",
        result=result,
        company_name="Example Tech",
        role_name="Backend Engineer",
        application_date="2026-07-15",
        layout_settings=layout.model_dump(),
        revision=2,
    )
    monkeypatch.setattr(
        ImprovementService,
        "update_layout",
        lambda *_args: record,
    )

    response = client.put(
        "/api/v1/analyses/analysis-id/improvements/layout",
        json={"layout": layout.model_dump()},
    )

    assert response.status_code == 200
    assert response.json()["company_name"] == "Example Tech"
    assert response.json()["revision"] == 2
    assert response.json()["layout"]["body_size"] == 11


def test_bullet_optimization_returns_reviewable_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = BulletOptimizationProposal(
        proposal_id="proposal-id",
        section_id="section-experience",
        group_index=0,
        entry_label="Backend Engineer | Example Tech",
        item_indices=[1, 2, 3],
        original_bullets=["- Built APIs.", "- Added tests.", "- Shipped faster."],
        proposed_bullets=["- Built and tested reliable APIs.", "- Shipped faster."],
        target_count=2,
        mode="consolidate",
        protected_keywords=["Python"],
        lost_keywords=[],
        rationale="Consolidates overlapping evidence.",
        skill_integrations=[
            SkillIntegrationProposal(
                suggestion_id="suggestion-id",
                bullet_index=0,
                skills=["Python"],
                suggested_bullet="- Built and tested reliable Python APIs.",
                reason="Confirm Python was used for these APIs.",
            )
        ],
    )
    monkeypatch.setattr(BulletOptimizationService, "propose", lambda *_args: proposal)

    response = client.post(
        "/api/v1/analyses/analysis-id/improvements/bullets",
        json={
            "section_id": "section-experience",
            "group_index": 0,
            "target_count": 2,
            "mode": "consolidate",
        },
    )

    assert response.status_code == 200
    assert response.json()["can_apply"] is True
    assert response.json()["item_indices"] == [1, 2, 3]
    assert response.json()["skill_integrations"] == [
        {
            "suggestion_id": "suggestion-id",
            "bullet_index": 0,
            "skills": ["Python"],
            "suggested_bullet": "- Built and tested reliable Python APIs.",
            "reason": "Confirm Python was used for these APIs.",
        }
    ]


def test_pdf_preview_renders_unsaved_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AnalysisService, "get", lambda *_args: stored_analysis())
    rendered: list[tuple[str, ResumeLayoutSettings]] = []

    def to_pdf_preview(
        draft: str,
        layout: ResumeLayoutSettings,
    ) -> tuple[bytes, int]:
        rendered.append((draft, layout))
        return b"%PDF-1.7 preview", 2

    monkeypatch.setattr(ResumeExportService, "to_pdf_preview", to_pdf_preview)
    response = client.post(
        "/api/v1/analyses/analysis-id/preview/pdf",
        json={
            "draft": "Tailored resume draft",
            "layout": {"body_size": 11, "margin_left": 0.7},
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["x-resume-page-count"] == "2"
    assert response.content == b"%PDF-1.7 preview"
    assert rendered[0][0] == "Tailored resume draft"
    assert rendered[0][1].body_size == 11
    assert rendered[0][1].margin_left == 0.7

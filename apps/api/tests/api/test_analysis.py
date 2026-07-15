from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.ai.schemas import ResumeAnalysisResult
from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app
from app.models.analysis import AnalysisRecord
from app.repositories.analysis_repository import AnalysisNotFoundError
from app.services.analysis_service import AnalysisService
from app.services.export_service import ResumeExportService

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


def test_pdf_preview_renders_unsaved_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AnalysisService, "get", lambda *_args: stored_analysis())
    rendered: list[tuple[str, int]] = []

    def to_pdf_preview(draft: str, target_pages: int) -> tuple[bytes, int]:
        rendered.append((draft, target_pages))
        return b"%PDF-1.7 preview", 2

    monkeypatch.setattr(ResumeExportService, "to_pdf_preview", to_pdf_preview)
    response = client.post(
        "/api/v1/analyses/analysis-id/preview/pdf",
        json={"draft": "Tailored resume draft", "target_pages": 1},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["x-resume-page-count"] == "2"
    assert response.headers["x-resume-target-fit"] == "false"
    assert response.content == b"%PDF-1.7 preview"
    assert rendered == [("Tailored resume draft", 1)]

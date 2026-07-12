import pytest
from fastapi.testclient import TestClient

from app.ai.schemas import ResumeAnalysisResult
from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app
from app.services.analysis_service import AnalysisService

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

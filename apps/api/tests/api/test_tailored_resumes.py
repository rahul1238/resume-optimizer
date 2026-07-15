from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app
from app.models.improvement import ImprovementRecord
from app.models.resume import ResumeRecord
from app.services.improvement_service import ImprovementService
from app.services.resume_service import ResumeService

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_authentication() -> None:
    async def get_test_user() -> CurrentUser:
        return CurrentUser("test-user-id", "test@example.com", True)

    app.dependency_overrides[get_current_user] = get_test_user
    yield
    app.dependency_overrides.clear()


def test_list_tailored_resumes_returns_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamp = datetime(2026, 7, 15, tzinfo=UTC)
    improvement = ImprovementRecord(
        analysis_id="analysis-id",
        owner_uid="test-user-id",
        resume_id="resume-id",
        provider="gemini",
        model="gemini-3.1-flash-lite",
        result={},
        company_name="Google",
        role_name="Backend Engineer",
        application_date="2026-07-15",
        revision=4,
        created_at=timestamp,
        updated_at=timestamp,
    )
    resume = ResumeRecord(
        resume_id="resume-id",
        owner_uid="test-user-id",
        filename="master.pdf",
        file_type="pdf",
        page_count=2,
        character_count=2_000,
        original_storage_path="original.pdf",
        text_storage_path="resume.txt",
        content_sha256="hash",
        title="Backend Master",
    )
    monkeypatch.setattr(ImprovementService, "list", lambda *_args: [improvement])
    monkeypatch.setattr(ResumeService, "list", lambda *_args: [resume])

    response = client.get("/api/v1/tailored-resumes?resume_id=resume-id")

    assert response.status_code == 200
    assert response.json()[0]["company_name"] == "Google"
    assert response.json()[0]["base_resume_title"] == "Backend Master"
    assert response.json()[0]["revision"] == 4
    assert "result" not in response.json()[0]

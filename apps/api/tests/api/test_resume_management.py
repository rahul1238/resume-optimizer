from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app
from app.models.resume import ResumeRecord
from app.services.resume_service import ResumeService
from app.services.resume_upload_service import ParsedResume

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_authentication() -> None:
    async def get_test_user() -> CurrentUser:
        return CurrentUser("test-user-id", "test@example.com", True)

    app.dependency_overrides[get_current_user] = get_test_user
    yield
    app.dependency_overrides.clear()


def record() -> ResumeRecord:
    return ResumeRecord(
        resume_id="resume-id",
        owner_uid="test-user-id",
        filename="resume.pdf",
        file_type="pdf",
        page_count=2,
        character_count=1200,
        original_storage_path="resumes/test-user-id/resume-id/original.pdf",
        text_storage_path="resumes/test-user-id/resume-id/extracted.txt",
        content_sha256="abc123",
        created_at=datetime(2026, 7, 12, tzinfo=UTC),
    )


def test_list_resumes_returns_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ResumeService, "list", lambda _owner_uid: [record()])

    response = client.get("/api/v1/resumes")

    assert response.status_code == 200
    assert response.json()[0]["resume_id"] == "resume-id"
    assert "text" not in response.json()[0]
    assert "original_storage_path" not in response.json()[0]


def test_get_resume_returns_extracted_text(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = ParsedResume(
        resume_id="resume-id",
        filename="resume.pdf",
        file_type="pdf",
        page_count=2,
        storage_path="internal-path",
        text_storage_path="internal-text-path",
        text="Python engineer",
    )
    monkeypatch.setattr(ResumeService, "get", lambda *_args: parsed)

    response = client.get("/api/v1/resumes/resume-id")

    assert response.status_code == 200
    assert response.json()["text"] == "Python engineer"


def test_delete_resume_returns_no_content(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ResumeService,
        "delete",
        lambda owner_uid, resume_id: deleted.append((owner_uid, resume_id)),
    )

    response = client.delete("/api/v1/resumes/resume-id")

    assert response.status_code == 204
    assert response.content == b""
    assert deleted == [("test-user-id", "resume-id")]


def test_delete_cors_preflight_allows_the_local_frontend() -> None:
    response = client.options(
        "/api/v1/resumes/resume-id",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "DELETE" in response.headers["access-control-allow-methods"]

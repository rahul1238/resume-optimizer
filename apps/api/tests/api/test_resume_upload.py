import io

import fitz
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_authentication() -> None:
    async def get_test_user() -> CurrentUser:
        return CurrentUser(
            uid="test-user-id",
            email="test@example.com",
            email_verified=True,
        )

    app.dependency_overrides[get_current_user] = get_test_user
    yield
    app.dependency_overrides.clear()


def test_upload_pdf_extracts_text() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Ada Lovelace\nPython Engineer")
    content = document.tobytes()
    document.close()

    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["file_type"] == "pdf"
    assert response.json()["page_count"] == 1
    assert "Ada Lovelace" in response.json()["text"]


def test_upload_docx_extracts_text() -> None:
    document = Document()
    document.add_paragraph("Grace Hopper")
    document.add_paragraph("Compiler Pioneer")
    content = io.BytesIO()
    document.save(content)

    response = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                "resume.docx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["file_type"] == "docx"
    assert response.json()["page_count"] is None
    assert "Grace Hopper" in response.json()["text"]


def test_upload_rejects_unsupported_format() -> None:
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.txt", b"Resume", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Only PDF and DOCX resumes are supported.",
        "code": "unsupported_resume_format",
    }


def test_upload_rejects_a_file_with_a_spoofed_pdf_extension() -> None:
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "unreadable_resume"


def test_upload_rejects_a_file_larger_than_the_allowed_limit() -> None:
    content = b"0" * (5 * 1024 * 1024 + 1)

    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", content, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "resume_too_large"


def test_upload_requires_a_firebase_id_token() -> None:
    app.dependency_overrides.pop(get_current_user)

    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-", "application/pdf")},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "A Firebase ID token is required.",
        "code": "missing_authentication",
    }

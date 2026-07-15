from types import SimpleNamespace

from app.services.ats_scan_service import ATSScanService
from app.services.resume_service import ResumeService


def test_scan_detects_standard_ats_signals(monkeypatch) -> None:
    text = """Rahul Kumar
rahul@example.com | +91 98765 43210 | https://linkedin.com/in/rahul

EXPERIENCE
Backend Engineer | Example Tech | 2022-Present
- Built Python APIs for customer workflows.
- Improved service reliability through automated testing.
- Reduced deployment time using delivery pipelines.

SKILLS
Python, FastAPI, PostgreSQL, Docker

EDUCATION
B.Tech Computer Science | State University | 2022
""" + (" Delivered measurable software outcomes." * 55)
    monkeypatch.setattr(
        ResumeService,
        "get",
        lambda *_args: SimpleNamespace(text=text),
    )

    scan = ATSScanService.scan("user-id", "resume-id")

    statuses = {check.check_id: check.status for check in scan.checks}
    assert scan.score == 100
    assert statuses["parseable_text"] == "pass"
    assert statuses["section_experience"] == "pass"
    assert statuses["professional_links"] == "pass"
    assert scan.recommendations == []


def test_scan_reports_missing_core_sections_without_ai(monkeypatch) -> None:
    monkeypatch.setattr(
        ResumeService,
        "get",
        lambda *_args: SimpleNamespace(text="Rahul Kumar\nPython developer"),
    )

    scan = ATSScanService.scan("user-id", "resume-id")

    assert scan.score < 30
    assert any("Experience" in item for item in scan.recommendations)
    assert any(check.status == "fail" for check in scan.checks)

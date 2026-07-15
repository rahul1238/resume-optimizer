import fitz
import pytest

from app.ai.schemas import ResumeImprovementResult
from app.models.layout import ResumeLayoutSettings
from app.services.export_service import ExportContext, ResumeExportService

SAMPLE_DRAFT = """Jordan Lee
jordan@example.com | +1 555 0100 | Austin, TX | https://linkedin.com/in/jordanlee

PROFESSIONAL SUMMARY
Backend engineer building reliable Python services and APIs.

EXPERIENCE
Senior Software Engineer | Example Tech | 2023-Present
- Improved API availability to 99.95% through observability and testing.
- Reduced deployment time by 40% using automated delivery pipelines.

SKILLS
Python, FastAPI, PostgreSQL, Docker, Google Cloud

EDUCATION
B.S. Computer Science | State University
"""


def improvement_result() -> ResumeImprovementResult:
    return ResumeImprovementResult(
        optimized_resume_draft=SAMPLE_DRAFT,
        suggested_summary="Backend engineer building reliable Python services.",
        summary_reason="More concise.",
        ats_recommendations=["Use standard section headings."],
    )


def test_structure_preserves_semantic_hierarchy() -> None:
    resume = ResumeExportService.structure(SAMPLE_DRAFT)

    assert resume.header[0] == "Jordan Lee"
    assert [section.heading for section in resume.sections] == [
        "PROFESSIONAL SUMMARY",
        "EXPERIENCE",
        "SKILLS",
        "EDUCATION",
    ]
    assert ResumeExportService.is_bullet(resume.sections[1].lines[1])


def test_latex_source_uses_selected_ats_layout() -> None:
    layout = ResumeLayoutSettings(
        page_format="letter",
        body_font="serif",
        heading_font="sans",
        body_size=11,
        margin_top=0.7,
        margin_right=0.8,
        margin_bottom=0.9,
        margin_left=1,
        line_spacing=1.3,
    )

    source = ResumeExportService._latex_source(
        ResumeExportService.structure(SAMPLE_DRAFT),
        layout,
    )

    assert "letterpaper" in source
    assert "top=0.7in,right=0.8in,bottom=0.9in,left=1.0in" in source
    assert r"\setmainfont{lmroman10-regular.otf}" in source
    assert r"\newfontfamily\headingfont{lmsans10-regular.otf}" in source
    assert r"\fontsize{11.0}{14.30}\selectfont" in source


@pytest.mark.parametrize("template", ["classic", "compact", "technical"])
def test_pdf_templates_are_text_parseable_and_preserve_links(template) -> None:
    pdf = ResumeExportService.to_pdf(
        SAMPLE_DRAFT,
        ResumeLayoutSettings(template=template),
    )

    with fitz.open(stream=pdf, filetype="pdf") as document:
        extracted = "\n".join(page.get_text() for page in document)
        links = [link for page in document for link in page.get_links()]

    assert "99.95%" in extracted
    assert any(
        link.get("uri") == "https://linkedin.com/in/jordanlee" for link in links
    )


def test_templates_change_layout_without_changing_resume_content() -> None:
    resume = ResumeExportService.structure(SAMPLE_DRAFT)
    sources = {
        template: ResumeExportService._latex_source(
            resume,
            ResumeLayoutSettings(template=template),
        )
        for template in ("classic", "compact", "technical")
    }

    assert r"\begin{center}" in sources["classic"]
    assert r"\titlerule" not in sources["compact"]
    assert r"\begin{flushleft}" in sources["technical"]
    for source in sources.values():
        assert "Jordan Lee" in source
        assert "Reduced deployment time by 40" in source


def test_restores_links_missing_from_cached_optimized_draft() -> None:
    cached_draft = SAMPLE_DRAFT.replace(
        " | https://linkedin.com/in/jordanlee",
        "",
    )
    source_text = """Jordan Lee
rahul51

LINKS
LinkedIn: https://www.linkedin.com/in/rahul51
GitHub: https://github.com/rahul51
"""

    restored = ResumeExportService._restore_source_links(cached_draft, source_text)
    resume = ResumeExportService.structure(restored)

    assert any("linkedin.com/in/rahul51" in line for line in resume.header)
    assert any("github.com/rahul51" in line for line in resume.header)


def test_two_page_pdf_is_returned_without_content_fitting(monkeypatch) -> None:
    oversized = fitz.open()
    oversized.new_page()
    oversized.new_page()
    content = oversized.tobytes()
    oversized.close()
    monkeypatch.setattr(ResumeExportService, "_render_pdf", lambda *_args: content)
    monkeypatch.setattr(ResumeExportService, "_validate_pdf", lambda *_args: None)

    exported = ResumeExportService.to_pdf(SAMPLE_DRAFT, ResumeLayoutSettings())
    preview, page_count = ResumeExportService.to_pdf_preview(
        SAMPLE_DRAFT,
        ResumeLayoutSettings(),
    )

    assert exported == content
    assert preview == content
    assert page_count == 2


def test_export_filename_uses_first_name_and_company() -> None:
    context = ExportContext(
        result=improvement_result(),
        draft=SAMPLE_DRAFT,
        company_name="Example Tech, Inc.",
        layout=ResumeLayoutSettings(),
    )

    assert ResumeExportService.export_filename(context) == "Jordan_Example.pdf"

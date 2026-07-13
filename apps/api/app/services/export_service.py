import re
from html import escape
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Inches, Pt
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.services.improvement_service import ImprovementService


class ResumeExportError(Exception):
    status_code = 409
    code = "resume_draft_not_ready"
    message = "Generate and save an optimized resume draft before exporting."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ResumeExportService:
    section_names = {
        "summary",
        "professional summary",
        "experience",
        "professional experience",
        "work experience",
        "education",
        "skills",
        "technical skills",
        "projects",
        "certifications",
        "awards",
    }

    @classmethod
    def get_draft(cls, owner_uid: str, analysis_id: str) -> str:
        record = ImprovementService.get(owner_uid, analysis_id)
        draft = ImprovementService.result(record).optimized_resume_draft.strip()
        if not draft:
            raise ResumeExportError()
        return draft

    @classmethod
    def is_heading(cls, line: str) -> bool:
        normalized = line.strip().rstrip(":").lower()
        return normalized in cls.section_names or (
            len(line) <= 45
            and line.isupper()
            and any(character.isalpha() for character in line)
        )

    @staticmethod
    def is_bullet(line: str) -> bool:
        return bool(re.match(r"^\s*[-*•]\s+", line))

    @staticmethod
    def bullet_text(line: str) -> str:
        return re.sub(r"^\s*[-*•]\s+", "", line).strip()

    @classmethod
    def to_docx(cls, draft: str) -> bytes:
        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.65)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        styles = document.styles
        styles["Normal"].font.name = "Arial"
        styles["Normal"].font.size = Pt(10)

        nonempty_index = 0
        for raw_line in draft.splitlines():
            line = raw_line.strip()
            if not line:
                document.add_paragraph().paragraph_format.space_after = Pt(0)
                continue
            if cls.is_heading(line):
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_before = Pt(10)
                paragraph.paragraph_format.space_after = Pt(4)
                run = paragraph.add_run(line.rstrip(":"))
                run.bold = True
                run.font.size = Pt(11)
            elif cls.is_bullet(line):
                paragraph = document.add_paragraph(style="List Bullet")
                paragraph.add_run(cls.bullet_text(line))
                paragraph.paragraph_format.space_after = Pt(2)
            else:
                paragraph = document.add_paragraph(line)
                paragraph.paragraph_format.space_after = Pt(3)
                if nonempty_index == 0:
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                    paragraph.runs[0].bold = True
                    paragraph.runs[0].font.size = Pt(16)
            nonempty_index += 1

        output = BytesIO()
        document.save(output)
        return output.getvalue()

    @classmethod
    def to_pdf(cls, draft: str) -> bytes:
        font_dir = Path(__import__("reportlab").__file__).parent / "fonts"
        pdfmetrics.registerFont(TTFont("ResumeVera", str(font_dir / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("ResumeVeraBold", str(font_dir / "VeraBd.ttf")))

        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=LETTER,
            rightMargin=0.7 * inch,
            leftMargin=0.7 * inch,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
            title="Optimized Resume",
        )
        sample = getSampleStyleSheet()
        body = ParagraphStyle(
            "ResumeBody",
            parent=sample["BodyText"],
            fontName="ResumeVera",
            fontSize=9.5,
            leading=13,
            spaceAfter=3,
        )
        heading = ParagraphStyle(
            "ResumeHeading",
            parent=body,
            fontName="ResumeVeraBold",
            fontSize=10.5,
            leading=14,
            spaceBefore=9,
            spaceAfter=4,
        )
        name = ParagraphStyle(
            "ResumeName",
            parent=heading,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=6,
        )
        bullet = ParagraphStyle(
            "ResumeBullet",
            parent=body,
            leftIndent=12,
            firstLineIndent=-8,
            bulletIndent=2,
        )

        story = []
        nonempty_index = 0
        for raw_line in draft.splitlines():
            line = raw_line.strip()
            if not line:
                story.append(Spacer(1, 4))
                continue
            safe_line = escape(line)
            if nonempty_index == 0:
                story.append(Paragraph(safe_line, name))
            elif cls.is_heading(line):
                story.append(Paragraph(safe_line.rstrip(":"), heading))
            elif cls.is_bullet(line):
                story.append(
                    Paragraph(
                        escape(cls.bullet_text(line)),
                        bullet,
                        bulletText="•",
                    )
                )
            else:
                story.append(Paragraph(safe_line, body))
            nonempty_index += 1

        document.build(story)
        return output.getvalue()

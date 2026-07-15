import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from app.ai.schemas import ResumeImprovementResult
from app.core.config import settings
from app.models.layout import ResumeLayoutSettings
from app.parsers.resume_parser import ResumeParser
from app.repositories.resume_repository import ResumeRepository
from app.services.improvement_service import ImprovementService
from app.services.resume_storage_service import ResumeStorageService

logger = logging.getLogger(__name__)


class ResumeExportError(Exception):
    status_code = 409
    code = "resume_draft_not_ready"
    message = "Generate and save an optimized resume draft before exporting."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ResumeExportValidationError(ResumeExportError):
    code = "resume_export_validation_failed"
    message = "The generated resume could not be validated for reliable text parsing."


class LatexCompilationError(ResumeExportError):
    status_code = 503
    code = "latex_compiler_unavailable"
    message = "The PDF generator is temporarily unavailable."


@dataclass(frozen=True)
class ResumeSection:
    heading: str
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredResume:
    header: list[str]
    sections: list[ResumeSection]

    @property
    def all_text(self) -> str:
        parts = list(self.header)
        for section in self.sections:
            parts.append(section.heading)
            parts.extend(section.lines)
        return "\n".join(parts)


@dataclass(frozen=True)
class ExportContext:
    result: ResumeImprovementResult
    draft: str
    company_name: str | None
    layout: ResumeLayoutSettings


class ResumeExportService:
    section_names = {
        "summary",
        "professional summary",
        "profile",
        "objective",
        "experience",
        "professional experience",
        "work experience",
        "employment history",
        "education",
        "skills",
        "technical skills",
        "core competencies",
        "projects",
        "certifications",
        "licenses",
        "awards",
        "publications",
        "volunteering",
        "languages",
    }
    @classmethod
    def get_context(cls, owner_uid: str, analysis_id: str) -> ExportContext:
        improvement = ImprovementService.get(owner_uid, analysis_id)
        result = ImprovementService.result(improvement)
        if not result.optimized_resume_draft.strip():
            raise ResumeExportError()
        resume = ResumeRepository.get_owned(improvement.resume_id, owner_uid)
        source_text = ResumeStorageService.read_text(resume.text_storage_path)
        draft = cls._restore_source_links(
            result.optimized_resume_draft,
            source_text,
        )
        return ExportContext(
            result,
            draft,
            improvement.company_name,
            ResumeLayoutSettings.model_validate(improvement.layout_settings or {}),
        )

    @classmethod
    def get_draft(cls, owner_uid: str, analysis_id: str) -> str:
        return cls.get_context(owner_uid, analysis_id).draft

    @classmethod
    def _restore_source_links(cls, draft: str, source_text: str) -> str:
        pattern = re.compile(r"(?:https?://|mailto:|tel:)[^\s<>|]+")
        draft_urls = {
            normalized
            for value in pattern.findall(draft)
            if (normalized := ResumeParser._normalize_url(value.rstrip(".,;)")))
        }
        missing: list[tuple[str, str]] = []
        seen = set(draft_urls)
        for line in source_text.splitlines():
            for match in pattern.finditer(line):
                normalized = ResumeParser._normalize_url(
                    match.group(0).rstrip(".,;)")
                )
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                prefix = line[: match.start()].strip().rstrip(":|- ")
                label = ResumeParser._link_label(prefix, normalized)
                missing.append((label, normalized))
        if not missing:
            return draft.strip()

        link_line = " | ".join(f"{label}: {url}" for label, url in missing)
        lines = draft.strip().splitlines()
        heading_index = next(
            (index for index, line in enumerate(lines) if cls.is_heading(line)),
            len(lines),
        )
        lines.insert(heading_index, link_line)
        return "\n".join(lines)

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
        return bool(re.match(r"^\s*[-*\u2022]\s+", line))

    @staticmethod
    def bullet_text(line: str) -> str:
        return re.sub(r"^\s*[-*\u2022]\s+", "", line).strip()

    @classmethod
    def structure(cls, draft: str) -> StructuredResume:
        header: list[str] = []
        sections: list[ResumeSection] = []
        heading: str | None = None
        lines: list[str] = []

        def flush() -> None:
            nonlocal lines
            if heading is not None:
                sections.append(ResumeSection(heading.rstrip(":"), lines))
            lines = []

        for raw_line in draft.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if cls.is_heading(line):
                flush()
                heading = line
            elif heading is None:
                header.append(line)
            else:
                lines.append(line)
        flush()

        if not header and sections:
            first = sections.pop(0)
            header = [first.heading, *first.lines[:1]]
            if len(first.lines) > 1:
                sections.insert(0, ResumeSection("Profile", first.lines[1:]))
        if not header:
            raise ResumeExportError("The optimized draft does not contain usable text.")
        return StructuredResume(header[:6], sections)

    @classmethod
    def to_pdf(
        cls,
        draft: str,
        layout: ResumeLayoutSettings | None = None,
    ) -> bytes:
        resume = cls.structure(draft)
        content = cls._render_pdf(resume, layout or ResumeLayoutSettings())
        cls._validate_pdf(content, resume.all_text)
        return content

    @classmethod
    def to_pdf_preview(
        cls,
        draft: str,
        layout: ResumeLayoutSettings | None = None,
    ) -> tuple[bytes, int]:
        resume = cls.structure(draft)
        content = cls._render_pdf(resume, layout or ResumeLayoutSettings())
        with fitz.open(stream=content, filetype="pdf") as document:
            page_count = len(document)
        cls._validate_pdf(content, resume.all_text)
        return content, page_count

    @classmethod
    def export_filename(cls, context: ExportContext) -> str:
        resume = cls.structure(context.draft)
        first_name = cls._filename_part(resume.header[0].split()[0], "Resume")
        company = cls._filename_part(
            (context.company_name or "Tailored").split()[0],
            "Tailored",
        )
        return f"{first_name}_{company}.pdf"

    @staticmethod
    def _filename_part(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "", value)
        return cleaned or fallback

    @classmethod
    def _render_pdf(
        cls,
        resume: StructuredResume,
        layout: ResumeLayoutSettings,
    ) -> bytes:
        source = cls._latex_source(resume, layout)
        try:
            with tempfile.TemporaryDirectory(prefix="resume-latex-") as directory:
                source_path = Path(directory) / "resume.tex"
                source_path.write_text(source, encoding="utf-8")
                command = [settings.tectonic_binary]
                if settings.tectonic_only_cached:
                    command.append("--only-cached")
                command.extend(
                    ["--untrusted", "--outdir", directory, str(source_path)]
                )
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=settings.latex_compile_timeout_seconds,
                )
                output_path = Path(directory) / "resume.pdf"
                if completed.returncode != 0 or not output_path.exists():
                    logger.error(
                        "Tectonic resume compilation failed: %s",
                        completed.stderr[-2000:],
                    )
                    raise LatexCompilationError()
                return output_path.read_bytes()
        except (OSError, subprocess.SubprocessError) as error:
            raise LatexCompilationError() from error

    @classmethod
    def _latex_source(
        cls,
        resume: StructuredResume,
        layout: ResumeLayoutSettings,
    ) -> str:
        header_lines = "\\\\\n".join(
            cls._latex_text(line) for line in resume.header[1:]
        )
        sections = "\n".join(cls._latex_section(section) for section in resume.sections)
        heading_style = (
            rf"\headingfont\bfseries\fontsize{{{layout.heading_size}}}"
            rf"{{{layout.heading_size + 2}}}\selectfont"
        )
        name_style = (
            rf"\headingfont\bfseries\fontsize{{{layout.name_size}}}"
            rf"{{{layout.name_size + 2}}}\selectfont"
        )
        math_sizes = "\n".join(
            rf"\DeclareMathSizes{{{size}}}{{10}}{{7}}{{5}}"
            for size in {
                layout.body_size,
                layout.heading_size,
                layout.name_size,
            }
        )
        name = cls._latex_text(resume.header[0])
        paper = "a4paper" if layout.page_format == "a4" else "letterpaper"
        body_font = (
            "lmroman10-regular.otf" if layout.body_font == "serif"
            else "lmsans10-regular.otf"
        )
        body_bold = (
            "lmroman10-bold.otf" if layout.body_font == "serif"
            else "lmsans10-bold.otf"
        )
        heading_font = (
            "lmroman10-regular.otf" if layout.heading_font == "serif"
            else "lmsans10-regular.otf"
        )
        heading_bold = (
            "lmroman10-bold.otf" if layout.heading_font == "serif"
            else "lmsans10-bold.otf"
        )
        leading = layout.body_size * layout.line_spacing
        return rf"""\documentclass[10pt,{paper}]{{article}}
\usepackage[top={layout.margin_top}in,right={layout.margin_right}in,bottom={layout.margin_bottom}in,left={layout.margin_left}in]{{geometry}}
\usepackage{{fontspec}}
\usepackage{{titlesec}}
\usepackage{{enumitem}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{xurl}}
\setmainfont{{{body_font}}}[BoldFont={body_bold}]
\newfontfamily\headingfont{{{heading_font}}}[BoldFont={heading_bold}]
\setmonofont{{lmmono10-regular.otf}}
{math_sizes}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{{layout.block_spacing}pt}}
\setlist[itemize]{{leftmargin=1.15em,itemsep={layout.block_spacing}pt,topsep=1pt,parsep=0pt}}
\titleformat{{\section}}{{{heading_style}}}{{}}{{0pt}}{{\MakeUppercase}}[\vspace{{-2pt}}\titlerule]
\titlespacing*{{\section}}{{0pt}}{{{layout.section_spacing}pt}}{{{layout.heading_content_spacing}pt}}
\begin{{document}}
\fontsize{{{layout.body_size}}}{{{leading:.2f}}}\selectfont
\begin{{center}}
{{{name_style} {name}}}\\[1pt]
{header_lines}
\end{{center}}
\vspace{{-5pt}}
{sections}
\end{{document}}
"""

    @classmethod
    def _latex_section(cls, section: ResumeSection) -> str:
        output = [rf"\section*{{{cls._latex_escape(section.heading)}}}"]
        in_list = False
        for index, line in enumerate(section.lines):
            if cls.is_bullet(line):
                if not in_list:
                    output.append(r"\begin{itemize}")
                    in_list = True
                output.append(rf"\item {cls._latex_text(cls.bullet_text(line))}")
                continue
            if in_list:
                output.append(r"\end{itemize}")
                in_list = False
            next_is_bullet = (
                index + 1 < len(section.lines)
                and cls.is_bullet(section.lines[index + 1])
            )
            value = cls._latex_text(line)
            if next_is_bullet:
                output.append(rf"\textbf{{{value}}}\par")
            else:
                output.append(rf"{value}\par")
        if in_list:
            output.append(r"\end{itemize}")
        return "\n".join(output)

    @classmethod
    def _latex_text(cls, text: str) -> str:
        link_pattern = re.compile(r"(?:https?://|mailto:|tel:)[^\s<>]+")
        parts: list[str] = []
        position = 0
        for match in link_pattern.finditer(text):
            parts.append(cls._latex_escape(text[position : match.start()]))
            url = match.group(0).replace("{", "%7B").replace("}", "%7D")
            parts.append(rf"\href{{\detokenize{{{url}}}}}{{\nolinkurl{{{url}}}}}")
            position = match.end()
        parts.append(cls._latex_escape(text[position:]))
        return "".join(parts)

    @staticmethod
    def _latex_escape(text: str) -> str:
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }
        return "".join(replacements.get(character, character) for character in text)

    @classmethod
    def _validate_pdf(cls, content: bytes, expected: str) -> None:
        with fitz.open(stream=content, filetype="pdf") as document:
            extracted = "\n".join(page.get_text("text") for page in document)
        cls._validate_text(expected, extracted)

    @staticmethod
    def _validate_text(expected: str, extracted: str) -> None:
        expected_words = set(re.findall(r"[a-z0-9+#.]{2,}", expected.lower()))
        extracted_words = set(re.findall(r"[a-z0-9+#.]{2,}", extracted.lower()))
        if not expected_words:
            return
        coverage = len(expected_words & extracted_words) / len(expected_words)
        if coverage < 0.95:
            raise ResumeExportValidationError()

import io
import zipfile

import fitz
from docx import Document

from app.core.config import settings


class ResumeParsingError(Exception):
    """Raised when a resume file cannot be parsed."""


class ResumeParser:
    @staticmethod
    def parse_pdf(content: bytes) -> tuple[str, int]:
        if not content.startswith(b"%PDF-"):
            raise ResumeParsingError("The file contents are not a valid PDF.")

        try:
            document = fitz.open(stream=content, filetype="pdf")
        except (fitz.FileDataError, RuntimeError, ValueError) as error:
            raise ResumeParsingError("The PDF file could not be read.") from error

        try:
            if document.is_encrypted:
                raise ResumeParsingError("Password-protected PDFs are not supported.")

            text = "\n".join(page.get_text("text") for page in document).strip()
            return text, len(document)
        finally:
            document.close()

    @staticmethod
    def parse_docx(content: bytes) -> tuple[str, None]:
        ResumeParser._validate_docx_archive(content)

        try:
            document = Document(io.BytesIO(content))
        except Exception as error:
            raise ResumeParsingError("The DOCX file could not be read.") from error

        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        table_cells = [
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        ]
        text = "\n".join(paragraphs + table_cells).strip()

        # DOCX files do not store a reliable rendered page count.
        return text, None

    @staticmethod
    def _validate_docx_archive(content: bytes) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                uncompressed_size = sum(item.file_size for item in archive.infolist())
        except (zipfile.BadZipFile, OSError) as error:
            raise ResumeParsingError(
                "The file contents are not a valid DOCX."
            ) from error

        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise ResumeParsingError("The file contents are not a valid DOCX.")

        if uncompressed_size > settings.max_docx_uncompressed_bytes:
            raise ResumeParsingError("The DOCX contents exceed the allowed limit.")

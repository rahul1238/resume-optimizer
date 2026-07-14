from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from app.core.config import settings
from app.models.resume import ResumeRecord
from app.parsers.resume_parser import ResumeParser, ResumeParsingError
from app.repositories.resume_repository import ResumeRepository, ResumeRepositoryError
from app.services.resume_storage_service import ResumeStorageService


class ResumeUploadError(Exception):
    status_code = 400
    code = "resume_upload_error"
    message = "The resume upload could not be processed."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class UnsupportedResumeFormatError(ResumeUploadError):
    """Raised when an uploaded file is not a supported resume format."""

    status_code = 415
    code = "unsupported_resume_format"
    message = "Only PDF and DOCX resumes are supported."


class ResumeTooLargeError(ResumeUploadError):
    """Raised when an uploaded file exceeds the allowed size."""

    status_code = 413
    code = "resume_too_large"
    message = "Resume must not exceed 5 MB."


class EmptyResumeError(ResumeUploadError):
    """Raised when an uploaded file contains no usable resume text."""

    code = "empty_resume"
    message = "Uploaded file is empty."


class ResumeUnreadableError(ResumeUploadError):
    """Raised when a supported resume file cannot be parsed."""

    status_code = 422
    code = "unreadable_resume"
    message = "Unable to read this resume file."


class ResumeTextNotFoundError(ResumeUploadError):
    """Raised when a resume has no extractable text."""

    status_code = 422
    code = "resume_text_not_found"
    message = "No readable text was found in this resume."


@dataclass(frozen=True)
class ParsedResume:
    resume_id: str
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int | None
    storage_path: str
    text_storage_path: str
    text: str


class ResumeUploadService:
    allowed_extensions = {".pdf", ".docx"}

    @classmethod
    def process(cls, owner_uid: str, filename: str, content: bytes) -> ParsedResume:
        safe_filename = Path(filename).name or "resume"
        extension = Path(safe_filename).suffix.lower()

        if extension not in cls.allowed_extensions:
            raise UnsupportedResumeFormatError()

        if len(content) > settings.max_resume_upload_bytes:
            raise ResumeTooLargeError()

        if not content:
            raise EmptyResumeError()

        content_sha256 = sha256(content).hexdigest()
        existing = ResumeRepository.find_owned_by_hash(owner_uid, content_sha256)

        try:
            if extension == ".pdf":
                text, page_count = ResumeParser.parse_pdf(content)
                file_type: Literal["pdf", "docx"] = "pdf"
            else:
                text, page_count = ResumeParser.parse_docx(content)
                file_type = "docx"
        except ResumeParsingError as error:
            raise ResumeUnreadableError() from error

        if not text:
            raise ResumeTextNotFoundError()

        if existing:
            stored_text = ResumeStorageService.read_text(existing.text_storage_path)
            if stored_text != text:
                ResumeStorageService.write_text(existing.text_storage_path, text)
            ResumeRepository.update_extracted_metadata(
                existing.resume_id,
                len(text),
                page_count,
            )
            return ParsedResume(
                resume_id=existing.resume_id,
                filename=existing.filename,
                file_type=existing.file_type,
                page_count=page_count,
                storage_path=existing.original_storage_path,
                text_storage_path=existing.text_storage_path,
                text=text,
            )

        resume_id = str(uuid5(NAMESPACE_URL, f"{owner_uid}:{content_sha256}"))
        stored_resume = ResumeStorageService.store_original(
            owner_uid=owner_uid,
            filename=safe_filename,
            extension=extension,
            content=content,
            extracted_text=text,
            resume_id=resume_id,
        )

        try:
            ResumeRepository.create(
                ResumeRecord(
                    resume_id=stored_resume.resume_id,
                    owner_uid=owner_uid,
                    filename=safe_filename,
                    file_type=file_type,
                    page_count=page_count,
                    character_count=len(text),
                    original_storage_path=stored_resume.storage_path,
                    text_storage_path=stored_resume.text_storage_path,
                    content_sha256=content_sha256,
                )
            )
        except ResumeRepositoryError:
            ResumeStorageService.delete_paths(
                stored_resume.storage_path,
                stored_resume.text_storage_path,
            )
            raise

        return ParsedResume(
            resume_id=stored_resume.resume_id,
            filename=safe_filename,
            file_type=file_type,
            page_count=page_count,
            storage_path=stored_resume.storage_path,
            text_storage_path=stored_resume.text_storage_path,
            text=text,
        )

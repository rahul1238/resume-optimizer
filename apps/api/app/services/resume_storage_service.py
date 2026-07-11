from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class ResumeStorageError(Exception):
    status_code = 503
    code = "resume_storage_unavailable"
    message = "Resume storage is temporarily unavailable. Please try again."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ResumeStorageConfigurationError(ResumeStorageError):
    code = "resume_storage_not_configured"
    message = "Resume storage is not configured."


@dataclass(frozen=True)
class StoredResume:
    resume_id: str
    storage_path: str


class ResumeStorageService:
    content_types: dict[Literal[".pdf", ".docx"], str] = {
        ".pdf": "application/pdf",
        ".docx": (
            "application/"
            "vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    }

    @staticmethod
    @lru_cache
    def _client():
        if not all(
            [
                settings.r2_endpoint_url,
                settings.r2_access_key_id,
                settings.r2_secret_access_key,
                settings.r2_bucket_name,
            ]
        ):
            raise ResumeStorageConfigurationError()

        return boto3.client(
            service_name="s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(
                connect_timeout=5,
                read_timeout=settings.r2_upload_timeout_seconds,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    @classmethod
    def store_original(
        cls,
        owner_uid: str,
        filename: str,
        extension: Literal[".pdf", ".docx"] | str,
        content: bytes,
    ) -> StoredResume:
        if extension not in cls.content_types:
            raise ResumeStorageError("Unsupported storage file type.")

        resume_id = str(uuid4())
        owner_key = quote(owner_uid, safe="")
        storage_path = f"resumes/{owner_key}/{resume_id}/original{extension}"

        try:
            cls._client().put_object(
                Bucket=settings.r2_bucket_name,
                Key=storage_path,
                Body=content,
                ContentType=cls.content_types[extension],
                Metadata={
                    "owner-uid": owner_uid,
                    "resume-id": resume_id,
                    "original-filename": filename,
                },
            )
        except (BotoCoreError, ClientError, ValueError) as error:
            raise ResumeStorageError() from error

        return StoredResume(resume_id=resume_id, storage_path=storage_path)

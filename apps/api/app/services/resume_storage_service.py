import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    text_storage_path: str


class ResumeStorageService:
    content_types: dict[Literal[".pdf", ".docx"], str] = {
        ".pdf": "application/pdf",
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
        extracted_text: str,
        resume_id: str,
    ) -> StoredResume:
        if extension not in cls.content_types:
            raise ResumeStorageError("Unsupported storage file type.")

        owner_key = quote(owner_uid, safe="")
        storage_path = f"resumes/{owner_key}/{resume_id}/original{extension}"
        text_storage_path = f"resumes/{owner_key}/{resume_id}/extracted.txt"

        try:
            client = cls._client()
            client.put_object(
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
            client.put_object(
                Bucket=settings.r2_bucket_name,
                Key=text_storage_path,
                Body=extracted_text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
                Metadata={"owner-uid": owner_uid, "resume-id": resume_id},
            )
        except (BotoCoreError, ClientError, ValueError) as error:
            cls.delete_paths(storage_path, text_storage_path)
            raise ResumeStorageError() from error

        return StoredResume(
            resume_id=resume_id,
            storage_path=storage_path,
            text_storage_path=text_storage_path,
        )

    @classmethod
    def delete_paths(cls, *storage_paths: str) -> None:
        paths = [path for path in storage_paths if path]
        if not paths:
            return
        try:
            cls._client().delete_objects(
                Bucket=settings.r2_bucket_name,
                Delete={"Objects": [{"Key": path} for path in paths], "Quiet": True},
            )
        except (BotoCoreError, ClientError, ValueError):
            logger.exception("Failed to clean up resume storage objects")

    @classmethod
    def read_text(cls, storage_path: str) -> str:
        try:
            response = cls._client().get_object(
                Bucket=settings.r2_bucket_name,
                Key=storage_path,
            )
            return response["Body"].read().decode("utf-8")
        except (BotoCoreError, ClientError, UnicodeDecodeError, ValueError) as error:
            raise ResumeStorageError(
                "Unable to retrieve parsed resume text."
            ) from error

    @classmethod
    def write_text(cls, storage_path: str, text: str) -> None:
        try:
            cls._client().put_object(
                Bucket=settings.r2_bucket_name,
                Key=storage_path,
                Body=text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
        except (BotoCoreError, ClientError, ValueError) as error:
            raise ResumeStorageError(
                "Unable to refresh parsed resume text."
            ) from error

    @classmethod
    def read_bytes(cls, storage_path: str) -> bytes:
        try:
            response = cls._client().get_object(
                Bucket=settings.r2_bucket_name,
                Key=storage_path,
            )
            return response["Body"].read()
        except (BotoCoreError, ClientError, ValueError) as error:
            raise ResumeStorageError(
                "Unable to retrieve the original resume."
            ) from error

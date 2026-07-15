import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from firebase_admin import exceptions, firestore
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter

from app.auth.firebase import get_firebase_app
from app.models.resume import ResumeRecord

logger = logging.getLogger(__name__)


class ResumeRepositoryError(Exception):
    status_code = 503
    code = "resume_repository_unavailable"
    message = "Resume metadata storage is temporarily unavailable."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ResumeNotFoundError(ResumeRepositoryError):
    status_code = 404
    code = "resume_not_found"
    message = "Resume was not found."


class ResumeRepository:
    collection_name = "resumes"

    @staticmethod
    @lru_cache
    def _client():
        return firestore.client(app=get_firebase_app())

    @classmethod
    def create(cls, record: ResumeRecord) -> None:
        payload = {
            "owner_uid": record.owner_uid,
            "filename": record.filename,
            "file_type": record.file_type,
            "page_count": record.page_count,
            "character_count": record.character_count,
            "original_storage_path": record.original_storage_path,
            "text_storage_path": record.text_storage_path,
            "content_sha256": record.content_sha256,
            "title": record.title or Path(record.filename).stem,
            "tags": list(record.tags),
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        try:
            cls._client().collection(cls.collection_name).document(
                record.resume_id
            ).set(payload)
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to persist resume metadata")
            raise ResumeRepositoryError() from error

    @classmethod
    def find_owned_by_hash(
        cls,
        owner_uid: str,
        content_sha256: str,
    ) -> ResumeRecord | None:
        try:
            snapshots = (
                cls._client()
                .collection(cls.collection_name)
                .where(filter=FieldFilter("content_sha256", "==", content_sha256))
                .stream()
            )
            for snapshot in snapshots:
                data = snapshot.to_dict() or {}
                if data.get("owner_uid") == owner_uid:
                    return cls._from_snapshot(snapshot, data)
            return None
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to find resume metadata")
            raise ResumeRepositoryError() from error

    @classmethod
    def list_owned(cls, owner_uid: str) -> list[ResumeRecord]:
        try:
            snapshots = (
                cls._client()
                .collection(cls.collection_name)
                .where(filter=FieldFilter("owner_uid", "==", owner_uid))
                .stream()
            )
            records = [
                cls._from_snapshot(snapshot, snapshot.to_dict() or {})
                for snapshot in snapshots
            ]
            return sorted(
                records,
                key=lambda record: (
                    record.created_at or datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=True,
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to list resume metadata")
            raise ResumeRepositoryError() from error

    @classmethod
    def delete(cls, resume_id: str) -> None:
        try:
            cls._client().collection(cls.collection_name).document(resume_id).delete()
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to delete resume metadata")
            raise ResumeRepositoryError() from error

    @classmethod
    def update_extracted_metadata(
        cls,
        resume_id: str,
        character_count: int,
        page_count: int | None,
    ) -> None:
        try:
            cls._client().collection(cls.collection_name).document(resume_id).update(
                {
                    "character_count": character_count,
                    "page_count": page_count,
                }
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to update parsed resume metadata")
            raise ResumeRepositoryError() from error

    @classmethod
    def update_profile(
        cls,
        resume_id: str,
        title: str,
        tags: list[str],
    ) -> None:
        try:
            cls._client().collection(cls.collection_name).document(resume_id).update(
                {"title": title, "tags": tags}
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to update base resume metadata")
            raise ResumeRepositoryError() from error

    @classmethod
    def get_owned(cls, resume_id: str, owner_uid: str) -> ResumeRecord:
        try:
            snapshot = (
                cls._client().collection(cls.collection_name).document(resume_id).get()
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to read resume metadata")
            raise ResumeRepositoryError() from error

        if not snapshot.exists:
            raise ResumeNotFoundError()

        data = snapshot.to_dict() or {}
        if data.get("owner_uid") != owner_uid:
            # Do not reveal whether another user owns this identifier.
            raise ResumeNotFoundError()

        return cls._from_snapshot(snapshot, data)

    @staticmethod
    def _from_snapshot(snapshot, data: dict[str, object]) -> ResumeRecord:
        return ResumeRecord(
            resume_id=snapshot.id,
            owner_uid=data["owner_uid"],
            filename=data["filename"],
            file_type=data["file_type"],
            page_count=data.get("page_count"),
            character_count=data["character_count"],
            original_storage_path=data["original_storage_path"],
            text_storage_path=data["text_storage_path"],
            content_sha256=data.get("content_sha256"),
            title=str(data.get("title") or Path(str(data["filename"])).stem),
            tags=tuple(str(tag) for tag in data.get("tags", []) if str(tag).strip()),
            created_at=data.get("created_at"),
        )

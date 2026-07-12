import logging
from functools import lru_cache

from firebase_admin import exceptions, firestore
from google.api_core.exceptions import GoogleAPICallError

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
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        try:
            cls._client().collection(cls.collection_name).document(
                record.resume_id
            ).create(payload)
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to persist resume metadata")
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

        return ResumeRecord(
            resume_id=snapshot.id,
            owner_uid=data["owner_uid"],
            filename=data["filename"],
            file_type=data["file_type"],
            page_count=data.get("page_count"),
            character_count=data["character_count"],
            original_storage_path=data["original_storage_path"],
            text_storage_path=data["text_storage_path"],
            created_at=data.get("created_at"),
        )

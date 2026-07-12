import logging
from functools import lru_cache

from firebase_admin import exceptions, firestore
from google.api_core.exceptions import GoogleAPICallError

from app.auth.firebase import get_firebase_app
from app.models.improvement import ImprovementRecord

logger = logging.getLogger(__name__)


class ImprovementRepositoryError(Exception):
    status_code = 503
    code = "improvement_repository_unavailable"
    message = "Resume improvement storage is temporarily unavailable."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ImprovementNotFoundError(ImprovementRepositoryError):
    status_code = 404
    code = "improvement_not_found"
    message = "Resume improvements were not found."


class ImprovementRepository:
    collection_name = "analysis_improvements"

    @staticmethod
    @lru_cache
    def _client():
        return firestore.client(app=get_firebase_app())

    @classmethod
    def save(cls, record: ImprovementRecord) -> None:
        try:
            cls._client().collection(cls.collection_name).document(
                record.analysis_id
            ).set(
                {
                    "owner_uid": record.owner_uid,
                    "resume_id": record.resume_id,
                    "provider": record.provider,
                    "model": record.model,
                    "result": record.result,
                    "created_at": firestore.SERVER_TIMESTAMP,
                }
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to persist resume improvements")
            raise ImprovementRepositoryError() from error

    @classmethod
    def get_owned(cls, analysis_id: str, owner_uid: str) -> ImprovementRecord:
        try:
            snapshot = (
                cls._client()
                .collection(cls.collection_name)
                .document(analysis_id)
                .get()
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to read resume improvements")
            raise ImprovementRepositoryError() from error
        if not snapshot.exists:
            raise ImprovementNotFoundError()
        data = snapshot.to_dict() or {}
        if data.get("owner_uid") != owner_uid:
            raise ImprovementNotFoundError()
        return ImprovementRecord(
            analysis_id=snapshot.id,
            owner_uid=data["owner_uid"],
            resume_id=data["resume_id"],
            provider=data["provider"],
            model=data["model"],
            result=data["result"],
            created_at=data.get("created_at"),
        )

    @classmethod
    def delete(cls, analysis_id: str) -> None:
        try:
            cls._client().collection(cls.collection_name).document(analysis_id).delete()
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to delete resume improvements")
            raise ImprovementRepositoryError() from error

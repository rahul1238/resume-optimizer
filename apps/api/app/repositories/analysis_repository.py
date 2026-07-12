import logging
from functools import lru_cache

from firebase_admin import exceptions, firestore
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1.base_query import FieldFilter

from app.auth.firebase import get_firebase_app
from app.models.analysis import AnalysisRecord

logger = logging.getLogger(__name__)


class AnalysisRepositoryError(Exception):
    status_code = 503
    code = "analysis_repository_unavailable"
    message = "Analysis storage is temporarily unavailable."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class AnalysisRepository:
    collection_name = "analyses"

    @staticmethod
    @lru_cache
    def _client():
        return firestore.client(app=get_firebase_app())

    @classmethod
    def create(cls, record: AnalysisRecord) -> None:
        payload = {
            "owner_uid": record.owner_uid,
            "resume_id": record.resume_id,
            "job_description": record.job_description,
            "job_title": record.job_title,
            "company_name": record.company_name,
            "provider": record.provider,
            "model": record.model,
            "status": record.status,
            "result": record.result,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        try:
            cls._client().collection(cls.collection_name).document(
                record.analysis_id
            ).create(payload)
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to persist analysis")
            raise AnalysisRepositoryError() from error

    @classmethod
    def delete_for_resume(cls, resume_id: str, owner_uid: str) -> None:
        try:
            collection = cls._client().collection(cls.collection_name)
            snapshots = collection.where(
                filter=FieldFilter("resume_id", "==", resume_id)
            ).stream()
            batch = cls._client().batch()
            changed = False
            for snapshot in snapshots:
                data = snapshot.to_dict() or {}
                if data.get("owner_uid") == owner_uid:
                    batch.delete(snapshot.reference)
                    changed = True
            if changed:
                batch.commit()
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to delete resume analyses")
            raise AnalysisRepositoryError() from error

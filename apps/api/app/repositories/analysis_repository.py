import logging
from datetime import datetime, timezone
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


class AnalysisNotFoundError(AnalysisRepositoryError):
    status_code = 404
    code = "analysis_not_found"
    message = "Analysis was not found."


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
    def list_owned(
        cls,
        owner_uid: str,
        resume_id: str | None = None,
    ) -> list[AnalysisRecord]:
        try:
            snapshots = (
                cls._client()
                .collection(cls.collection_name)
                .where(filter=FieldFilter("owner_uid", "==", owner_uid))
                .stream()
            )
            records = []
            for snapshot in snapshots:
                data = snapshot.to_dict() or {}
                if resume_id is None or data.get("resume_id") == resume_id:
                    records.append(cls._from_snapshot(snapshot, data))
            return sorted(
                records,
                key=lambda record: (
                    record.created_at or datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=True,
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to list analyses")
            raise AnalysisRepositoryError() from error

    @classmethod
    def get_owned(cls, analysis_id: str, owner_uid: str) -> AnalysisRecord:
        try:
            snapshot = (
                cls._client()
                .collection(cls.collection_name)
                .document(analysis_id)
                .get()
            )
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to read analysis")
            raise AnalysisRepositoryError() from error

        if not snapshot.exists:
            raise AnalysisNotFoundError()
        data = snapshot.to_dict() or {}
        if data.get("owner_uid") != owner_uid:
            raise AnalysisNotFoundError()
        return cls._from_snapshot(snapshot, data)

    @classmethod
    def delete(cls, analysis_id: str) -> None:
        try:
            cls._client().collection(cls.collection_name).document(analysis_id).delete()
        except (GoogleAPICallError, exceptions.FirebaseError, ValueError) as error:
            logger.exception("Failed to delete analysis")
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

    @staticmethod
    def _from_snapshot(snapshot, data: dict[str, object]) -> AnalysisRecord:
        return AnalysisRecord(
            analysis_id=snapshot.id,
            owner_uid=data["owner_uid"],
            resume_id=data["resume_id"],
            job_description=data["job_description"],
            job_title=data.get("job_title"),
            company_name=data.get("company_name"),
            provider=data["provider"],
            model=data["model"],
            status=data["status"],
            result=data["result"],
            created_at=data.get("created_at"),
        )

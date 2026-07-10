from functools import lru_cache

import firebase_admin
from firebase_admin import App, credentials

from app.core.config import settings


@lru_cache
def get_firebase_app() -> App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        options = (
            {"projectId": settings.firebase_project_id}
            if settings.firebase_project_id
            else None
        )
        credential = (
            credentials.Certificate(settings.firebase_service_account_path)
            if settings.firebase_service_account_path
            else None
        )
        return firebase_admin.initialize_app(credential=credential, options=options)

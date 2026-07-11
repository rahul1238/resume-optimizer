from functools import lru_cache

import firebase_admin
from firebase_admin import App, credentials

from app.core.config import settings


@lru_cache
def get_firebase_app() -> App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        options: dict[str, str] = {}
        if settings.firebase_project_id:
            options["projectId"] = settings.firebase_project_id
        credential = (
            credentials.Certificate(settings.firebase_service_account_path)
            if settings.firebase_service_account_path
            else None
        )
        return firebase_admin.initialize_app(
            credential=credential,
            options=options or None,
        )

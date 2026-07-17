import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings

PRODUCTION_VALUES = {
    "app_env": "production",
    "cors_allowed_origins": ["https://resume.example.com"],
    "firebase_project_id": "resume-project",
    "firebase_service_account_json": json.dumps(
        {
            "type": "service_account",
            "project_id": "resume-project",
            "client_email": "firebase-admin@example.com",
            "private_key": "test-only-key",
        }
    ),
    "gemini_api_key": "test-gemini-key",
    "r2_endpoint_url": "https://example.r2.cloudflarestorage.com",
    "r2_access_key_id": "test-r2-key",
    "r2_secret_access_key": "test-r2-secret",
    "r2_bucket_name": "resume-optimizer",
}


def test_production_configuration_accepts_environment_credentials() -> None:
    configured = Settings(_env_file=None, **PRODUCTION_VALUES)

    assert configured.firebase_service_account_data()["project_id"] == (
        "resume-project"
    )
    assert "test-gemini-key" not in repr(configured)


def test_production_configuration_reports_all_missing_services() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            app_env="production",
            cors_allowed_origins=["https://resume.example.com"],
        )

    message = str(error.value)
    assert "FIREBASE_PROJECT_ID" in message
    assert "FIREBASE_SERVICE_ACCOUNT_JSON" in message
    assert "GEMINI_API_KEY" in message
    assert "R2_BUCKET_NAME" in message


@pytest.mark.parametrize(
    "origins",
    [
        ["http://localhost:3000"],
        ["*"],
        ["http://resume.example.com"],
    ],
)
def test_production_configuration_rejects_unsafe_origins(
    origins: list[str],
) -> None:
    with pytest.raises(ValidationError, match="deployed HTTPS origins"):
        Settings(
            _env_file=None,
            **{**PRODUCTION_VALUES, "cors_allowed_origins": origins},
        )


def test_production_configuration_rejects_invalid_service_account_json() -> None:
    with pytest.raises(ValidationError, match="must contain valid JSON"):
        Settings(
            _env_file=None,
            **{
                **PRODUCTION_VALUES,
                "firebase_service_account_json": "not-json",
            },
        )


def test_development_allows_partial_configuration() -> None:
    configured = Settings(_env_file=None, app_env="development")

    assert configured.app_env == "development"

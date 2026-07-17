import json
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Resume Optimizer API"
    app_env: Literal["development", "test", "production"] = "development"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    firebase_project_id: str | None = None
    firebase_service_account_json: SecretStr | None = None
    firebase_service_account_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FIREBASE_SERVICE_ACCOUNT_PATH",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ),
    )
    firebase_web_api_key: SecretStr | None = None
    firebase_check_revoked_tokens: bool = True
    r2_endpoint_url: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket_name: str | None = None
    r2_upload_timeout_seconds: int = 30
    max_resume_upload_bytes: int = 5 * 1024 * 1024
    max_docx_uncompressed_bytes: int = 20 * 1024 * 1024
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_fallback_models: list[str] = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
    ]
    gemini_timeout_seconds: int = 60
    tectonic_binary: str = "tectonic"
    tectonic_only_cached: bool = True
    latex_compile_timeout_seconds: int = 30
    max_job_description_characters: int = 30_000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    def firebase_service_account_data(self) -> dict[str, object] | None:
        if not self.firebase_service_account_json:
            return None
        try:
            value = json.loads(
                self.firebase_service_account_json.get_secret_value()
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must contain valid JSON."
            ) from error
        if not isinstance(value, dict):
            raise ValueError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must contain a JSON object."
            )
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.app_env != "production":
            return self

        required_values = {
            "FIREBASE_PROJECT_ID": self.firebase_project_id,
            "GEMINI_API_KEY": self.gemini_api_key,
            "R2_ENDPOINT_URL": self.r2_endpoint_url,
            "R2_ACCESS_KEY_ID": self.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": self.r2_secret_access_key,
            "R2_BUCKET_NAME": self.r2_bucket_name,
        }
        missing = [name for name, value in required_values.items() if not value]
        if not (
            self.firebase_service_account_json
            or self.firebase_service_account_path
        ):
            missing.append(
                "FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH"
            )
        if missing:
            raise ValueError(
                "Missing required production configuration: " + ", ".join(missing)
            )

        self.firebase_service_account_data()
        invalid_origins = [
            origin
            for origin in self.cors_allowed_origins
            if origin == "*" or "localhost" in origin or "127.0.0.1" in origin
        ]
        if not self.cors_allowed_origins or invalid_origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain only deployed HTTPS origins "
                "in production."
            )
        has_non_https_origin = any(
            not origin.startswith("https://")
            for origin in self.cors_allowed_origins
        )
        if has_non_https_origin:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain only deployed HTTPS origins "
                "in production."
            )
        return self


settings = Settings()

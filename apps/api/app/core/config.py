from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Resume Optimizer API"
    app_env: str = "development"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    firebase_project_id: str | None = None
    firebase_service_account_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FIREBASE_SERVICE_ACCOUNT_PATH",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ),
    )
    firebase_web_api_key: str | None = None
    firebase_check_revoked_tokens: bool = True
    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_upload_timeout_seconds: int = 30
    max_resume_upload_bytes: int = 5 * 1024 * 1024
    max_docx_uncompressed_bytes: int = 20 * 1024 * 1024
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-3.5-flash"
    gemini_timeout_seconds: int = 60
    max_job_description_characters: int = 30_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

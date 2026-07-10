from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Resume Optimizer API"
    app_env: str = "development"
    firebase_project_id: str | None = None
    firebase_service_account_path: str | None = None
    firebase_web_api_key: str | None = None
    firebase_check_revoked_tokens: bool = True
    max_resume_upload_bytes: int = 5 * 1024 * 1024
    max_docx_uncompressed_bytes: int = 20 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

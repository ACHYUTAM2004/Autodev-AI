from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AutoDev AI"
    environment: str = "development"
    log_level: str = "INFO"

    # ✅ ADD THIS
    google_api_key: str

    class Config:
        env_file = ".env"
        case_sensitive = False  # allows OPENAI_API_KEY

settings = Settings()

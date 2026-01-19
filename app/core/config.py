from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AutoDev AI"
    environment: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()

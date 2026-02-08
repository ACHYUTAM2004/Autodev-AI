import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoDev AI"
    VERSION: str = "0.1.0"
    
    # Gemini Configuration
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    # "gemini-1.5-pro" is recommended for complex reasoning (Planner/Tech Lead)
    # "gemini-1.5-flash" is faster/cheaper for simple tasks
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-1.5-pro") 

    # Base directory for generating projects
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    GENERATION_DIR: str = os.path.join(BASE_DIR, "generated_projects")
    
    # Logging paths
    LOG_DIR: str = os.path.join(BASE_DIR, "logs")

    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.GENERATION_DIR, exist_ok=True)
os.makedirs(settings.LOG_DIR, exist_ok=True)
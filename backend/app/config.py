from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vidflow"

    # APIs
    GEMINI_API_KEY: str = ""
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""

    # App
    SECRET_KEY: str = "change-me-in-production-very-long-secret-key"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    UPLOAD_DIR: str = "/tmp/vidflow_uploads"
    OUTPUT_DIR: str = "/tmp/vidflow_outputs"

    # Optional external services
    N8N_WEBHOOK_URL: Optional[str] = None
    WHATSAPP_NUMBER: Optional[str] = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

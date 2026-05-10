import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    upload_dir: str = "./uploads"
    output_dir: str = "./output"
    max_upload_size_mb: int = 500
    max_images: int = 1000
    log_level: str = "INFO"
    auth_username: str = "admin"
    auth_password: str = "album2024"
    auth_secret_key: str = "change-this-secret"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Use absolute paths based on the backend directory
_BACKEND_DIR = Path(__file__).parent.parent
UPLOAD_PATH = (_BACKEND_DIR / settings.upload_dir).resolve()
OUTPUT_PATH = (_BACKEND_DIR / settings.output_dir).resolve()
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

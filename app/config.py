from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os


class Settings(BaseSettings):
    # App
    app_name: str
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    max_videos_limit: int = 10

    # Database
    database_url: str

    # AWS
    aws_region: str = "us-west-2"
    s3_bucket_name: str
    sqs_queue_url: str

    # pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "video-frames"

    # Processing
    max_video_size_mb: int = 500
    supported_formats: List[str] = ["mp4", "avi", "mov", "mkv"]

    # IMPORTANT:
    # - By default, reads from environment variables
    model_config = SettingsConfigDict(
        env_file=".env" if os.getenv("LOAD_DOTENV", "false").lower() == "true" else None,
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

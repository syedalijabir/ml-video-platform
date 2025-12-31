from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models import JobStatus


class VideoUploadResponse(BaseModel):
    id: str
    job_id: str | None = None
    filename: str
    s3_key: str
    size_bytes: int
    uploaded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class VideoDetail(BaseModel):
    id: str
    filename: str
    s3_key: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    format: str
    uploaded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class JobCreateRequest(BaseModel):
    video_id: str = Field(..., description="ID of the video to process")


class JobCreateResponse(BaseModel):
    id: str
    video_id: str
    status: JobStatus
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class JobDetail(BaseModel):
    id: str
    video_id: str
    status: JobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    processing_time_seconds: Optional[float] = None
    frames_processed: Optional[int] = None
    embeddings_stored: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class HealthCheck(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    database: str = "connected"
    s3: str = "connected"
    sqs: str = "connected"


class SearchRequest(BaseModel):
    query: str = Field(..., description="Text query to search for (e.g., 'a walking cat')")
    threshold: float = Field(0.25, ge=0.0, le=1.0, description="Minimum similarity score (0-1)")
    max_results_per_video: int = Field(5, ge=1, le=50, description="Maximum matches per video")
    max_videos: int = Field(10, ge=1, le=100, description="Maximum number of videos to return")
    video_ids: Optional[List[str]] = Field(None, description="Optional: search only in specific videos")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "a walking cat",
                "threshold": 0.25,
                "max_results_per_video": 5,
                "max_videos": 10
            }
        }


class SearchMatch(BaseModel):
    frame_id: int
    frame_index: int
    timestamp: float
    time_formatted: str
    similarity_score: float


class SearchResult(BaseModel):
    video_id: str
    video_filename: str
    matches: List[SearchMatch]


class SearchResponse(BaseModel):
    query: str
    total_videos: int
    total_matches: int
    results: List[SearchResult]
    average_similarity: float


class DeleteVideoResponse(BaseModel):
    status: str
    message: str


class VideoStats(BaseModel):
    video_count: int
    total_size_mb: float
    max_videos: int
    remaining_slots: int
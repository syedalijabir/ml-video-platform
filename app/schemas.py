from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any
from app.models import JobStatus


class VideoUploadResponse(BaseModel):
    id: str
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
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class HealthCheck(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    database: str = "connected"
    s3: str = "connected"
    sqs: str = "connected"
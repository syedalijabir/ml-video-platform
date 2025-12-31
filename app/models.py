from sqlalchemy import Column, String, Integer, DateTime, Float, JSON, Enum as SQLEnum, ForeignKey, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    s3_key = Column(String, nullable=False, unique=True)
    size_bytes = Column(Integer, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    format = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    frames = relationship("VideoFrame", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video {self.id}: {self.filename}>"


class VideoFrame(Base):
    __tablename__ = "video_frames"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, ForeignKey('videos.id'), nullable=False, index=True)
    frame_index = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False, index=True)

    # CLIP embedding as array (512 dimensions for CLIP ViT-B/32)
    embedding = Column(ARRAY(Float, dimensions=1), nullable=False)
    scene_description = Column(String, nullable=True)
    video = relationship("Video", back_populates="frames")

    def __repr__(self):
        return f"<VideoFrame {self.id}: video={self.video_id}, timestamp={self.timestamp}>"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    
    id = Column(String, primary_key=True, index=True)
    video_id = Column(String, nullable=False, index=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)
    
    results = Column(JSON, nullable=True)
    
    processing_time_seconds = Column(Float, nullable=True)
    frames_processed = Column(Integer, nullable=True)
    embeddings_stored = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<ProcessingJob {self.id}: {self.status}>"

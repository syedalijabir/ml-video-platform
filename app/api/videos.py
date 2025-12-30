from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import boto3
from botocore.exceptions import ClientError
import uuid
import os

from app.database import get_db
from app.config import get_settings
from app.models import Video
from app.schemas import VideoUploadResponse, VideoDetail

router = APIRouter()
settings = get_settings()


def get_s3_client():
    return boto3.client('s3', region_name=settings.aws_region)


def validate_video_file(file: UploadFile) -> None:
    """Validate uploaded video file"""
    # Check file extension
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in settings.supported_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format. Supported: {', '.join(settings.supported_formats)}"
        )
    
    # Check file size (done during upload in chunks)
    if hasattr(file, 'size') and file.size > settings.max_video_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.max_video_size_mb}MB"
        )


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    s3_client = Depends(get_s3_client)
):
    """Upload a video file to S3 and register it in the database"""
    
    validate_video_file(file)
    
    # Generate unique ID and S3 key
    video_id = str(uuid.uuid4())
    file_ext = file.filename.split('.')[-1].lower()
    s3_key = f"videos/{video_id}.{file_ext}"
    
    try:
        # Upload to S3
        file_content = await file.read()
        file_size = len(file_content)
        
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type or 'video/mp4'
        )
        
        # Create database record
        video = Video(
            id=video_id,
            filename=file.filename,
            s3_key=s3_key,
            size_bytes=file_size,
            format=file_ext
        )
        
        db.add(video)
        db.commit()
        db.refresh(video)
        
        return video
        
    except ClientError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload to S3: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, db: Session = Depends(get_db)):
    """Get video details by ID"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video {video_id} not found"
        )
    
    return video


@router.get("/", response_model=List[VideoDetail])
async def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all videos with pagination"""
    
    videos = db.query(Video).offset(skip).limit(limit).all()
    return videos


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    s3_client = Depends(get_s3_client)
):
    """Delete a video from S3 and database"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video {video_id} not found"
        )
    
    try:
        # Delete from S3
        s3_client.delete_object(
            Bucket=settings.s3_bucket_name,
            Key=video.s3_key
        )
        
        # Delete from database
        db.delete(video)
        db.commit()
        
    except ClientError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete from S3: {str(e)}"
        )
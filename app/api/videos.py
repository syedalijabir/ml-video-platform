from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
import boto3
from botocore.exceptions import ClientError
import json
import uuid
import os
from sqlalchemy import func

from app.database import get_db
from app.config import get_settings
from app.models import Video, ProcessingJob, JobStatus
from app.schemas import VideoUploadResponse, VideoDetail
from app.pinecone_client import delete_video_embeddings

router = APIRouter()
settings = get_settings()


def get_s3_client():
    return boto3.client('s3', region_name=settings.aws_region)


def get_sqs_client():
    return boto3.client("sqs", region_name=settings.aws_region)


def validate_video_file(file: UploadFile) -> None:
    """Validate uploaded video file"""
    # Check file extension
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in settings.supported_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format. Supported: {', '.join(settings.supported_formats)}"
        )
    
    # Check file size
    if hasattr(file, 'size') and file.size > settings.max_video_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.max_video_size_mb}MB"
        )


def check_video_limit(db: Session):
    """Check if maximum video limit is reached"""
    video_count = db.query(func.count(Video.id)).scalar()

    if video_count >= settings.max_videos_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Maximum video limit reached ({settings.max_videos_limit} videos). "
                f"Please delete some videos before uploading new ones."
            ),
        )

@router.get("/stats/count", status_code=status.HTTP_200_OK)
async def get_video_stats(db: Session = Depends(get_db)):
    """Get video statistics"""
    
    video_count = db.query(func.count(Video.id)).scalar()
    total_size_bytes = db.query(func.sum(Video.size_bytes)).scalar() or 0
    total_size_mb = total_size_bytes / (1024 * 1024)
    
    return {
        "video_count": video_count,
        "total_size_mb": round(total_size_mb, 2),
        "max_videos": settings.max_videos_limit,
        "remaining_slots": max(0, settings.max_videos_limit - video_count),
    }


@router.get("/{video_id}/play")
async def get_video_play_url(
    video_id: str,
    expires_seconds: int = Query(900, ge=60, le=3600),
    db: Session = Depends(get_db),
    s3_client = Depends(get_s3_client),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": video.s3_key},
            ExpiresIn=expires_seconds,
        )
        return {"video_id": video_id, "url": url}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate play URL: {e}")


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    s3_client  = Depends(get_s3_client),
    sqs_client = Depends(get_sqs_client)
):
    """Upload a video file to S3 and register it in the database"""
    check_video_limit(db)
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

        # auto-create a job
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            video_id=video_id,
            status=JobStatus.PENDING
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Send message to SQS
        message = {
            "job_id": job_id,
            "video_id": video_id,
            "s3_key": video.s3_key,
            "s3_bucket": settings.s3_bucket_name
        }
        sqs_client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(message),
            MessageAttributes={"JobId": {"StringValue": job_id, "DataType": "String"}}
        )
        
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
            
            
@router.get("/", response_model=List[VideoDetail])
async def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all videos with pagination"""    
    return (
        db.query(Video)
        .order_by(Video.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
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


@router.delete("/{video_id}", status_code=status.HTTP_200_OK)
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

    filename = video.filename
    s3_key = video.s3_key

    try:
        #Delete embeddings from Pinecone
        try:
            delete_video_embeddings(video_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete Pinecone embeddings for video {video_id}: {str(e)}",
            )

        #Delete associated jobs
        db.query(ProcessingJob).filter(ProcessingJob.video_id == video_id).delete()

        # Delete from S3
        try:
            s3_client.delete_object(
                Bucket=settings.s3_bucket_name,
                Key=video.s3_key
            )
        except ClientError:
            # continue with database deletion
            pass
        
        # Delete from database
        db.delete(video)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Video '{video.filename}' deleted successfully"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video: {str(e)}"
        )

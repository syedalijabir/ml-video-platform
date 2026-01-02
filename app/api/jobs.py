from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError
import uuid
import json

from app.database import get_db
from app.config import get_settings
from app.models import ProcessingJob, Video, JobStatus
from app.schemas import JobCreateRequest, JobCreateResponse, JobDetail

router = APIRouter()
settings = get_settings()


def get_sqs_client():
    return boto3.client('sqs', region_name=settings.aws_region)


@router.post("/", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_request: JobCreateRequest,
    db: Session = Depends(get_db),
    sqs_client = Depends(get_sqs_client)
):
    """Create a new video processing job and queue it"""
    
    # Verify video exists
    video = db.query(Video).filter(Video.id == job_request.video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video {job_request.video_id} not found"
        )
    
    # Create job
    job_id = str(uuid.uuid4())
    job = ProcessingJob(
        id=job_id,
        video_id=job_request.video_id,
        status=JobStatus.PENDING
    )
    
    try:
        # Save to database
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Send message to SQS
        message = {
            "job_id": job_id,
            "video_id": job_request.video_id,
            "s3_key": video.s3_key,
            "s3_bucket": settings.s3_bucket_name
        }
        
        sqs_client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'JobId': {
                    'StringValue': job_id,
                    'DataType': 'String'
                }
            }
        )
        
        return job
        
    except ClientError as e:
        db.rollback()
        # If SQS failed, mark job as failed
        try:
            job.status = JobStatus.FAILED
            job.error_message = f"SQS enqueue failed: {str(e)}"
            db.add(job)
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue job: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job creation failed: {str(e)}"
        )


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job details by ID"""
    
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return job


@router.get("/", response_model=List[JobDetail])
async def list_jobs(
    video_id: Optional[str] = None,
    status_filter: Optional[JobStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List jobs with optional filters"""
    
    query = db.query(ProcessingJob)
    
    if video_id:
        query = query.filter(ProcessingJob.video_id == video_id)
    
    if status_filter:
        query = query.filter(ProcessingJob.status == status_filter)
    
    jobs = (
        query.order_by(ProcessingJob.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return jobs


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a job record"""
    
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Only allow deletion of completed or failed jobs
    if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete job that is pending or processing"
        )
    
    try:
        db.delete(job)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job: {str(e)}",
        )
